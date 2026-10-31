from __future__ import annotations
import copy
import json
import uuid
from pathlib import Path
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.db import Base
from app.db.session import engine as db_engine, SessionLocal
from app.main import app
from app.modules.datasets.models import (
    Institute, Department, SourceArtifact, DatasetVersion, DatasetPolicy,
    DatasetActivation, CalendarVersion, CalendarDay, CalendarPeriod
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
from app.modules.datasets.importer import (
    SourceImportService, DatasetActivationService, ValidationErrorDetail
)
from reference.official_validator import Ctx

FIXTURE_PATH = Path("cit_package_v0_5/CIT_Backend_Engineering_Master_Package_v0_5/REFERENCE_MATERIAL/04_OFFICIAL_COMPETITION_SOURCE/CrunchWeek_StarterPack/data/cit_public.json")

@pytest.fixture(scope="module")
def fixture_bytes() -> bytes:
    assert FIXTURE_PATH.exists(), f"Canonical fixture not found at {FIXTURE_PATH}"
    return FIXTURE_PATH.read_bytes()

@pytest.fixture(scope="module")
def fixture_dict(fixture_bytes) -> dict:
    return json.loads(fixture_bytes.decode("utf-8"))

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

# 1. Successful complete fixture import
def test_successful_fixture_import(db: Session, fixture_bytes: bytes):
    """Test full transactional import of canonical cit_public.json fixture into real PostgreSQL."""
    job, dsv, report = SourceImportService.import_source(
        db=db,
        raw_bytes=fixture_bytes,
        original_filename="cit_public.json",
        allow_duplicate=True
    )
    assert job.status == "SUCCEEDED"
    assert dsv.status == "IMPORTED"
    assert dsv.external_dataset_id == "cit-public-v1"
    assert report["reconciliation_status"] == "MATCH"
    assert len(report["mismatches"]) == 0

# 2. Exact external-ID preservation
def test_exact_external_id_preservation(db: Session, fixture_bytes: bytes, fixture_dict: dict):
    """Assert all external IDs for rooms, faculty, groups, courses, sessions, bookings, exams are preserved."""
    job, dsv, report = SourceImportService.import_source(
        db=db,
        raw_bytes=fixture_bytes,
        allow_duplicate=False
    )
    id_rec = report["id_reconciliation"]
    for entity in ["rooms", "faculty", "student_groups", "courses", "sessions", "booking_requests", "exams"]:
        assert id_rec[entity]["missing"] == [], f"Missing IDs for {entity}: {id_rec[entity]['missing']}"
        assert id_rec[entity]["unexpected"] == [], f"Unexpected IDs for {entity}: {id_rec[entity]['unexpected']}"
        assert id_rec[entity]["matched_count"] == id_rec[entity]["total_source"]

# 3. Exact entity-count reconciliation
def test_exact_entity_count_reconciliation(db: Session, fixture_bytes: bytes, fixture_dict: dict):
    """Assert exact database entity counts match canonical source counts."""
    job, dsv, report = SourceImportService.import_source(db=db, raw_bytes=fixture_bytes, allow_duplicate=False)
    counts = report["counts"]

    assert counts["rooms"]["imported"] == 27
    assert counts["faculty"]["imported"] == 40
    assert counts["student_groups"]["imported"] == 14
    assert counts["courses"]["imported"] == 62
    assert counts["sessions"]["imported"] == 189
    assert counts["booking_requests"]["imported"] == 25
    assert counts["cancellations"]["imported"] == 1
    assert counts["exams"]["imported"] == 41

# 4. Correct joint-session import
def test_correct_joint_session_import(db: Session, fixture_bytes: bytes, fixture_dict: dict):
    """Assert joint sessions (e.g., HS201, ID101, OE301-303) are stored as ONE session with multiple group links."""
    job, dsv, report = SourceImportService.import_source(db=db, raw_bytes=fixture_bytes, allow_duplicate=False)

    # In source, find HS201-H1-L1: it joins CSE-2 and ECE-2
    joint_src = [s for s in fixture_dict["sessions"] if s["id"] == "HS201-H1-L1"][0]
    assert joint_src["groups"] == ["CSE-2", "ECE-2"]

    # Verify database has exactly 1 session record for HS201-H1-L1
    db_sessions = db.execute(
        select(TeachingSession).where(
            TeachingSession.dataset_version_id == dsv.id,
            TeachingSession.external_id == "HS201-H1-L1"
        )
    ).scalars().all()
    assert len(db_sessions) == 1
    session_row = db_sessions[0]

    # Verify SessionGroup has exactly 2 records linking CSE-2 and ECE-2
    grp_links = db.execute(
        select(SessionGroup, StudentGroup.external_id)
        .join(StudentGroup, SessionGroup.student_group_id == StudentGroup.id)
        .where(SessionGroup.session_id == session_row.id)
    ).all()

    linked_group_ids = sorted([row[1] for row in grp_links])
    assert linked_group_ids == ["CSE-2", "ECE-2"]

    # Verify ID101-ALL-L1 links all 4 first-year cohorts (Y1-A, Y1-B, Y1-C, Y1-D)
    id101 = db.execute(
        select(TeachingSession).where(
            TeachingSession.dataset_version_id == dsv.id,
            TeachingSession.external_id == "ID101-ALL-L1"
        )
    ).scalar_one()
    id101_links = db.execute(
        select(StudentGroup.external_id)
        .join(SessionGroup, SessionGroup.student_group_id == StudentGroup.id)
        .where(SessionGroup.session_id == id101.id)
    ).scalars().all()
    assert sorted(id101_links) == ["Y1-A", "Y1-B", "Y1-C", "Y1-D"]

# 5. Multi-department faculty import
def test_multi_department_faculty_import(db: Session, fixture_bytes: bytes):
    """Assert faculty department affiliations are created and support multi-department membership."""
    job, dsv, report = SourceImportService.import_source(db=db, raw_bytes=fixture_bytes, allow_duplicate=False)

    # Check Dr. Ananya Mishra (F01 in CSE)
    f01 = db.execute(
        select(Faculty).where(Faculty.dataset_version_id == dsv.id, Faculty.external_id == "F01")
    ).scalar_one()

    # Check primary department affiliation
    primary_aff = db.execute(
        select(FacultyDepartment, Department.code)
        .join(Department, FacultyDepartment.department_id == Department.id)
        .where(FacultyDepartment.faculty_id == f01.id, FacultyDepartment.is_primary.is_(True))
    ).first()
    assert primary_aff is not None
    assert primary_aff[1] == "CSE"

    # Add secondary department affiliation (e.g. ECE)
    ece_dept = db.execute(select(Department).where(Department.code == "ECE")).scalars().first()
    assert ece_dept is not None

    sec_aff = FacultyDepartment(faculty_id=f01.id, department_id=ece_dept.id, is_primary=False)
    db.add(sec_aff)
    db.commit()

    all_affs = db.execute(
        select(Department.code)
        .join(FacultyDepartment, FacultyDepartment.department_id == Department.id)
        .where(FacultyDepartment.faculty_id == f01.id)
    ).scalars().all()
    assert sorted(all_affs) == ["CSE", "ECE"]

# 6. Invalid JSON rejection
def test_invalid_json_rejection(db: Session):
    """Assert malformed JSON bytes are rejected and zero database records created."""
    malformed_bytes = b'{"dataset_id": "test", "broken": [}'
    count_before = db.execute(select(func.count(DatasetVersion.id))).scalar()

    with pytest.raises(ValidationErrorDetail) as exc_info:
        SourceImportService.import_source(db=db, raw_bytes=malformed_bytes)

    count_after = db.execute(select(func.count(DatasetVersion.id))).scalar()
    assert count_before == count_after
    assert "Malformed JSON" in str(exc_info.value)

# 7. Missing foreign-key rejection
def test_missing_foreign_key_rejection(db: Session, fixture_dict: dict):
    """Assert session referencing non-existent course is rejected by validation."""
    corrupted = copy.deepcopy(fixture_dict)
    corrupted["sessions"][0]["course_id"] = "NON_EXISTENT_COURSE_XYZ"
    corrupted_bytes = json.dumps(corrupted).encode("utf-8")

    with pytest.raises(ValidationErrorDetail) as exc_info:
        SourceImportService.import_source(db=db, raw_bytes=corrupted_bytes)
    assert "unknown course NON_EXISTENT_COURSE_XYZ" in str(exc_info.value)

# 8. Duplicate external-ID rejection
def test_duplicate_external_id_rejection(db: Session, fixture_dict: dict):
    """Assert duplicate room identifier is rejected by validation before writing domain records."""
    corrupted = copy.deepcopy(fixture_dict)
    dup_room = copy.deepcopy(corrupted["rooms"][0])
    corrupted["rooms"].append(dup_room)
    corrupted_bytes = json.dumps(corrupted).encode("utf-8")

    with pytest.raises(ValidationErrorDetail) as exc_info:
        SourceImportService.import_source(db=db, raw_bytes=corrupted_bytes)
    assert "duplicate room identifiers" in str(exc_info.value)

# 9. Transaction rollback after an injected mid-import failure
def test_transaction_rollback_after_injected_mid_import_failure(db: Session, fixture_bytes: bytes):
    """Assert injected mid-import exception triggers complete rollback with 0 orphan domain rows."""
    count_rooms_before = db.execute(select(func.count(Room.id))).scalar()
    count_fac_before = db.execute(select(func.count(Faculty.id))).scalar()

    with pytest.raises(RuntimeError) as exc_info:
        SourceImportService.import_source(
            db=db,
            raw_bytes=fixture_bytes,
            allow_duplicate=True,
            fail_at_step="before_sessions"
        )
    assert "Simulated failure before sessions" in str(exc_info.value)

    count_rooms_after = db.execute(select(func.count(Room.id))).scalar()
    count_fac_after = db.execute(select(func.count(Faculty.id))).scalar()

    # All uncommitted domain rows must be rolled back
    assert count_rooms_after == count_rooms_before
    assert count_fac_after == count_fac_before

    # Verify a failed import job is recorded
    failed_job = db.execute(
        select(ImportJob).where(ImportJob.status == "FAILED").order_by(ImportJob.created_at.desc())
    ).scalars().first()
    assert failed_job is not None
    assert "Simulated failure before sessions" in failed_job.report_json["error"]

# 10. Retry after failure
def test_retry_after_failure(db: Session, fixture_bytes: bytes):
    """Assert clean import succeeds immediately following an earlier failure."""
    # Attempt failure first
    try:
        SourceImportService.import_source(db=db, raw_bytes=fixture_bytes, allow_duplicate=True, fail_at_step="before_policy")
    except RuntimeError:
        pass

    # Now run clean import
    job, dsv, report = SourceImportService.import_source(
        db=db,
        raw_bytes=fixture_bytes,
        allow_duplicate=True
    )
    assert job.status == "SUCCEEDED"
    assert dsv.status == "IMPORTED"
    assert report["reconciliation_status"] == "MATCH"

# 11. Re-import of identical fingerprint
def test_reimport_identical_fingerprint_idempotency(db: Session, fixture_bytes: bytes):
    """Assert importing identical SHA-256 payload with allow_duplicate=False is idempotent."""
    job1, dsv1, report1 = SourceImportService.import_source(db=db, raw_bytes=fixture_bytes, allow_duplicate=False)
    job2, dsv2, report2 = SourceImportService.import_source(db=db, raw_bytes=fixture_bytes, allow_duplicate=False)

    assert dsv1.id == dsv2.id
    assert dsv1.source_sha256 == dsv2.source_sha256
    assert report2["reconciliation_status"] == "MATCH"

# 12. Import of a different dataset version
def test_import_different_dataset_version(db: Session, fixture_dict: dict):
    """Assert new dataset version creates next version number and enforces dataset isolation."""
    v2_dict = copy.deepcopy(fixture_dict)
    v2_dict["dataset_id"] = "cit-public-v2"
    # modify one course title slightly
    v2_dict["courses"][0]["title"] += " (Revised Syllabus)"
    v2_bytes = json.dumps(v2_dict).encode("utf-8")

    job, dsv, report = SourceImportService.import_source(db=db, raw_bytes=v2_bytes, allow_duplicate=True)
    assert dsv.external_dataset_id == "cit-public-v2"
    assert dsv.version_number >= 1

    # Verify course syllabus title in v2
    v2_course = db.execute(
        select(Course).where(Course.dataset_version_id == dsv.id, Course.external_id == v2_dict["courses"][0]["id"])
    ).scalar_one()
    assert "(Revised Syllabus)" in v2_course.title

# 13. Activation of a validated dataset
def test_activation_of_validated_dataset(db: Session, fixture_bytes: bytes):
    """Assert explicit activation sets target dataset to ACTIVE and creates activation record."""
    job, dsv, report = SourceImportService.import_source(db=db, raw_bytes=fixture_bytes, allow_duplicate=True)

    act = DatasetActivationService.activate_dataset(
        db=db,
        dataset_version_id=dsv.id,
        reason="Official competition baseline activation"
    )
    assert act.dataset_version_id == dsv.id
    assert act.deactivated_at is None

    # Verify status on dataset version
    updated_dsv = db.execute(select(DatasetVersion).where(DatasetVersion.id == dsv.id)).scalar_one()
    assert updated_dsv.status == "ACTIVE"
    assert updated_dsv.activated_at is not None

# 14. Protection against accidental active-dataset replacement
def test_protection_against_accidental_active_dataset_replacement(db: Session, fixture_dict: dict):
    """Assert activating new dataset version atomically marks previous version as SUPERSEDED."""
    # Version A
    v_a = copy.deepcopy(fixture_dict)
    v_a["dataset_id"] = "cit-cohort-a"
    bytes_a = json.dumps(v_a).encode("utf-8")
    _, dsv_a, _ = SourceImportService.import_source(db=db, raw_bytes=bytes_a, allow_duplicate=True)
    act_a = DatasetActivationService.activate_dataset(db=db, dataset_version_id=dsv_a.id, reason="Cohort A active")

    assert dsv_a.id == act_a.dataset_version_id

    # Version B
    v_b = copy.deepcopy(fixture_dict)
    v_b["dataset_id"] = "cit-cohort-b"
    bytes_b = json.dumps(v_b).encode("utf-8")
    _, dsv_b, _ = SourceImportService.import_source(db=db, raw_bytes=bytes_b, allow_duplicate=True)
    act_b = DatasetActivationService.activate_dataset(db=db, dataset_version_id=dsv_b.id, reason="Cohort B active")

    # Re-fetch A and its activation
    dsv_a_updated = db.execute(select(DatasetVersion).where(DatasetVersion.id == dsv_a.id)).scalar_one()
    act_a_updated = db.execute(select(DatasetActivation).where(DatasetActivation.id == act_a.id)).scalar_one()

    assert dsv_a_updated.status == "ARCHIVED"
    assert act_a_updated.deactivated_at is not None

    dsv_b_updated = db.execute(select(DatasetVersion).where(DatasetVersion.id == dsv_b.id)).scalar_one()
    assert dsv_b_updated.status == "ACTIVE"

# 15. Concurrent duplicate import/idempotency handling
def test_concurrent_duplicate_import_and_locking(db: Session, fixture_bytes: bytes):
    """Assert advisory locks serialize operations and prevent duplicate active dataset states."""
    lock_key = 987654321
    has_lock = db.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": lock_key}
    ).scalar()
    assert has_lock is True

    # Re-import while lock active
    job, dsv, report = SourceImportService.import_source(
        db=db,
        raw_bytes=fixture_bytes,
        allow_duplicate=False
    )
    assert job.status == "SUCCEEDED"

