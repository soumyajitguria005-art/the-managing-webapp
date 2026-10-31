"""Department scope, shared teaching, and dataset composite integrity hardening.

Revision ID: 0002_dept_scope_shared_teaching
Revises: 0001_initial
Create Date: 2026-10-31
"""
from alembic import op

revision = "0002_dept_scope_shared_teaching"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
-- 1) Dataset-scoped session_groups join table
ALTER TABLE academic.session_groups ADD COLUMN dataset_version_id uuid;

UPDATE academic.session_groups sg
SET dataset_version_id = ts.dataset_version_id
FROM academic.teaching_sessions ts
WHERE ts.id = sg.session_id;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM academic.session_groups sg
    JOIN academic.student_groups g ON g.id = sg.student_group_id
    WHERE g.dataset_version_id <> sg.dataset_version_id
  ) THEN
    RAISE EXCEPTION 'session_groups contains cross-dataset group references';
  END IF;
END $$;

ALTER TABLE academic.session_groups ALTER COLUMN dataset_version_id SET NOT NULL;

ALTER TABLE academic.session_groups
  ADD CONSTRAINT fk_session_groups_session_dataset
  FOREIGN KEY (session_id, dataset_version_id)
  REFERENCES academic.teaching_sessions(id, dataset_version_id);

ALTER TABLE academic.session_groups
  ADD CONSTRAINT fk_session_groups_group_dataset
  FOREIGN KEY (student_group_id, dataset_version_id)
  REFERENCES academic.student_groups(id, dataset_version_id);

CREATE INDEX ix_session_groups_group ON academic.session_groups(student_group_id, session_id);

-- 2) Faculty affiliations: many-to-many, preserving primary department
CREATE TABLE academic.faculty_departments (
  faculty_id uuid NOT NULL REFERENCES academic.faculty(id),
  department_id uuid NOT NULL REFERENCES core.departments(id),
  is_primary boolean NOT NULL DEFAULT false,
  valid_from date,
  valid_to date,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (faculty_id, department_id),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

INSERT INTO academic.faculty_departments(faculty_id, department_id, is_primary)
SELECT id, department_id, true
FROM academic.faculty
WHERE department_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE UNIQUE INDEX uq_faculty_one_primary_department
ON academic.faculty_departments(faculty_id) WHERE is_primary;

-- 3) Multi-faculty teaching assignments with dataset composite foreign keys
CREATE TABLE academic.teaching_session_faculty (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL,
  dataset_version_id uuid NOT NULL,
  faculty_id uuid NOT NULL,
  assignment_role varchar(32) NOT NULL DEFAULT 'instructor',
  is_primary boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (session_id, faculty_id),
  FOREIGN KEY (session_id, dataset_version_id)
    REFERENCES academic.teaching_sessions(id, dataset_version_id),
  FOREIGN KEY (faculty_id, dataset_version_id)
    REFERENCES academic.faculty(id, dataset_version_id)
);

INSERT INTO academic.teaching_session_faculty
  (session_id, dataset_version_id, faculty_id, assignment_role, is_primary)
SELECT id, dataset_version_id, faculty_id, 'instructor', true
FROM academic.teaching_sessions
WHERE faculty_id IS NOT NULL
ON CONFLICT (session_id, faculty_id) DO NOTHING;

CREATE UNIQUE INDEX uq_session_one_primary_faculty
ON academic.teaching_session_faculty(session_id) WHERE is_primary;

CREATE INDEX ix_session_faculty_faculty ON academic.teaching_session_faculty(faculty_id, session_id);

-- 4) Dataset identity on timetable assignments and composite FKs
ALTER TABLE scheduling.timetable_assignments ADD COLUMN dataset_version_id uuid;

UPDATE scheduling.timetable_assignments a
SET dataset_version_id = tv.dataset_version_id
FROM scheduling.timetable_versions tv
WHERE tv.id = a.timetable_version_id;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM scheduling.timetable_assignments a
    JOIN academic.teaching_sessions s ON s.id = a.session_id
    JOIN academic.rooms r ON r.id = a.room_id
    WHERE s.dataset_version_id <> a.dataset_version_id
       OR r.dataset_version_id <> a.dataset_version_id
  ) THEN
    RAISE EXCEPTION 'timetable_assignments contains cross-dataset session or room references';
  END IF;
END $$;

ALTER TABLE scheduling.timetable_assignments ALTER COLUMN dataset_version_id SET NOT NULL;

ALTER TABLE scheduling.timetable_assignments
  ADD CONSTRAINT uq_assignment_id_timetable_dataset
  UNIQUE (id, timetable_version_id, dataset_version_id);

ALTER TABLE scheduling.timetable_assignments
  ADD CONSTRAINT fk_assignment_timetable_dataset
  FOREIGN KEY (timetable_version_id, dataset_version_id)
  REFERENCES scheduling.timetable_versions(id, dataset_version_id);

ALTER TABLE scheduling.timetable_assignments
  ADD CONSTRAINT fk_assignment_session_dataset
  FOREIGN KEY (session_id, dataset_version_id)
  REFERENCES academic.teaching_sessions(id, dataset_version_id);

ALTER TABLE scheduling.timetable_assignments
  ADD CONSTRAINT fk_assignment_room_dataset
  FOREIGN KEY (room_id, dataset_version_id)
  REFERENCES academic.rooms(id, dataset_version_id);

-- 5) Dataset-scoped mandatory booking groups
ALTER TABLE booking.booking_mandatory_groups ADD COLUMN dataset_version_id uuid;

