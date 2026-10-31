from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.datasets.models import (
    Institute, Department, SourceArtifact, DatasetVersion, DatasetPolicy,
    DatasetActivation, CalendarVersion, CalendarDay, CalendarPeriod,
    CalendarBreak, CalendarLabStartPeriod, CalendarEventPeriod,
    CalendarExamDay, CalendarExamSession
)
from app.modules.academic.models import (
    Room, RoomFeature, RoomFeatureAssignment, RoomAllowedUse,
    RoomUnavailability, Faculty, FacultyDepartment, FacultyUnavailability,
    FacultyPreference, StudentGroup, Course, TeachingSession,
    TeachingSessionFaculty, SessionGroup, SessionAllowedRoomType
)
from app.modules.booking.models import (
    BookingRequest, BookingCancellation, BookingWindow,
    BookingAllowedRoomType, BookingRequiredFeature, BookingMandatoryGroup
)
from app.modules.exams.models import (
    ExamRecord, ExamCourse, ExamGroup
)
from app.modules.integration.models import ImportJob
from app.modules.integration.source_schemas import SourceDataset

class ValidationErrorDetail(Exception):
    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        self.message = message
        self.errors = errors or []
        msgs = "; ".join(e.get("msg", "") for e in self.errors)
        display_msg = f"{message}: {msgs}" if msgs else message
        super().__init__(display_msg)

