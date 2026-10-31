from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.db.session import engine as db_engine
from app.main import app
from app.core.config import JWT_SECRET, JWT_ALGORITHM
from app.core.security import create_access_token, decode_access_token, hash_password
from app.modules.identity.models import User, UserRoleAssignment, AuthSession, AuditEvent
from app.modules.datasets.models import Department, DatasetVersion
from app.modules.academic.models import Course, TeachingSession, StudentGroup, SessionGroup, Faculty, FacultyDepartment
from app.modules.booking.models import BookingRequest
from app.modules.identity.permissions import (
    ROLE_ADMIN,
    ROLE_DEPARTMENT_COORDINATOR,
    ROLE_FACULTY,
    ROLE_CLUB,
    SCOPE_INSTITUTE,
    SCOPE_DEPARTMENT,
    SCOPE_RESOURCE,
    SCOPE_CLUB,
    evaluate_session_modification_authority,
    evaluate_faculty_access,
    evaluate_booking_request_authority,
)
from app.modules.identity.service import (
    AuthService,
    UserService,
    AuthError,
    AccountLockedError,
    TokenReuseSecurityError,
)
from app.modules.identity.seeds import seed_dev_identities, DEV_TEST_PASSWORDS

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture
def db():
    with Session(db_engine) as session:
        yield session
        session.rollback()

@pytest.fixture(scope="module")
def seeded_users():
    with Session(db_engine) as session:
        # Clear failed login events to prevent inter-run lockout pollution on seeded accounts
        session.execute(text("DELETE FROM core.audit_events WHERE action IN ('AUTH_LOGIN_FAILED', 'AUTH_ACCOUNT_LOCKED')"))
        session.commit()
        users = seed_dev_identities(session)
        return users

def test_seed_dev_identities_structure(db, seeded_users):
    """Verifies that the seeded test identities strictly use the 4 official roles and appropriate scopes."""
    for key, data in seeded_users.items():
        user = db.execute(select(User).where(User.email == data["email"])).scalar_one_or_none()
        assert user is not None
        assert user.status == "ACTIVE"

        assignments = db.execute(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.revoked_at.is_(None)
            )
        ).scalars().all()
        assert len(assignments) >= 1

        for a in assignments:
            assert a.role_code in ("admin", "department_coordinator", "faculty", "club")
            assert a.scope_type in ("institute", "department", "faculty", "resource", "club")

def test_login_success_and_token_structure(client, seeded_users):
    """Verifies login endpoint returns JWT access token, opaque refresh token, and user summary."""
    admin_data = seeded_users["admin"]
    resp = client.post("/api/v1/auth/login", json={
        "email": admin_data["email"],
        "password": admin_data["password"]
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert data["user"]["email"] == admin_data["email"]
    assert "admin" in data["user"]["roles"]

    # Decode and inspect access token claims
    payload = decode_access_token(data["access_token"])
    assert payload["sub"] == str(admin_data["user_id"])
    assert payload["email"] == admin_data["email"]
    assert "admin" in payload["roles"]
    assert payload["type"] == "access"

def test_login_invalid_password_returns_401(client, db):
    """Verifies login failure with incorrect password returns 401 on an isolated account."""
    temp_email = f"wrong_pwd_{uuid.uuid4().hex[:8]}@cit.test"
    UserService.create_user(db, temp_email, "Wrong Password User", "RealPassword123!")
    resp = client.post("/api/v1/auth/login", json={
        "email": temp_email,
        "password": "WrongPassword2026!"
    })
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]

def test_account_lockout_after_consecutive_failed_logins(client, db):
    """Verifies that 5 consecutive failed logins trigger account lockout and HTTP 429."""
    test_email = f"lockout_test_{uuid.uuid4().hex[:8]}@cit.test"
    user = UserService.create_user(db, test_email, "Lockout Target", "CorrectPassword123!")

    # Attempt 5 incorrect logins
    for i in range(5):
        resp = client.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": f"WrongAttempt_{i}"
        })
        if i < 4:
            assert resp.status_code == 401
        else:
            # The 5th failure triggers lockout
            assert resp.status_code in (401, 429)

    # 6th attempt must be rejected immediately with 429 Too Many Requests
    locked_resp = client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": "CorrectPassword123!"
    })
    assert locked_resp.status_code == 429
    assert "locked" in locked_resp.json()["detail"].lower()
    assert "Retry-After" in locked_resp.headers