UPDATE booking.booking_mandatory_groups bg
SET dataset_version_id = br.dataset_version_id
FROM booking.booking_requests br
WHERE br.id = bg.booking_request_id;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM booking.booking_mandatory_groups bg
    JOIN academic.student_groups sg ON sg.id = bg.student_group_id
    WHERE sg.dataset_version_id <> bg.dataset_version_id
  ) THEN
    RAISE EXCEPTION 'booking_mandatory_groups contains cross-dataset group references';
  END IF;
END $$;

ALTER TABLE booking.booking_mandatory_groups ALTER COLUMN dataset_version_id SET NOT NULL;

ALTER TABLE booking.booking_mandatory_groups
  ADD CONSTRAINT fk_booking_mandatory_request_dataset
  FOREIGN KEY (booking_request_id, dataset_version_id)
  REFERENCES booking.booking_requests(id, dataset_version_id);

ALTER TABLE booking.booking_mandatory_groups
  ADD CONSTRAINT fk_booking_mandatory_group_dataset
  FOREIGN KEY (student_group_id, dataset_version_id)
  REFERENCES academic.student_groups(id, dataset_version_id);

-- 6) Normalized generation scopes and locked baseline assignments
CREATE TABLE scheduling.generation_scopes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  generation_request_id uuid NOT NULL UNIQUE
    REFERENCES scheduling.timetable_generation_requests(id),
  baseline_timetable_version_id uuid REFERENCES scheduling.timetable_versions(id),
  preserve_outside_scope boolean NOT NULL DEFAULT true,
  scope_mode varchar(24) NOT NULL
    CHECK (scope_mode IN ('INSTITUTE','DEPARTMENT','SELECTED_GROUPS')),
  scope_fingerprint char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE scheduling.generation_scope_departments (
  generation_scope_id uuid NOT NULL REFERENCES scheduling.generation_scopes(id),
  department_id uuid NOT NULL REFERENCES core.departments(id),
  PRIMARY KEY (generation_scope_id, department_id)
);

CREATE TABLE scheduling.generation_scope_sessions (
  generation_scope_id uuid NOT NULL REFERENCES scheduling.generation_scopes(id),
  session_id uuid NOT NULL REFERENCES academic.teaching_sessions(id),
  inclusion_reason varchar(32) NOT NULL
    CHECK (inclusion_reason IN ('DIRECT_DEPARTMENT','PARTICIPATING_GROUP','CROSS_DEPARTMENT','EXPLICIT_OWNER')),
  is_movable boolean NOT NULL DEFAULT true,
  PRIMARY KEY (generation_scope_id, session_id)
);

CREATE TABLE scheduling.locked_assignments (
  generation_scope_id uuid NOT NULL REFERENCES scheduling.generation_scopes(id),
  assignment_id uuid NOT NULL REFERENCES scheduling.timetable_assignments(id),
  lock_reason varchar(32) NOT NULL
    CHECK (lock_reason IN ('OUTSIDE_SCOPE','CROSS_SCOPE_AUTHORITY','ADMIN_LOCK','FIXED_BASELINE')),
  baseline_hash char(64) NOT NULL,
  PRIMARY KEY (generation_scope_id, assignment_id)
);

CREATE INDEX ix_generation_scope_session_session
ON scheduling.generation_scope_sessions(session_id);

-- 7) Explicit department owner for activities without student groups
ALTER TABLE booking.booking_requests
  ADD COLUMN owner_department_id uuid REFERENCES core.departments(id);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE booking.booking_requests DROP COLUMN IF EXISTS owner_department_id;
DROP TABLE IF EXISTS scheduling.locked_assignments CASCADE;
DROP TABLE IF EXISTS scheduling.generation_scope_sessions CASCADE;
DROP TABLE IF EXISTS scheduling.generation_scope_departments CASCADE;
DROP TABLE IF EXISTS scheduling.generation_scopes CASCADE;

ALTER TABLE booking.booking_mandatory_groups DROP CONSTRAINT IF EXISTS fk_booking_mandatory_group_dataset;
ALTER TABLE booking.booking_mandatory_groups DROP CONSTRAINT IF EXISTS fk_booking_mandatory_request_dataset;
ALTER TABLE booking.booking_mandatory_groups DROP COLUMN IF EXISTS dataset_version_id;

ALTER TABLE scheduling.timetable_assignments DROP CONSTRAINT IF EXISTS fk_assignment_room_dataset;
ALTER TABLE scheduling.timetable_assignments DROP CONSTRAINT IF EXISTS fk_assignment_session_dataset;
ALTER TABLE scheduling.timetable_assignments DROP CONSTRAINT IF EXISTS fk_assignment_timetable_dataset;
ALTER TABLE scheduling.timetable_assignments DROP CONSTRAINT IF EXISTS uq_assignment_id_timetable_dataset;
ALTER TABLE scheduling.timetable_assignments DROP COLUMN IF EXISTS dataset_version_id;

DROP TABLE IF EXISTS academic.teaching_session_faculty CASCADE;
DROP TABLE IF EXISTS academic.faculty_departments CASCADE;

ALTER TABLE academic.session_groups DROP CONSTRAINT IF EXISTS fk_session_groups_group_dataset;
ALTER TABLE academic.session_groups DROP CONSTRAINT IF EXISTS fk_session_groups_session_dataset;
DROP INDEX IF EXISTS academic.ix_session_groups_group;
ALTER TABLE academic.session_groups DROP COLUMN IF EXISTS dataset_version_id;
"""

from sqlalchemy import text

def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(UPGRADE_SQL))

def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(DOWNGRADE_SQL))

