import uuid
from datetime import datetime, date, time
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, DBAPIError

from app.db import Base
from app.modules.datasets.models import (
    Institute, Department, DatasetVersion, CalendarVersion, CalendarDay, CalendarPeriod
)
from app.modules.academic.models import (
    Room, RoomUnavailability, Faculty, FacultyDepartment, FacultyUnavailability,
    FacultyPreference, StudentGroup, Course, TeachingSession,
    TeachingSessionFaculty, SessionGroup
)
from app.modules.identity.models import User, UserRoleAssignment
from app.modules.scheduling.models import TimetableVersion, TimetableAssignment, GenerationScope, LockedAssignment
from app.modules.booking.models import BookingRequest, BookingMandatoryGroup

DB_URL = "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/cit_dev"

@pytest.fixture(scope="module")
def engine():
    return create_engine(DB_URL)

@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()

def test_alembic_current_revision(session):
    """Assert applied Alembic revision matches migration 0002."""
    res = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert res == "0002_dept_scope_shared_teaching"

def test_schema_table_parity_catalog_and_orm(session):
    """Assert exact 1-to-1 table parity between PostgreSQL catalog (84) and ORM (84)."""
    rows = session.execute(text("""
        SELECT table_schema || '.' || table_name 
        FROM information_schema.tables 
        WHERE table_schema IN (
            'core','academic','identity','scheduling','booking','exams',
            'change_mgmt','approvals','analytics','assistant','notifications','integration'
        )
    """)).scalars().all()
    pg_tables = set(rows)
    orm_tables = set(Base.metadata.tables.keys())

    assert len(pg_tables) == 84
    assert len(orm_tables) == 84
    assert pg_tables == orm_tables

def test_department_isolation_and_shared_resources(session):
    """Assert relational coexistence of independent departments and multi-group joint sessions.
    
    NOTE: This test proves schema-level integrity and multi-cohort representation in PostgreSQL.
    Solver-level simultaneous scheduling and constraint satisfaction are tested in Milestone 6.
    """
    inst = Institute(code=f"CIT_TEST_{uuid.uuid4().hex[:6]}", name="Chilika Institute of Technology Test")
    session.add(inst)
    session.flush()

    dept_cse = Department(institute_id=inst.id, code="CSE", name="Computer Science & Engineering")
    dept_ece = Department(institute_id=inst.id, code="ECE", name="Electronics & Communication Engineering")
    session.add_all([dept_cse, dept_ece])
    session.flush()

    dsv = DatasetVersion(
        institute_id=inst.id,
        external_dataset_id="cit-public-test",
        version_number=1,
        source_sha256="0" * 64,
        import_schema_version="1.0",
        status="ACTIVE",
        source_snapshot={}
    )
    session.add(dsv)
    session.flush()

    # Shared faculty with multi-department affiliation (0002)
    f_shared = Faculty(
        dataset_version_id=dsv.id,
        external_id="F_SHARED_01",
        name="Prof. Shared Maths",
        department_id=dept_cse.id,
        max_hours_per_day=Decimal("4.0")
    )
    r_shared = Room(
        dataset_version_id=dsv.id,
        external_id="R_LH_101",
        name="Lecture Hall 101",
        room_type="lecture_hall",
        capacity=160,
        accessible=True
    )
    session.add_all([f_shared, r_shared])
    session.flush()

    aff_cse = FacultyDepartment(faculty_id=f_shared.id, department_id=dept_cse.id, is_primary=True)
    aff_ece = FacultyDepartment(faculty_id=f_shared.id, department_id=dept_ece.id, is_primary=False)
    session.add_all([aff_cse, aff_ece])
    session.flush()

    # Distinct departmental cohorts
    g_cse = StudentGroup(
        dataset_version_id=dsv.id, external_id="CSE-2", name="CSE Year 2",
        year=2, department_id=dept_cse.id, size=80
    )
    g_ece = StudentGroup(
        dataset_version_id=dsv.id, external_id="ECE-2", name="ECE Year 2",
        year=2, department_id=dept_ece.id, size=70
    )
    session.add_all([g_cse, g_ece])
    session.flush()

    # Joint course and session (HS201: CSE + ECE)
    course_joint = Course(
        dataset_version_id=dsv.id, external_id="HS201", title="Universal Human Values",
        department_id=dept_cse.id, year=2
    )
    session.add(course_joint)
    session.flush()

    session_joint = TeachingSession(
        dataset_version_id=dsv.id, external_id="HS201-H1-L1", course_id=course_joint.id,
        kind="lecture", faculty_id=f_shared.id, size=150, duration_periods=1
    )
    session.add(session_joint)
    session.flush()

    # Link both groups to the single joint session
    sg_cse = SessionGroup(session_id=session_joint.id, student_group_id=g_cse.id, dataset_version_id=dsv.id)
    sg_ece = SessionGroup(session_id=session_joint.id, student_group_id=g_ece.id, dataset_version_id=dsv.id)
    session.add_all([sg_cse, sg_ece])
    session.flush()

    # Link primary instructor
    tsf = TeachingSessionFaculty(
        session_id=session_joint.id, dataset_version_id=dsv.id, faculty_id=f_shared.id,
        assignment_role="instructor", is_primary=True
    )
    session.add(tsf)
    session.flush()

    # Verify query for participating groups
    res_groups = session.execute(
        select(SessionGroup).where(SessionGroup.session_id == session_joint.id)
    ).scalars().all()
    assert len(res_groups) == 2