def test_auth_me_endpoint_with_bearer_token(client, seeded_users):
    """Verifies /api/v1/auth/me returns the caller's profile and active roles."""
    user_data = seeded_users["cse_coord"]
    login_resp = client.post("/api/v1/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    token = login_resp.json()["access_token"]

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me = resp.json()
    assert me["email"] == user_data["email"]
    assert "department_coordinator" in me["roles"]
    assert len(me["scopes"]) >= 1

def test_expired_access_token_rejection(client, seeded_users):
    """Verifies that an expired access token is rejected with 401 Unauthorized."""
    admin_id = str(seeded_users["admin"]["user_id"])
    expired_token = create_access_token(
        {"sub": admin_id, "email": "admin@cit.test", "roles": ["admin"], "scopes": []},
        expires_delta=timedelta(seconds=-10)
    )

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()

def test_refresh_token_rotation_flow(client, seeded_users):
    """Verifies that presenting a valid refresh token returns a new rotated token pair."""
    admin_data = seeded_users["admin"]
    login_resp = client.post("/api/v1/auth/login", json={
        "email": admin_data["email"],
        "password": admin_data["password"]
    })
    token1 = login_resp.json()["refresh_token"]

    # Rotate token
    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token1})
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    token2 = data["refresh_token"]

    # Tokens must not be identical
    assert token1 != token2
    assert "access_token" in data

def test_refresh_token_reuse_detection_and_family_revocation(client, seeded_users, db):
    """
    CRITICAL SECURITY TEST:
    If a rotated (previously consumed) refresh token is submitted again,
    the entire session family MUST be revoked immediately, and future refreshes
    from that family must fail.
    """
    user_data = seeded_users["club"]
    login_resp = client.post("/api/v1/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    token_t1 = login_resp.json()["refresh_token"]

    # Valid rotation: T1 -> T2
    refresh1 = client.post("/api/v1/auth/refresh", json={"refresh_token": token_t1})
    assert refresh1.status_code == 200
    token_t2 = refresh1.json()["refresh_token"]

    # ATTACK / REUSE: Submitting T1 again!
    reuse_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token_t1})
    assert reuse_resp.status_code == 401
    assert "reuse detected" in reuse_resp.json()["detail"].lower()

    # Now verify T2 (the legitimate active child token) is ALSO revoked because family was killed!
    child_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": token_t2})
    assert child_refresh.status_code == 401

    # Verify audit event was logged
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.action == "AUTH_REFRESH_TOKEN_REUSE_DETECTED",
            AuditEvent.actor_user_id == user_data["user_id"]
        ).order_by(AuditEvent.created_at.desc())
    ).scalars().first()
    assert event is not None

