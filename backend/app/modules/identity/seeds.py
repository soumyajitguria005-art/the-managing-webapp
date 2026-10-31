from __future__ import annotations
import uuid
from typing import Any, Dict
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.identity.models import User, UserRoleAssignment
from app.modules.datasets.models import Department
from app.modules.academic.models import Faculty
from app.modules.identity.permissions import (
    ROLE_ADMIN,
    ROLE_DEPARTMENT_COORDINATOR,
    ROLE_FACULTY,
    ROLE_CLUB,
    SCOPE_INSTITUTE,
    SCOPE_DEPARTMENT,
    SCOPE_RESOURCE,
    SCOPE_CLUB,
)

DEV_TEST_PASSWORDS = {
    "admin": "CitAdmin2026!Secure",
    "cse_coord": "CitCseCoord2026!Secure",
    "ece_coord": "CitEceCoord2026!Secure",
    "faculty": "CitFaculty2026!Secure",
    "club": "CitClubRep2026!Secure",
}

def seed_dev_identities(db: Session) -> Dict[str, Dict[str, Any]]:
    """
    Seeds reproducible development and test user accounts for the four official roles:
    1. Institute Admin (global authority)
    2. CSE Department Coordinator
    3. ECE Department Coordinator
    4. Multi-Department Faculty Member (Dr. Rajesh Kumar across CSE and ECE)
    5. Club Representative
    
    Safe for development and integration test execution.
    """
    # 1. Lookup CSE and ECE departments if imported
    cse_dept = db.execute(select(Department).where(Department.code == "CSE")).scalars().first()
    ece_dept = db.execute(select(Department).where(Department.code == "ECE")).scalars().first()
    
    # If no department exists in DB yet, create placeholder departments
    if not cse_dept:
        cse_dept = Department(code="CSE", name="Department of Computer Science & Engineering")
        db.add(cse_dept)
        db.flush()
    if not ece_dept:
        ece_dept = Department(code="ECE", name="Department of Electronics & Communication Engineering")
        db.add(ece_dept)
        db.flush()

    # Find or associate a faculty record
    faculty_rec = db.execute(select(Faculty)).scalars().first()
    faculty_id = faculty_rec.id if faculty_rec else uuid.uuid4()

    club_scope_id = uuid.uuid4()

    seed_specs = [
        {
            "key": "admin",
            "email": "admin@cit.test",
            "display_name": "Institute Administrator",
            "password": DEV_TEST_PASSWORDS["admin"],
            "roles": [
                {"role_code": ROLE_ADMIN, "scope_type": SCOPE_INSTITUTE, "scope_id": None}
            ]
        },
        {
            "key": "cse_coord",
            "email": "cse_coordinator@cit.test",
            "display_name": "CSE Department Coordinator",
            "password": DEV_TEST_PASSWORDS["cse_coord"],
            "roles": [
                {"role_code": ROLE_DEPARTMENT_COORDINATOR, "scope_type": SCOPE_DEPARTMENT, "scope_id": cse_dept.id}
            ]
        },
        {
            "key": "ece_coord",
            "email": "ece_coordinator@cit.test",
            "display_name": "ECE Department Coordinator",
            "password": DEV_TEST_PASSWORDS["ece_coord"],
            "roles": [
                {"role_code": ROLE_DEPARTMENT_COORDINATOR, "scope_type": SCOPE_DEPARTMENT, "scope_id": ece_dept.id}
            ]
        },
        {
            "key": "faculty",
            "email": "dr_rajesh_kumar@cit.test",
            "display_name": "Dr. Rajesh Kumar",
            "password": DEV_TEST_PASSWORDS["faculty"],
            "roles": [
                {"role_code": ROLE_FACULTY, "scope_type": SCOPE_RESOURCE, "scope_id": faculty_id},
                {"role_code": ROLE_FACULTY, "scope_type": SCOPE_DEPARTMENT, "scope_id": cse_dept.id},
                {"role_code": ROLE_FACULTY, "scope_type": SCOPE_DEPARTMENT, "scope_id": ece_dept.id},
            ]
        },
        {
            "key": "club",
            "email": "club_rep@cit.test",
            "display_name": "Robotics Club Representative",
            "password": DEV_TEST_PASSWORDS["club"],
            "roles": [
                {"role_code": ROLE_CLUB, "scope_type": SCOPE_CLUB, "scope_id": club_scope_id}
            ]
        }
    ]

    seeded_users: Dict[str, Dict[str, Any]] = {}

    for spec in seed_specs:
        user = db.execute(select(User).where(User.email == spec["email"])).scalar_one_or_none()
        if not user:
            user = User(
                email=spec["email"],
                display_name=spec["display_name"],
                password_hash=hash_password(spec["password"]),
                status="ACTIVE",
                auth_provider="LOCAL"
            )
            db.add(user)
            db.flush()

        # Ensure clean idempotency: revoke any previous active assignments for seeded user
        db.execute(
            update(UserRoleAssignment)
            .where(
                UserRoleAssignment.user_id == user.id,
                UserRoleAssignment.revoked_at.is_(None)
            )
            .values(revoked_at=func.now())
        )

        # Apply fresh role assignments
        for r in spec["roles"]:
            db.add(UserRoleAssignment(
                user_id=user.id,
                role_code=r["role_code"],
                scope_type=r["scope_type"],
                scope_id=r["scope_id"],
            ))
        db.flush()

        seeded_users[spec["key"]] = {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "password": spec["password"],
            "roles": [r["role_code"] for r in spec["roles"]],
        }

    db.commit()
    return seeded_users