class SourceImportService:
    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def validate_source(cls, raw_bytes: bytes) -> tuple[SourceDataset, dict[str, Any], str]:
        sha256 = cls.calculate_sha256(raw_bytes)
        try:
            raw_dict = json.loads(raw_bytes.decode("utf-8"))
        except Exception as e:
            raise ValidationErrorDetail(
                f"Malformed JSON: {str(e)}",
                [{"loc": ["root"], "msg": f"Malformed JSON: {str(e)}", "type": "json_decode_error"}]
            ) from e

        try:
            dataset = SourceDataset.model_validate_json(raw_bytes)
        except ValidationError as e:
            formatted_errors = []
            for err in e.errors():
                loc_str = " -> ".join(str(x) for x in err.get("loc", []))
                formatted_errors.append({
                    "loc": err.get("loc", []),
                    "path": loc_str,
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                })
            raise ValidationErrorDetail(
                f"Validation failed with {len(formatted_errors)} error(s)",
                formatted_errors
            ) from e

        return dataset, raw_dict, sha256

    @classmethod
    def import_source(
        cls,
        db: Session,
        raw_bytes: bytes,
        original_filename: str = "cit_public.json",
        imported_by: uuid.UUID | None = None,
        allow_duplicate: bool = False,
        fail_at_step: str | None = None,
    ) -> tuple[ImportJob, DatasetVersion, dict[str, Any]]:
        # 1. Validation
        dataset, raw_dict, sha256 = cls.validate_source(raw_bytes)

        # 2. Check for identical already-imported version (idempotency)
        existing_version = db.execute(
            select(DatasetVersion).where(
                DatasetVersion.source_sha256 == sha256,
                DatasetVersion.status.in_(["IMPORTED", "ACTIVE"])
            ).order_by(DatasetVersion.version_number.desc())
        ).scalars().first()

        if existing_version and not allow_duplicate:
            existing_job = db.execute(
                select(ImportJob).where(
                    ImportJob.dataset_version_id == existing_version.id,
                    ImportJob.status == "SUCCEEDED"
                ).order_by(ImportJob.created_at.desc())
            ).scalars().first()
            report = existing_job.report_json if existing_job else cls.build_reconciliation_report(db, existing_version.id)
            return existing_job or ImportJob(
                dataset_version_id=existing_version.id,
                status="SUCCEEDED",
                report_json=report
            ), existing_version, report

        # 3. Create initial ImportJob record
        job = ImportJob(
            status="RUNNING",
            started_at=datetime.now(),
            report_json={"stage": "importing", "sha256": sha256}
        )
        db.add(job)
        db.flush()

        try:
            # 4. Source artifact
            artifact = db.execute(
                select(SourceArtifact).where(SourceArtifact.sha256 == sha256)
            ).scalar_one_or_none()
            if not artifact:
                artifact = SourceArtifact(
                    storage_key=f"datasets/{sha256}/{original_filename}",
                    original_filename=original_filename,
                    mime_type="application/json",
                    size_bytes=len(raw_bytes),
                    sha256=sha256,
                )
                db.add(artifact)
                db.flush()

            job.source_artifact_id = artifact.id

            # 5. Institute upsert
            inst = db.execute(
                select(Institute).where(Institute.code == "CIT")
            ).scalar_one_or_none()
            if not inst:
                inst = Institute(
                    code="CIT",
                    name=dataset.institute,
                    timezone="Asia/Kolkata"
                )
                db.add(inst)
                db.flush()

            # 6. Discover & persist departments dynamically
            all_dept_codes: Set[str] = set()
            for f in dataset.faculty:
                all_dept_codes.add(f.department)
            for g in dataset.student_groups:
                all_dept_codes.add(g.department)
            for c in dataset.courses:
                all_dept_codes.add(c.department)
            for b in dataset.booking_requests:
                if b.department:
                    all_dept_codes.add(b.department)

            dept_map: Dict[str, uuid.UUID] = {}
            for code in sorted(all_dept_codes):
                dept = db.execute(
                    select(Department).where(
                        Department.institute_id == inst.id,
                        Department.code == code
                    )
                ).scalar_one_or_none()
                if not dept:
                    dept = Department(
                        institute_id=inst.id,
                        code=code,
                        name=f"Department of {code}"
                    )
                    db.add(dept)
                    db.flush()
                dept_map[code] = dept.id

            # 7. Dataset version
            max_v = db.execute(
                select(func.coalesce(func.max(DatasetVersion.version_number), 0)).where(
                    DatasetVersion.institute_id == inst.id,
                    DatasetVersion.external_dataset_id == dataset.dataset_id
                )
            ).scalar() or 0
            version_number = max_v + 1

            dsv = DatasetVersion(
                institute_id=inst.id,
                external_dataset_id=dataset.dataset_id,
                version_number=version_number,
                source_artifact_id=artifact.id,
                source_sha256=sha256,
                import_schema_version="1.0",
                application_version="1.0.0",
                status="IMPORTED",
                source_snapshot=raw_dict,
                imported_by=imported_by,
                imported_at=datetime.now(),
            )
            db.add(dsv)
            db.flush()
            job.dataset_version_id = dsv.id

            if fail_at_step == "before_policy":
                raise RuntimeError("Simulated failure before policy")

            # 8. Dataset Policy
            policy = DatasetPolicy(
                dataset_version_id=dsv.id,
                priority_order=dataset.priority_order,
                role_category_cap=dataset.role_category_cap,
                policy_snapshot={"source": "cit_public.json"}
            )
            db.add(policy)

            # 9. Calendar Version & Children
            cal = CalendarVersion(
                dataset_version_id=dsv.id,
                timezone="Asia/Kolkata",
                fest_week_label=dataset.calendar.fest_week
            )
            db.add(cal)
            db.flush()

            # Days
            for idx, d in enumerate(dataset.calendar.days, start=1):
                cday = CalendarDay(
                    calendar_version_id=cal.id,
                    day_code=d,
                    ordinal=idx,
                    is_teaching_day=True
                )
                db.add(cday)

            # Periods
            for p in dataset.calendar.periods:
                cper = CalendarPeriod(
                    calendar_version_id=cal.id,
                    period_number=p.id,
                    starts_at=p.start,
                    ends_at=p.end,
                    is_teaching_period=p.teaching
                )
                db.add(cper)
            db.flush()

            # Lunch Break
            lunch = CalendarBreak(
                calendar_version_id=cal.id,
                break_code="LUNCH",
                after_period=dataset.calendar.lunch.after_period,
                starts_at=dataset.calendar.lunch.start,
                ends_at=dataset.calendar.lunch.end
            )
            db.add(lunch)

            # Lab Start Periods & Event Only Periods
            for p_num in dataset.calendar.lab_start_periods:
                db.add(CalendarLabStartPeriod(calendar_version_id=cal.id, period_number=p_num))
            for p_num in dataset.calendar.event_only_periods:
                db.add(CalendarEventPeriod(calendar_version_id=cal.id, period_number=p_num))

            # Exam Week
            for idx, d in enumerate(dataset.calendar.exam_week.days, start=1):
                db.add(CalendarExamDay(calendar_version_id=cal.id, day_code=d, ordinal=idx))
            for es in dataset.calendar.exam_week.sessions:
                db.add(CalendarExamSession(
                    calendar_version_id=cal.id,
                    session_code=es.id,
                    starts_at=es.start,
                    ends_at=es.end
                ))
            db.flush()

            if fail_at_step == "before_rooms":
                raise RuntimeError("Simulated failure before rooms")

            # 10. Room Features
            all_features: Set[str] = set()
            for r in dataset.rooms:
                all_features.update(r.features)
            for b in dataset.booking_requests:
                all_features.update(b.needs)

            feat_map: Dict[str, uuid.UUID] = {}
            for f_code in sorted(all_features):
                rf = db.execute(select(RoomFeature).where(RoomFeature.code == f_code)).scalar_one_or_none()
                if not rf:
                    rf = RoomFeature(code=f_code, label=f_code.replace("_", " ").title())
                    db.add(rf)
                    db.flush()
                feat_map[f_code] = rf.id

            # 11. Rooms
            room_map: Dict[str, uuid.UUID] = {}
            for r in dataset.rooms:
                rm = Room(
                    dataset_version_id=dsv.id,
                    external_id=r.id,
                    name=r.name,
                    building=r.building,
                    room_type=r.type,
                    capacity=r.capacity,
                    accessible=r.accessible
                )
                db.add(rm)
                db.flush()
                room_map[r.id] = rm.id

                for f_code in r.features:
                    db.add(RoomFeatureAssignment(room_id=rm.id, feature_id=feat_map[f_code]))
                for u_code in r.allowed_uses:
                    db.add(RoomAllowedUse(room_id=rm.id, use_code=u_code))

            # Room Unavailability
            seen_room_unav: Set[Tuple[uuid.UUID, str, int]] = set()
            for ru in dataset.room_unavailability:
                r_id = room_map[ru.room_id]
                for p_num in ru.periods:
                    key = (r_id, ru.day, p_num)
                    if key not in seen_room_unav:
                        seen_room_unav.add(key)
                        db.add(RoomUnavailability(
                            room_id=r_id,
                            day_code=ru.day,
                            period_number=p_num,
                            reason=ru.reason
                        ))
            db.flush()

            # 12. Faculty
            fac_map: Dict[str, uuid.UUID] = {}
            for f in dataset.faculty:
                fac = Faculty(
                    dataset_version_id=dsv.id,
                    external_id=f.id,
                    name=f.name,
                    department_id=dept_map[f.department],
                    max_hours_per_day=Decimal(str(f.max_hours_per_day)),
                    needs_accessible=f.needs_accessible
                )
                db.add(fac)
                db.flush()
                fac_map[f.id] = fac.id

                # Primary department affiliation
                db.add(FacultyDepartment(
                    faculty_id=fac.id,
                    department_id=dept_map[f.department],
                    is_primary=True
                ))

                # Unavailability
                seen_fu: Set[Tuple[uuid.UUID, str, int]] = set()
                for fu in f.unavailable:
                    for p_num in fu.periods:
                        key = (fac.id, fu.day, p_num)
                        if key not in seen_fu:
                            seen_fu.add(key)
                            db.add(FacultyUnavailability(
                                faculty_id=fac.id,
                                day_code=fu.day,
                                period_number=p_num,
                                reason=fu.reason
                            ))

                # Preferences
                for pref in f.preferences:
                    pref_days = pref.days if pref.days else dataset.calendar.days
                    pref_periods = pref.periods if pref.periods else [p.id for p in dataset.calendar.periods if p.teaching]
                    for d_code in pref_days:
                        for p_num in pref_periods:
                            db.add(FacultyPreference(
                                faculty_id=fac.id,
                                preference_type=pref.type,
                                day_code=d_code,
                                period_number=p_num,
                                note=pref.note,
                                weight=Decimal("1.0")
                            ))
            db.flush()

            # 13. Student Groups
            grp_map: Dict[str, uuid.UUID] = {}
            for g in dataset.student_groups:
                sg = StudentGroup(
                    dataset_version_id=dsv.id,
                    external_id=g.id,
                    name=g.name,
                    year=g.year,
                    department_id=dept_map.get(g.department),
                    size=g.size,
                    needs_accessible=g.needs_accessible
                )
                db.add(sg)
                db.flush()
                grp_map[g.id] = sg.id

            # 14. Courses
            course_map: Dict[str, uuid.UUID] = {}
            for c in dataset.courses:
                crs = Course(
                    dataset_version_id=dsv.id,
                    external_id=c.id,
                    title=c.title,
                    department_id=dept_map.get(c.department),
                    year=c.year,
                    lecture_hours=Decimal(str(c.lecture_hours)),
                    tutorial_hours=Decimal(str(c.tutorial_hours)),
                    lab_blocks=Decimal(str(c.lab_blocks))
                )
                db.add(crs)
                db.flush()
                course_map[c.id] = crs.id

            if fail_at_step == "before_sessions":
                raise RuntimeError("Simulated failure before sessions")

            # 15. Teaching Sessions (Single Record per Session, Multiple Group Links for Joint Sessions)
            session_map: Dict[str, uuid.UUID] = {}
            for s in dataset.sessions:
                ts = TeachingSession(
                    dataset_version_id=dsv.id,
                    external_id=s.id,
                    course_id=course_map[s.course_id],
                    kind=s.kind,
                    faculty_id=fac_map[s.faculty_id],
                    size=s.size,
                    duration_periods=s.duration,
                    needs_accessible=s.needs_accessible,
                    basket_slot=s.basket_slot,
                    fixed_day=s.fixed_slot.day if s.fixed_slot else None,
                    fixed_start_period=s.fixed_slot.start_period if s.fixed_slot else None,
                    source_payload=s.model_dump(mode="json")
                )
                db.add(ts)
                db.flush()
                session_map[s.id] = ts.id

                # Instructor link
                db.add(TeachingSessionFaculty(
                    session_id=ts.id,
                    faculty_id=fac_map[s.faculty_id],
                    dataset_version_id=dsv.id,
                    assignment_role="instructor",
                    is_primary=True
                ))

                # Participating Groups (CRITICAL: Joint sessions have multiple SessionGroup links)
                for g_id in s.groups:
                    db.add(SessionGroup(
                        session_id=ts.id,
                        student_group_id=grp_map[g_id],
                        dataset_version_id=dsv.id
                    ))

                # Allowed room types
                for rt in s.room_types:
                    db.add(SessionAllowedRoomType(
                        session_id=ts.id,
                        room_type=rt
                    ))
            db.flush()

            # 16. Booking Requests & Cancellations
            booking_map: Dict[str, uuid.UUID] = {}
            for b in dataset.booking_requests:
                req_room_id = room_map.get(b.requested_room) if b.requested_room else None
                dept_id = dept_map.get(b.department) if b.department else None

                br = BookingRequest(
                    dataset_version_id=dsv.id,
                    external_id=b.id,
                    submitted_at=b.submitted_at,
                    requester_label=b.requester,
                    requester_role=b.role,
                    department_id=dept_id,
                    owner_department_id=dept_id,
                    requested_category=b.requested_category,
                    title=b.title,
                    attendance=b.attendance,
                    duration_periods=b.duration_periods,
                    requested_room_id=req_room_id,
                    series_id=b.series_id,
                    raw_text=b.raw_text,
                )
                db.add(br)
                db.flush()
                booking_map[b.id] = br.id

                # Windows
                for w in b.windows:
                    db.add(BookingWindow(
                        booking_request_id=br.id,
                        day_code=w.day,
                        from_period=w.from_period,
                        to_period=w.to_period
                    ))

                # Room types
                for rt in b.room_types:
                    db.add(BookingAllowedRoomType(
                        booking_request_id=br.id,
                        room_type=rt
                    ))

                # Required features
                for need in b.needs:
                    db.add(BookingRequiredFeature(
                        booking_request_id=br.id,
                        feature_code=need
                    ))

                # Mandatory groups
                for g_id in b.mandatory_for_groups:
                    db.add(BookingMandatoryGroup(
                        booking_request_id=br.id,
                        student_group_id=grp_map[g_id],
                        dataset_version_id=dsv.id
                    ))

            # Cancellations
            for c in dataset.cancellations:
                db.add(BookingCancellation(
                    booking_request_id=booking_map[c.request_id],
                    cancelled_at=c.cancelled_at,
                    cancelled_by_label=c.by,
                    note=c.note
                ))
            db.flush()

            # 17. Exams
            for e in dataset.exams:
                ex = ExamRecord(
                    dataset_version_id=dsv.id,
                    external_id=e.id,
                    size=e.size,
                    duration_hours=Decimal(str(e.duration_hours))
                )
                db.add(ex)
                db.flush()

                for c_id in e.course_ids:
                    db.add(ExamCourse(
                        exam_id=ex.id,
                        course_id=course_map[c_id]
                    ))

                for g_id in e.groups:
                    db.add(ExamGroup(
                        exam_id=ex.id,
                        student_group_id=grp_map[g_id]
                    ))
            db.flush()

            if fail_at_step == "before_commit":
                raise RuntimeError("Simulated failure before commit")

            # 18. Build reconciliation report & complete job
            report = cls.build_reconciliation_report(db, dsv.id)
            if report["reconciliation_status"] != "MATCH":
                raise ValueError(f"Post-import reconciliation mismatch: {report['mismatches']}")

            job.status = "SUCCEEDED"
            job.finished_at = datetime.now()
            job.report_json = report
            db.commit()

            return job, dsv, report

        except Exception as exc:
            db.rollback()
            # In a clean separate transaction, record the failed import job
            try:
                failed_job = ImportJob(
                    source_artifact_id=artifact.id if 'artifact' in locals() and artifact else None,
                    status="FAILED",
                    started_at=job.started_at if job else datetime.now(),
                    finished_at=datetime.now(),
                    report_json={
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "sha256": sha256
                    }
                )
                db.add(failed_job)
                db.commit()
            except Exception:
                db.rollback()
            raise

    @classmethod
    def build_reconciliation_report(cls, db: Session, dataset_version_id: uuid.UUID) -> dict[str, Any]:
        dsv = db.execute(select(DatasetVersion).where(DatasetVersion.id == dataset_version_id)).scalar_one()
        source = dsv.source_snapshot

        # Query database counts & external IDs
        rooms = db.execute(select(Room).where(Room.dataset_version_id == dataset_version_id)).scalars().all()
        faculty = db.execute(select(Faculty).where(Faculty.dataset_version_id == dataset_version_id)).scalars().all()
        groups = db.execute(select(StudentGroup).where(StudentGroup.dataset_version_id == dataset_version_id)).scalars().all()
        courses = db.execute(select(Course).where(Course.dataset_version_id == dataset_version_id)).scalars().all()
        sessions = db.execute(select(TeachingSession).where(TeachingSession.dataset_version_id == dataset_version_id)).scalars().all()
        bookings = db.execute(select(BookingRequest).where(BookingRequest.dataset_version_id == dataset_version_id)).scalars().all()
        cancellations = db.execute(
            select(BookingCancellation)
            .join(BookingRequest, BookingCancellation.booking_request_id == BookingRequest.id)
            .where(BookingRequest.dataset_version_id == dataset_version_id)
        ).scalars().all()
        exams = db.execute(select(ExamRecord).where(ExamRecord.dataset_version_id == dataset_version_id)).scalars().all()

        # Build comparison dictionaries
        entities = [
            ("rooms", [r.external_id for r in rooms], [r["id"] for r in source.get("rooms", [])]),
            ("faculty", [f.external_id for f in faculty], [f["id"] for f in source.get("faculty", [])]),
            ("student_groups", [g.external_id for g in groups], [g["id"] for g in source.get("student_groups", [])]),
            ("courses", [c.external_id for c in courses], [c["id"] for c in source.get("courses", [])]),
            ("sessions", [s.external_id for s in sessions], [s["id"] for s in source.get("sessions", [])]),
            ("booking_requests", [b.external_id for b in bookings], [b["id"] for b in source.get("booking_requests", [])]),
            ("exams", [e.external_id for e in exams], [e["id"] for e in source.get("exams", [])]),
        ]

        id_reconciliation = {}
        counts = {}
        mismatches = []

        for name, imported_ids, source_ids in entities:
            src_set = set(source_ids)
            imp_set = set(imported_ids)
            counts[name] = {
                "source": len(source_ids),
                "imported": len(imported_ids),
                "matched": len(src_set & imp_set)
            }
            diff_missing = sorted(src_set - imp_set)
            diff_extra = sorted(imp_set - src_set)
            id_reconciliation[name] = {
                "total_source": len(src_set),
                "total_imported": len(imp_set),
                "matched_count": len(src_set & imp_set),
                "missing": diff_missing,
                "unexpected": diff_extra
            }
            if diff_missing or diff_extra or len(source_ids) != len(imported_ids):
                mismatches.append(f"{name} mismatch: missing={diff_missing}, unexpected={diff_extra}")

        # Cancellations check
        counts["cancellations"] = {
            "source": len(source.get("cancellations", [])),
            "imported": len(cancellations),
            "matched": len(cancellations)
        }
        if len(source.get("cancellations", [])) != len(cancellations):
            mismatches.append(f"cancellations count mismatch: {len(source.get('cancellations', []))} != {len(cancellations)}")

        # Joint sessions verification
        joint_sessions_in_db = []
        for s in sessions:
            grp_links = db.execute(
                select(SessionGroup).where(SessionGroup.session_id == s.id)
            ).scalars().all()
            if len(grp_links) > 1:
                joint_sessions_in_db.append({
                    "session_external_id": s.external_id,
                    "linked_groups_count": len(grp_links)
                })

        source_joint_count = sum(1 for s in source.get("sessions", []) if len(s.get("groups", [])) > 1)
        if len(joint_sessions_in_db) != source_joint_count:
            mismatches.append(f"joint sessions count mismatch: db={len(joint_sessions_in_db)} vs src={source_joint_count}")

        # Calendar and policy verification
        cal = db.execute(select(CalendarVersion).where(CalendarVersion.dataset_version_id == dataset_version_id)).scalar_one_or_none()
        policy = db.execute(select(DatasetPolicy).where(DatasetPolicy.dataset_version_id == dataset_version_id)).scalar_one_or_none()

        policy_check = {
            "priority_order_match": policy.priority_order == source.get("priority_order") if policy else False,
            "role_category_cap_match": policy.role_category_cap == source.get("role_category_cap") if policy else False,
        }
        if not policy_check["priority_order_match"] or not policy_check["role_category_cap_match"]:
            mismatches.append("policy mismatch with canonical source")

        return {
            "dataset_version_id": str(dataset_version_id),
            "external_dataset_id": dsv.external_dataset_id,
            "version_number": dsv.version_number,
            "source_sha256": dsv.source_sha256,
            "reconciliation_status": "MATCH" if not mismatches else "MISMATCH",
            "mismatches": mismatches,
            "counts": counts,
            "id_reconciliation": id_reconciliation,
            "joint_sessions": {
                "source_count": source_joint_count,
                "imported_count": len(joint_sessions_in_db),
                "joint_sessions_sample": joint_sessions_in_db[:5]
            },
            "policy": policy_check,
            "reconciled_at": datetime.now().isoformat()
        }