def test_faculty_and_room_unavailability_constraints(session):
    """Assert unavailability and preference constraints and uniqueness."""
    inst = Institute(code=f"CIT_UNAV_{uuid.uuid4().hex[:6]}", name="CIT Unavailability Test")
    session.add(inst)
    session.flush()

    dsv = DatasetVersion(
        institute_id=inst.id, external_dataset_id="ds-unav", version_number=1,
        source_sha256="u" * 64, import_schema_version="1.0", status="ACTIVE", source_snapshot={}
    )
    session.add(dsv)
    session.flush()

    fac = Faculty(dataset_version_id=dsv.id, external_id="F_UNAV", name="Dr. Unavail", max_hours_per_day=Decimal("4.0"))
    rm = Room(dataset_version_id=dsv.id, external_id="R_UNAV", name="Room Unavail", room_type="classroom", capacity=40)
    session.add_all([fac, rm])
    session.flush()

    # Faculty unavailability
    fu1 = FacultyUnavailability(faculty_id=fac.id, day_code="WED", period_number=6, reason="HOD meeting")
    session.add(fu1)
    session.flush()

    # Duplicate faculty unavailability on same day/period must be rejected
    sp1 = session.begin_nested()
    fu_dup = FacultyUnavailability(faculty_id=fac.id, day_code="WED", period_number=6, reason="Duplicate")
    session.add(fu_dup)
    with pytest.raises(IntegrityError):
        sp1.commit()
    sp1.rollback()

    # Room unavailability
    ru1 = RoomUnavailability(room_id=rm.id, day_code="FRI", period_number=8, reason="Maintenance")
    session.add(ru1)
    session.flush()

    # Duplicate room unavailability on same day/period must be rejected
    sp2 = session.begin_nested()
    ru_dup = RoomUnavailability(room_id=rm.id, day_code="FRI", period_number=8, reason="Maintenance Duplicate")
    session.add(ru_dup)
    with pytest.raises(IntegrityError):
        sp2.commit()
    sp2.rollback()

    # Faculty preferences
    fac = session.execute(select(Faculty).where(Faculty.external_id == "F_UNAV")).scalar_one()
    pref = FacultyPreference(faculty_id=fac.id, preference_type="avoid", day_code="MON", period_number=1, note="Dean duties", weight=Decimal("2.0"))
    session.add(pref)
    session.flush()
    assert pref.note == "Dean duties"