def test_logout_revokes_active_session(client, seeded_users):
    """Verifies that calling logout revokes active sessions and prevents further refresh."""
    user_data = seeded_users["faculty"]
    login_resp = client.post("/api/v1/auth/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    access_token = login_resp.json()["access_token"]
    refresh_token = login_resp.json()["refresh_token"]

    # Logout
    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {access_token}"})
    assert logout_resp.status_code == 200

    # Refresh token should now be rejected
    ref_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert ref_resp.status_code == 401

def test_password_change_invalidates_all_active_sessions(client, db):
    """Verifies that changing password revokes all active sessions for that user."""
    test_email = f"pwd_test_{uuid.uuid4().hex[:8]}@cit.test"
    user = UserService.create_user(db, test_email, "Password Test User", "OldPassword123!")

    # Login to get session
    login1 = client.post("/api/v1/auth/login", json={"email": test_email, "password": "OldPassword123!"})
    access1 = login1.json()["access_token"]
    refresh1 = login1.json()["refresh_token"]

    # Change password
    change_resp = client.post(
        "/api/v1/auth/password-change",
        headers={"Authorization": f"Bearer {access1}"},
        json={"current_password": "OldPassword123!", "new_password": "NewSecurePassword456!"}
    )
    assert change_resp.status_code == 200

    # Old refresh token is now revoked
    ref_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
    assert ref_resp.status_code == 401

    # Login with new password succeeds
    login2 = client.post("/api/v1/auth/login", json={"email": test_email, "password": "NewSecurePassword456!"})
    assert login2.status_code == 200

def test_user_deactivation_prevents_login_and_refresh(client, db, seeded_users):
    """Verifies that deactivated user cannot login, and reactivating allows login."""
    test_email = f"deact_test_{uuid.uuid4().hex[:8]}@cit.test"
    user = UserService.create_user(db, test_email, "Deact User", "ValidPassword123!")

    # Login first
    login = client.post("/api/v1/auth/login", json={"email": test_email, "password": "ValidPassword123!"})
    refresh = login.json()["refresh_token"]

    admin_login = client.post("/api/v1/auth/login", json={
        "email": seeded_users["admin"]["email"],
        "password": seeded_users["admin"]["password"]
    })
    admin_token = admin_login.json()["access_token"]

    # Admin deactivates user
    deact = client.post(f"/api/v1/users/{user.id}/deactivate", headers={"Authorization": f"Bearer {admin_token}"})
    assert deact.status_code == 200

    # Refresh must now be rejected (session was revoked upon deactivation)
    ref_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert ref_resp.status_code in (401, 403)

    # Login must now be rejected
    login_resp = client.post("/api/v1/auth/login", json={"email": test_email, "password": "ValidPassword123!"})
    assert login_resp.status_code == 403

    # Admin reactivates user
    act = client.post(f"/api/v1/users/{user.id}/activate", headers={"Authorization": f"Bearer {admin_token}"})
    assert act.status_code == 200

    # Login now succeeds
    login_again = client.post("/api/v1/auth/login", json={"email": test_email, "password": "ValidPassword123!"})
    assert login_again.status_code == 200

def test_department_coordinator_authority_on_single_department_session(db, seeded_users):
    """
    Verifies that a Department Coordinator is authorized for sessions belonging
    strictly to their department.
    """
    cse_user_id = seeded_users["cse_coord"]["user_id"]
    ece_user_id = seeded_users["ece_coord"]["user_id"]

    # Find a single-department CSE session
    cse_dept = db.execute(select(Department).where(Department.code == "CSE")).scalars().first()
    assert cse_dept is not None

    cse_courses = db.execute(select(Course.id).where(Course.department_id == cse_dept.id)).scalars().all()
    assert len(cse_courses) > 0

    single_cse_session = None
    for cid in cse_courses:
        sessions = db.execute(select(TeachingSession).where(TeachingSession.course_id == cid)).scalars().all()
        for s in sessions:
            groups = db.execute(
                select(StudentGroup)
                .join(SessionGroup, SessionGroup.student_group_id == StudentGroup.id)
                .where(SessionGroup.session_id == s.id)
            ).scalars().all()
            if groups and all(g.department_id == cse_dept.id for g in groups):
                single_cse_session = s
                break
        if single_cse_session:
            break

    assert single_cse_session is not None, "Single CSE department session should exist in canonical dataset"

    # CSE Coordinator MUST be authorized
    auth_cse, reason_cse = evaluate_session_modification_authority(db, cse_user_id, single_cse_session.id)
    assert auth_cse is True, reason_cse

    # ECE Coordinator MUST be rejected
    auth_ece, reason_ece = evaluate_session_modification_authority(db, ece_user_id, single_cse_session.id)
    assert auth_ece is False
    assert "Coordinator lacks authority" in reason_ece

def test_joint_session_unilateral_modification_rejected(db, seeded_users):
    """
    CRITICAL SCHEDULING AUTHORITY INVARIANT:
    A CSE Coordinator CANNOT unilaterally edit or reschedule a joint session involving ECE.
    Checking owning department alone is insufficient when participating cohorts span other departments.
    """
    cse_user_id = seeded_users["cse_coord"]["user_id"]
    ece_user_id = seeded_users["ece_coord"]["user_id"]
    admin_user_id = seeded_users["admin"]["user_id"]

    # Find a joint session involving both CSE and ECE or multiple departments (e.g. HS201, ID101, OE301)
    joint_session = None
    all_sessions = db.execute(select(TeachingSession)).scalars().all()
    for s in all_sessions:
        groups = db.execute(
            select(StudentGroup)
            .join(SessionGroup, SessionGroup.student_group_id == StudentGroup.id)
            .where(SessionGroup.session_id == s.id)
        ).scalars().all()
        depts = {g.department_id for g in groups if g.department_id}
        if len(depts) > 1:
            joint_session = s
            break

    assert joint_session is not None, "Joint multi-cohort session must exist in canonical dataset"

    # CSE Coordinator alone MUST BE REJECTED
    auth_cse, reason_cse = evaluate_session_modification_authority(db, cse_user_id, joint_session.id)
    assert auth_cse is False
    assert "Unilateral modification rejected" in reason_cse

    # ECE Coordinator alone MUST BE REJECTED
    auth_ece, reason_ece = evaluate_session_modification_authority(db, ece_user_id, joint_session.id)
    assert auth_ece is False
    assert "Unilateral modification rejected" in reason_ece

    # Institute Admin MUST BE AUTHORIZED
    auth_admin, reason_admin = evaluate_session_modification_authority(db, admin_user_id, joint_session.id)
    assert auth_admin is True

def test_multi_department_coordinator_can_modify_joint_session(db, seeded_users):
    """
    Verifies that a user granted coordinator authority for ALL participating departments
    in a joint session IS authorized to modify it.
    """
    # Find a joint session
    all_sessions = db.execute(select(TeachingSession)).scalars().all()
    target_session = None
    involved_dept_ids = set()
    for s in all_sessions:
        groups = db.execute(
            select(StudentGroup)
            .join(SessionGroup, SessionGroup.student_group_id == StudentGroup.id)
            .where(SessionGroup.session_id == s.id)
        ).scalars().all()
        depts = {g.department_id for g in groups if g.department_id}
        if len(depts) > 1:
            target_session = s
            course = db.get(Course, s.course_id)
            if course and course.department_id:
                depts.add(course.department_id)
            involved_dept_ids = depts
            break

    assert target_session is not None

    # Create a user with coordinator grants for ALL involved departments
    dual_coord = UserService.create_user(db, f"dual_coord_{uuid.uuid4().hex[:6]}@cit.test", "Dual Coordinator", "Pass1234567!")
    for dept_id in involved_dept_ids:
        UserService.assign_role(db, dual_coord.id, "department_coordinator", "department", dept_id)

    # Authority evaluation MUST SUCCEED
    auth, reason = evaluate_session_modification_authority(db, dual_coord.id, target_session.id)
    assert auth is True, reason

def test_faculty_self_isolation(db, seeded_users):
    """Verifies that a faculty user can manage their own profile but cannot touch another faculty's profile."""
    faculty_user_id = seeded_users["faculty"]["user_id"]

    # Get faculty user's own assigned resource
    own_assignment = db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == faculty_user_id,
            UserRoleAssignment.role_code == ROLE_FACULTY,
            UserRoleAssignment.scope_type == SCOPE_RESOURCE
        )
    ).scalars().first()
    assert own_assignment is not None
    own_faculty_id = own_assignment.scope_id

    # Self access -> Allowed
    auth_self, _ = evaluate_faculty_access(db, faculty_user_id, own_faculty_id)
    assert auth_self is True

    # Another faculty member
    other_faculty = db.execute(
        select(Faculty).where(Faculty.id != own_faculty_id)
    ).scalars().first()
    assert other_faculty is not None

    # Other faculty access -> Denied
    auth_other, reason = evaluate_faculty_access(db, faculty_user_id, other_faculty.id)
    assert auth_other is False
    assert "Unauthorized" in reason