class DatasetActivationService:
    @classmethod
    def activate_dataset(
        cls,
        db: Session,
        dataset_version_id: uuid.UUID,
        activated_by: uuid.UUID | None = None,
        reason: str | None = None
    ) -> DatasetActivation:
        # Fetch target version
        target = db.execute(
            select(DatasetVersion).where(DatasetVersion.id == dataset_version_id)
        ).scalar_one_or_none()
        if not target:
            raise ValueError(f"Dataset version {dataset_version_id} does not exist")

        # Serialized locking on institute row to avoid concurrent race conditions
        db.execute(
            select(Institute).where(Institute.id == target.institute_id).with_for_update()
        )

        # Check if already active
        current_active_act = db.execute(
            select(DatasetActivation).where(
                DatasetActivation.institute_id == target.institute_id,
                DatasetActivation.deactivated_at.is_(None)
            )
        ).scalar_one_or_none()

        if current_active_act and current_active_act.dataset_version_id == dataset_version_id:
            # Already active, idempotent return
            return current_active_act

        # Deactivate currently active version
        if current_active_act:
            current_active_act.deactivated_at = func.now()
            prev_dsv = db.execute(
                select(DatasetVersion).where(DatasetVersion.id == current_active_act.dataset_version_id)
            ).scalar_one_or_none()
            if prev_dsv:
                prev_dsv.status = "ARCHIVED"

        # Activate target
        target.status = "ACTIVE"
        target.activated_at = func.now()

        activation = DatasetActivation(
            institute_id=target.institute_id,
            dataset_version_id=target.id,
            activated_by=activated_by,
            activated_at=datetime.now(),
            reason=reason or "Activated via DatasetActivationService"
        )
        db.add(activation)
        db.commit()
        db.refresh(activation)
        return activation

    @classmethod
    def get_active_dataset(cls, db: Session, institute_id: uuid.UUID | None = None) -> DatasetVersion | None:
        query = select(DatasetVersion).where(DatasetVersion.status == "ACTIVE")
        if institute_id:
            query = query.where(DatasetVersion.institute_id == institute_id)
        return db.execute(query).scalar_one_or_none()