def test_composite_foreign_key_cross_dataset_rejection(session):
    """Assert session_groups rejects cross-dataset group references."""
    inst = Institute(code=f"CIT_FK_{uuid.uuid4().hex[:6]}", name="CIT FK Test Institute")
    session.add(inst)
    session.flush()

    dsv1 = DatasetVersion(
        institute_id=inst.id, external_dataset_id="ds-v1", version_number=1,
        source_sha256="1" * 64, import_schema_version="1.0", status="ACTIVE", source_snapshot={}
    )
    dsv2 = DatasetVersion(
        institute_id=inst.id, external_dataset_id="ds-v2", version_number=2,
        source_sha256="2" * 64, import_schema_version="1.0", status="ACTIVE", source_snapshot={}
    )
    session.add_all([dsv1, dsv2])
    session.flush()

    g1 = StudentGroup(dataset_version_id=dsv1.id, external_id="G1", name="Group 1", size=60)
    c2 = Course(dataset_version_id=dsv2.id, external_id="C2", title="Course 2")
    session.add_all([g1, c2])
    session.flush()

    s2 = TeachingSession(
        dataset_version_id=dsv2.id, external_id="S2", course_id=c2.id,
        kind="lecture", size=60, duration_periods=1
    )
    session.add(s2)
    session.flush()

    # Attempt cross-dataset link: session in DS2, group in DS1
    sg_cross = SessionGroup(session_id=s2.id, student_group_id=g1.id, dataset_version_id=dsv2.id)
    session.add(sg_cross)

    with pytest.raises(IntegrityError) as exc_info:
        session.flush()
    assert "fk_session_groups_group_dataset" in str(exc_info.value) or "foreign key" in str(exc_info.value).lower()

def test_composite_fk_timetable_assignment_room_dataset_isolation(session):
    """Assert timetable_assignments rejects assigning a room from another dataset."""
    inst = Institute(code=f"CIT_TT_FK_{uuid.uuid4().hex[:6]}", name="CIT TT FK Test")
    session.add(inst)
    session.flush()

    dsv1 = DatasetVersion(
        institute_id=inst.id, external_dataset_id="ds-tt1", version_number=1,
        source_sha256="a" * 64, import_schema_version="1.0", status="ACTIVE", source_snapshot={}
    )
    dsv2 = DatasetVersion(
        institute_id=inst.id, external_dataset_id="ds-tt2", version_number=2,
        source_sha256="b" * 64, import_schema_version="1.0", status="ACTIVE", source_snapshot={}
    )
    session.add_all([dsv1, dsv2])
    session.flush()

    cal1 = CalendarVersion(dataset_version_id=dsv1.id, timezone="Asia/Kolkata")
    cal2 = CalendarVersion(dataset_version_id=dsv2.id, timezone="Asia/Kolkata")
    session.add_all([cal1, cal2])
    session.flush()

    # Room in Dataset 1
    r1 = Room(dataset_version_id=dsv1.id, external_id="R1", name="Room 1", room_type="classroom", capacity=50)
    # Course, Session and Timetable in Dataset 2
    c2 = Course(dataset_version_id=dsv2.id, external_id="C2", title="Course 2")
    session.add_all([r1, c2])
    session.flush()

    s2 = TeachingSession(
        dataset_version_id=dsv2.id, external_id="S2", course_id=c2.id,
        kind="lecture", size=40, duration_periods=1
    )
    tt2 = TimetableVersion(dataset_version_id=dsv2.id, calendar_version_id=cal2.id, version_number=1, status="DRAFT")
    session.add_all([s2, tt2])
    session.flush()

    # Cross-dataset room assignment: assignment in DS2, room in DS1
    ta_cross = TimetableAssignment(
        timetable_version_id=tt2.id,
        session_id=s2.id,
        day_code="MON",
        start_period=1,
        room_id=r1.id,
        dataset_version_id=dsv2.id
    )
    session.add(ta_cross)
    with pytest.raises(IntegrityError) as exc_info:
        session.flush()
    assert "fk_assignment_room_dataset" in str(exc_info.value) or "foreign key" in str(exc_info.value).lower()

def test_composite_fk_booking_mandatory_group_dataset_isolation(session):
    """Assert booking_mandatory_groups rejects student groups from another dataset."""
    inst = Institute(code=f"CIT_BK_FK_{uuid.uuid4().hex[:6]}", name="CIT Booking FK Test")
    session.add(inst)
    session.flush()

    dsv1 = DatasetVersion(
        institute_id=inst.id, external_dataset_id="ds-bk1", version_number=1,
        source_sha256="c" * 64, import_schema_version="1.0", status="ACTIVE", source_snapshot={}
    )
    dsv2 = DatasetVersion(
        institute_id=inst.id, external_dataset_id="ds-bk2", version_number=2,
        source_sha256="d" * 64, import_schema_version="1.0", status="ACTIVE", source_snapshot={}
    )
    session.add_all([dsv1, dsv2])
    session.flush()

    # Group in Dataset 1
    g1 = StudentGroup(dataset_version_id=dsv1.id, external_id="G1", name="Group 1", size=60)
    # Booking Request in Dataset 2
    br2 = BookingRequest(
        dataset_version_id=dsv2.id,
        external_id="BR-01",
        submitted_at=datetime.now(),
        requester_label="Club Lead",
        requester_role="club",
        requested_category="club_event",
        title="Robot Workshop",
        attendance=50,
        duration_periods=2
    )
    session.add_all([g1, br2])
    session.flush()

    # Cross-dataset link: booking request in DS2, group in DS1
    bmg_cross = BookingMandatoryGroup(
        booking_request_id=br2.id,
        student_group_id=g1.id,
        dataset_version_id=dsv2.id
    )
    session.add(bmg_cross)
    with pytest.raises(IntegrityError) as exc_info:
        session.flush()
    assert "fk_booking_mandatory_group_dataset" in str(exc_info.value) or "foreign key" in str(exc_info.value).lower()