def test_club_rep_booking_authority_and_isolation(db, seeded_users):
    """Verifies that a club rep is authorized for club bookings but rejected for academic scheduling."""
    club_user_id = seeded_users["club"]["user_id"]

    # Find a club booking request
    club_booking = db.execute(
        select(BookingRequest).where(BookingRequest.requester_role == ROLE_CLUB)
    ).scalars().first()
    assert club_booking is not None

    # Authorized for club booking
    auth_booking, _ = evaluate_booking_request_authority(db, club_user_id, club_booking.id)
    assert auth_booking is True

    # Denied for teaching session modification
    session = db.execute(select(TeachingSession)).scalars().first()
    assert session is not None
    auth_session, reason = evaluate_session_modification_authority(db, club_user_id, session.id)
    assert auth_session is False
    assert "no active roles" in reason or "lacks" in reason

def test_admin_user_management_and_role_crud(client, seeded_users, db):
    """Verifies admin user endpoints: create user, assign role, revoke role, and list users."""
    admin_login = client.post("/api/v1/auth/login", json={
        "email": seeded_users["admin"]["email"],
        "password": seeded_users["admin"]["password"]
    })
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create User
    new_email = f"managed_user_{uuid.uuid4().hex[:6]}@cit.test"
    create_resp = client.post("/api/v1/users", headers=headers, json={
        "email": new_email,
        "display_name": "Managed User",
        "password": "SecurePassword987!",
        "status": "ACTIVE",
        "initial_role": {
            "role_code": "faculty",
            "scope_type": "resource",
            "scope_id": str(uuid.uuid4())
        }
    })
    assert create_resp.status_code == 201, create_resp.text
    user_data = create_resp.json()
    new_user_id = user_data["id"]
    assert "faculty" in user_data["roles"]

    # 2. Assign second role (department_coordinator)
    dept = db.execute(select(Department)).scalars().first()
    role_resp = client.post(f"/api/v1/users/{new_user_id}/roles", headers=headers, json={
        "role_code": "department_coordinator",
        "scope_type": "department",
        "scope_id": str(dept.id)
    })
    assert role_resp.status_code == 200
    assignment_id = role_resp.json()["id"]

    # 3. Revoke role
    del_resp = client.delete(f"/api/v1/users/{new_user_id}/roles/{assignment_id}", headers=headers)
    assert del_resp.status_code == 200

    # 4. Non-admin forbidden
    club_login = client.post("/api/v1/auth/login", json={
        "email": seeded_users["club"]["email"],
        "password": seeded_users["club"]["password"]
    })
    club_token = club_login.json()["access_token"]
    forbidden_resp = client.post("/api/v1/users", headers={"Authorization": f"Bearer {club_token}"}, json={
        "email": "hacker@cit.test",
        "display_name": "Hacker",
        "password": "Password123!"
    })
    assert forbidden_resp.status_code == 403

def test_audit_trail_recorded_for_security_events(client, seeded_users, db):
    """Verifies that audit events exist in core.audit_events for security operations."""
    admin_login = client.post("/api/v1/auth/login", json={
        "email": seeded_users["admin"]["email"],
        "password": seeded_users["admin"]["password"]
    })
    admin_token = admin_login.json()["access_token"]

    resp = client.get("/api/v1/auth/audit-logs?limit=50", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) > 0

    actions = {l["action"] for l in logs}
    # Verify core security action names appear in the audit trail
    assert "AUTH_LOGIN_SUCCESS" in actions