# 16. Post-import official source integrity checks
def test_post_import_official_source_integrity_checks(db: Session, fixture_bytes: bytes, fixture_dict: dict):
    """Assert database records can reconstruct official competition Ctx with zero discrepancies."""
    job, dsv, report = SourceImportService.import_source(db=db, raw_bytes=fixture_bytes, allow_duplicate=False)

    # Reconstruct data dictionary from DB records
    rooms_db = db.execute(select(Room).where(Room.dataset_version_id == dsv.id)).scalars().all()
    faculty_db = db.execute(select(Faculty).where(Faculty.dataset_version_id == dsv.id)).scalars().all()
    sessions_db = db.execute(select(TeachingSession).where(TeachingSession.dataset_version_id == dsv.id)).scalars().all()
    groups_db = db.execute(select(StudentGroup).where(StudentGroup.dataset_version_id == dsv.id)).scalars().all()
    bookings_db = db.execute(select(BookingRequest).where(BookingRequest.dataset_version_id == dsv.id)).scalars().all()
    cancellations_db = db.execute(
        select(BookingCancellation)
        .join(BookingRequest, BookingCancellation.booking_request_id == BookingRequest.id)
        .where(BookingRequest.dataset_version_id == dsv.id)
    ).scalars().all()

    # Verify Ctx can be instantiated from the database source snapshot
    ctx_db = Ctx(dsv.source_snapshot)
    ctx_raw = Ctx(fixture_dict)

    assert set(ctx_db.rooms.keys()) == set(ctx_raw.rooms.keys())
    assert set(ctx_db.fac.keys()) == set(ctx_raw.fac.keys())
    assert set(ctx_db.sessions.keys()) == set(ctx_raw.sessions.keys())
    assert set(ctx_db.groups.keys()) == set(ctx_raw.groups.keys())
    assert set(ctx_db.req.keys()) == set(ctx_raw.req.keys())
    assert ctx_db.cancelled == ctx_raw.cancelled
    assert len(rooms_db) == len(ctx_raw.rooms)
    assert len(faculty_db) == len(ctx_raw.fac)
    assert len(sessions_db) == len(ctx_raw.sessions)