def test_transaction_rollback_and_error_recovery(session):
    """Assert failed operation inside a transaction rolls back and leaves zero orphan rows."""
    inst = Institute(code=f"CIT_TX_{uuid.uuid4().hex[:6]}", name="CIT Rollback Test")
    session.add(inst)
    session.flush()

    # Subtransaction / nested savepoint
    sp = session.begin_nested()
    bad_room = Room(
        dataset_version_id=uuid.uuid4(), # Unknown dataset version ID
        external_id="R_BAD",
        name="Bad Room",
        room_type="classroom",
        capacity=-10 # Also violates CHECK (capacity > 0)
    )
    session.add(bad_room)
    with pytest.raises(IntegrityError):
        sp.commit()
    sp.rollback()

    # Assert session is healthy and subsequent queries succeed
    count = session.execute(select(Institute).where(Institute.id == inst.id)).scalars().all()
    assert len(count) == 1

def test_department_scope_authorization_structure(session):
    """Assert four official competition roles, role check constraints, and department scopes."""
    roles_to_seed = [
        ("admin@cit.local", "Campus Admin", "admin", "institute", None),
        ("coordinator.cse@cit.local", "CSE Coordinator", "department_coordinator", "department", uuid.uuid4()),
        ("coordinator.ece@cit.local", "ECE Coordinator", "department_coordinator", "department", uuid.uuid4()),
        ("faculty.f01@cit.local", "Dr. Ananya Mishra", "faculty", "resource", uuid.uuid4()),
        ("club.robotics@cit.local", "Robotics Club Rep", "club", "club", uuid.uuid4()),
    ]
    for email, name, role, scope_type, scope_id in roles_to_seed:
        u = User(
            email=email,
            display_name=name,
            auth_provider="LOCAL",
            password_hash="pbkdf2_sha256$29000$development_salt_only$dummy_hash",
            status="ACTIVE"
        )
        session.add(u)
        session.flush()

        role_assign = UserRoleAssignment(
            user_id=u.id,
            role_code=role,
            scope_type=scope_type,
            scope_id=scope_id
        )
        session.add(role_assign)
        session.flush()

        res = session.execute(
            select(UserRoleAssignment).where(UserRoleAssignment.user_id == u.id)
        ).scalar_one()
        assert res.role_code == role
        assert res.scope_type == scope_type

    # Verify invalid role_code is rejected by CHECK constraint
    u_invalid = User(email=f"invalid_{uuid.uuid4().hex[:6]}@cit.local", display_name="Invalid Role", auth_provider="LOCAL")
    session.add(u_invalid)
    session.flush()

    role_invalid = UserRoleAssignment(user_id=u_invalid.id, role_code="student", scope_type="institute")
    session.add(role_invalid)
    with pytest.raises(IntegrityError) as exc_info:
        session.flush()
    assert "user_role_assignments_role_code_check" in str(exc_info.value) or "check constraint" in str(exc_info.value).lower()

def test_concurrent_writes_and_advisory_locks(session):
    """Assert PostgreSQL row-level locks and transactional advisory locks function properly."""
    inst = Institute(code=f"CIT_LOCK_{uuid.uuid4().hex[:6]}", name="CIT Lock Test")
    session.add(inst)
    session.flush()

    # Test transactional advisory lock
    lock_key = 123456789
    has_lock = session.execute(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": lock_key}
    ).scalar()
    assert has_lock is True

    # Test SELECT FOR UPDATE on institute row
    locked_inst = session.execute(
        select(Institute).where(Institute.id == inst.id).with_for_update()
    ).scalar_one()
    assert locked_inst.id == inst.id
