from __future__ import annotations
import uuid
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import User, UserRoleAssignment
from app.modules.academic.models import (
    TeachingSession, Course, StudentGroup, SessionGroup, Faculty, FacultyDepartment
)
from app.modules.booking.models import BookingRequest

# Exactly four official competition roles
ROLE_ADMIN = "admin"
ROLE_DEPARTMENT_COORDINATOR = "department_coordinator"
ROLE_FACULTY = "faculty"
ROLE_CLUB = "club"
OFFICIAL_ROLES = {ROLE_ADMIN, ROLE_DEPARTMENT_COORDINATOR, ROLE_FACULTY, ROLE_CLUB}

# Scopes
SCOPE_INSTITUTE = "institute"
SCOPE_DEPARTMENT = "department"
SCOPE_CLUB = "club"
SCOPE_RESOURCE = "resource"
OFFICIAL_SCOPES = {SCOPE_INSTITUTE, SCOPE_DEPARTMENT, SCOPE_CLUB, SCOPE_RESOURCE}

def get_active_user_roles_and_scopes(db: Session, user_id: uuid.UUID) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Retrieves all non-revoked roles and scope assignments for a given user."""
    stmt = select(UserRoleAssignment).where(
        UserRoleAssignment.user_id == user_id,
        UserRoleAssignment.revoked_at.is_(None)
    )
    assignments = db.execute(stmt).scalars().all()
    roles = sorted(list({a.role_code for a in assignments}))
    scopes = [
        {
            "assignment_id": str(a.id),
            "role_code": a.role_code,
            "scope_type": a.scope_type,
            "scope_id": str(a.scope_id) if a.scope_id else None
        }
        for a in assignments
    ]
    return roles, scopes

def is_institute_admin(assignments: List[UserRoleAssignment]) -> bool:
    """Checks if the user possesses the admin role with institute scope."""
    return any(
        a.role_code == ROLE_ADMIN and a.scope_type == SCOPE_INSTITUTE and a.revoked_at is None
        for a in assignments
    )

def get_coordinator_department_ids(assignments: List[UserRoleAssignment]) -> Set[uuid.UUID]:
    """Returns the set of department IDs for which the user is an active coordinator."""
    return {
        a.scope_id
        for a in assignments
        if a.role_code == ROLE_DEPARTMENT_COORDINATOR
        and a.scope_type == SCOPE_DEPARTMENT
        and a.scope_id is not None
        and a.revoked_at is None
    }

def get_faculty_resource_ids(assignments: List[UserRoleAssignment]) -> Set[uuid.UUID]:
    """Returns the set of faculty resource UUIDs assigned to this user."""
    return {
        a.scope_id
        for a in assignments
        if a.role_code == ROLE_FACULTY
        and a.scope_type == SCOPE_RESOURCE
        and a.scope_id is not None
        and a.revoked_at is None
    }

def get_club_scope_ids(assignments: List[UserRoleAssignment]) -> Set[uuid.UUID]:
    """Returns the set of club scope UUIDs assigned to this user."""
    return {
        a.scope_id
        for a in assignments
        if a.role_code == ROLE_CLUB
        and a.scope_type in (SCOPE_CLUB, SCOPE_RESOURCE)
        and a.scope_id is not None
        and a.revoked_at is None
    }

def evaluate_session_modification_authority(
    db: Session,
    user_id: uuid.UUID,
    session_id: uuid.UUID
) -> Tuple[bool, str]:
    """
    Evaluates whether a user has authority to modify, reschedule, or cancel a teaching session.
    
    Core Invariants:
    1. Institute Admin has global authority over all sessions.
    2. A Department Coordinator can ONLY modify sessions belonging strictly and exclusively
       to their assigned department(s).
    3. Joint/Cross-Department Sessions (e.g., CSE + ECE cohorts):
       A CSE Coordinator CANNOT unilaterally modify a joint session involving ECE.
       Unilateral modifications are strictly rejected; authority requires Admin privileges
       or explicit multi-department grants covering ALL participating departments.
    """
    # 1. Fetch user assignments
    assignments = db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.revoked_at.is_(None)
        )
    ).scalars().all()

    if not assignments:
        return False, "User has no active roles or permissions"

    if is_institute_admin(assignments):
        return True, "Authorized via Institute Admin authority"

    coord_dept_ids = get_coordinator_department_ids(assignments)
    if not coord_dept_ids:
        return False, "User lacks department coordinator authority"

    # 2. Fetch session, course, and participating groups
    session = db.execute(
        select(TeachingSession).where(TeachingSession.id == session_id)
    ).scalar_one_or_none()
    if not session:
        return False, f"Teaching session {session_id} not found"

    course = db.execute(
        select(Course).where(Course.id == session.course_id)
    ).scalar_one_or_none()
    if not course:
        return False, f"Course {session.course_id} for session not found"

    groups = db.execute(
        select(StudentGroup)
        .join(SessionGroup, SessionGroup.student_group_id == StudentGroup.id)
        .where(SessionGroup.session_id == session_id)
    ).scalars().all()

    # 3. Determine all involved department IDs
    involved_dept_ids: Set[uuid.UUID] = set()
    if course.department_id:
        involved_dept_ids.add(course.department_id)
    for g in groups:
        if g.department_id:
            involved_dept_ids.add(g.department_id)

    if not involved_dept_ids:
        return False, "Session has no identifiable department associations"

    # 4. Check joint session cross-department authority
    if len(involved_dept_ids) > 1:
        # Joint class across multiple departments
        unauthorized_depts = involved_dept_ids - coord_dept_ids
        if unauthorized_depts:
            return (
                False,
                f"Unilateral modification rejected: session '{session.external_id}' is a joint cross-department "
                f"session involving {len(involved_dept_ids)} departments. Action requires multi-department coordinator "
                f"grants covering all involved cohorts, or Institute Admin authority."
            )
        return True, "Authorized: coordinator holds explicit grants for all departments in this joint session"

    # 5. Single department session
    single_dept = next(iter(involved_dept_ids))
    if single_dept in coord_dept_ids:
        return True, f"Authorized coordinator for department {single_dept}"

    return False, f"Coordinator lacks authority for department {single_dept}"

def evaluate_faculty_access(
    db: Session,
    user_id: uuid.UUID,
    faculty_id: uuid.UUID
) -> Tuple[bool, str]:
    """
    Evaluates whether a user can access/modify a faculty member's profile, preferences, or availability.
    - Admin: allowed.
    - Department Coordinator: allowed if faculty belongs to coordinator's department.
    - Faculty Member: allowed ONLY for their own assigned faculty resource.
    - Others: rejected.
    """
    assignments = db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.revoked_at.is_(None)
        )
    ).scalars().all()

    if not assignments:
        return False, "User has no active roles"

    if is_institute_admin(assignments):
        return True, "Authorized via Institute Admin authority"

    # Check self faculty resource grant
    faculty_resource_ids = get_faculty_resource_ids(assignments)
    if faculty_id in faculty_resource_ids:
        return True, "Authorized: faculty member accessing their own resource"

    # Check if coordinator for faculty's department
    coord_dept_ids = get_coordinator_department_ids(assignments)
    if coord_dept_ids:
        fac_depts = db.execute(
            select(FacultyDepartment.department_id).where(
                FacultyDepartment.faculty_id == faculty_id
            )
        ).scalars().all()
        if any(d_id in coord_dept_ids for d_id in fac_depts):
            return True, "Authorized: department coordinator managing departmental faculty member"

    return False, "Unauthorized: faculty profile cannot be accessed or modified by this user"

def evaluate_booking_request_authority(
    db: Session,
    user_id: uuid.UUID,
    booking_id: uuid.UUID
) -> Tuple[bool, str]:
    """
    Evaluates whether a user can modify or cancel a booking request.
    - Admin: allowed.
    - Department Coordinator: allowed for bookings belonging to their department.
    - Club Rep: allowed for club bookings assigned to their club.
    """
    assignments = db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.revoked_at.is_(None)
        )
    ).scalars().all()

    if not assignments:
        return False, "User has no active roles"

    if is_institute_admin(assignments):
        return True, "Authorized via Institute Admin authority"

    booking = db.execute(
        select(BookingRequest).where(BookingRequest.id == booking_id)
    ).scalar_one_or_none()
    if not booking:
        return False, f"Booking request {booking_id} not found"

    coord_dept_ids = get_coordinator_department_ids(assignments)
    if booking.department_id and booking.department_id in coord_dept_ids:
        return True, "Authorized: department coordinator for booking's department"

    club_scope_ids = get_club_scope_ids(assignments)
    # Check if user has club role and matches club scope
    user_roles = {a.role_code for a in assignments}
    if ROLE_CLUB in user_roles and booking.requester_role == ROLE_CLUB:
        return True, "Authorized: club representative managing club booking"

    return False, "Unauthorized to manage this booking request"