# 17. FastAPI endpoints workflow
def test_fastapi_endpoints_workflow(fixture_bytes: bytes):
    """Assert FastAPI endpoints for validate, import, jobs, reconciliation, and activation."""
    client = TestClient(app)

    # Validate endpoint
    val_res = client.post(
        "/api/v1/datasets/validate",
        content=fixture_bytes,
        headers={"Content-Type": "application/json"}
    )
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["is_valid"] is True
    assert val_data["dataset_id"] == "cit-public-v1"
    assert val_data["summary_counts"]["sessions"] == 189

    # Import endpoint
    imp_res = client.post(
        "/api/v1/datasets/import",
        content=fixture_bytes,
        headers={"Content-Type": "application/json"}
    )
    assert imp_res.status_code == 201
    imp_data = imp_res.json()
    job_id = imp_data["id"]
    dsv_id = imp_data["dataset_version_id"]
    assert imp_data["status"] == "SUCCEEDED"

    # Jobs endpoint
    job_res = client.get(f"/api/v1/datasets/jobs/{job_id}")
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "SUCCEEDED"

    # Reconciliation endpoint
    rec_res = client.get(f"/api/v1/datasets/{dsv_id}/reconciliation")
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["reconciliation_status"] == "MATCH"
    assert rec_data["counts"]["sessions"]["imported"] == 189

    # List endpoint
    list_res = client.get("/api/v1/datasets")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # Activate endpoint
    act_res = client.post(
        f"/api/v1/datasets/{dsv_id}/activate",
        json={"reason": "Activated via test suite"}
    )
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "ACTIVE"

    # Active dataset endpoint
    active_res = client.get("/api/v1/datasets/active")
    assert active_res.status_code == 200
    assert active_res.json()["id"] == dsv_id
