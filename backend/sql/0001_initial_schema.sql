-- CIT Campus Scheduling & Venue Management Platform
-- PostgreSQL baseline schema v0.3
-- Generated: 2026-10-31
-- NOTE: Review against the organiser's final contract before production deployment.
BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS academic;
CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS scheduling;
CREATE SCHEMA IF NOT EXISTS booking;
CREATE SCHEMA IF NOT EXISTS exams;
CREATE SCHEMA IF NOT EXISTS change_mgmt;
CREATE SCHEMA IF NOT EXISTS approvals;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS assistant;
CREATE SCHEMA IF NOT EXISTS notifications;
CREATE SCHEMA IF NOT EXISTS integration;

-- ---------- CORE / DATASET / CALENDAR ----------

CREATE TABLE core.institutes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(64) NOT NULL UNIQUE,
    name text NOT NULL,
    timezone varchar(64) NOT NULL DEFAULT 'Asia/Kolkata',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.departments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES core.institutes(id),
    code varchar(64) NOT NULL,
    name text NOT NULL,
    UNIQUE (institute_id, code),
    UNIQUE (id, institute_id)
);

CREATE TABLE core.source_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    storage_key text NOT NULL,
    original_filename text NOT NULL,
    mime_type varchar(255) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sha256)
);

CREATE TABLE core.dataset_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES core.institutes(id),
    external_dataset_id varchar(128) NOT NULL,
    version_number integer NOT NULL CHECK (version_number > 0),
    parent_dataset_version_id uuid REFERENCES core.dataset_versions(id),
    source_artifact_id uuid REFERENCES core.source_artifacts(id),
    source_sha256 char(64) NOT NULL,
    import_schema_version varchar(32) NOT NULL,
    application_version varchar(64),
    status varchar(24) NOT NULL CHECK (status IN ('IMPORTING','IMPORTED','VALIDATION_FAILED','ACTIVE','ARCHIVED','DERIVED')),
    source_snapshot jsonb NOT NULL,
    derived_from_change_set_id uuid,
    imported_by uuid,
    imported_at timestamptz NOT NULL DEFAULT now(),
    activated_at timestamptz,
    UNIQUE (institute_id, external_dataset_id, version_number),
    UNIQUE (id, institute_id)
);

CREATE TABLE core.dataset_policy (
    dataset_version_id uuid PRIMARY KEY REFERENCES core.dataset_versions(id),
    priority_order jsonb NOT NULL,
    role_category_cap jsonb NOT NULL,
    policy_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE core.dataset_activations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    institute_id uuid NOT NULL REFERENCES core.institutes(id),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    activated_by uuid,
    activated_at timestamptz NOT NULL DEFAULT now(),
    deactivated_at timestamptz,
    reason text
);
CREATE UNIQUE INDEX uq_dataset_one_active
ON core.dataset_activations(institute_id) WHERE deactivated_at IS NULL;

CREATE TABLE core.calendar_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    timezone varchar(64) NOT NULL,
    fest_week_label text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, dataset_version_id),
    UNIQUE (dataset_version_id)
);

CREATE TABLE core.calendar_days (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    day_code varchar(8) NOT NULL,
    ordinal smallint NOT NULL CHECK (ordinal > 0),
    is_teaching_day boolean NOT NULL DEFAULT true,
    UNIQUE (calendar_version_id, day_code),
    UNIQUE (calendar_version_id, ordinal),
    UNIQUE (id, calendar_version_id)
);

CREATE TABLE core.calendar_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    period_number smallint NOT NULL CHECK (period_number > 0),
    starts_at time NOT NULL,
    ends_at time NOT NULL,
    is_teaching_period boolean NOT NULL,
    CHECK (ends_at > starts_at),
    UNIQUE (calendar_version_id, period_number),
    UNIQUE (id, calendar_version_id)
);

CREATE TABLE core.calendar_breaks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    break_code varchar(32) NOT NULL,
    after_period smallint,
    starts_at time NOT NULL,
    ends_at time NOT NULL,
    CHECK (ends_at > starts_at),
    UNIQUE (calendar_version_id, break_code)
);

CREATE TABLE core.calendar_lab_start_periods (
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    period_number smallint NOT NULL,
    PRIMARY KEY (calendar_version_id, period_number),
    FOREIGN KEY (calendar_version_id, period_number)
        REFERENCES core.calendar_periods(calendar_version_id, period_number)
);

CREATE TABLE core.calendar_event_periods (
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    period_number smallint NOT NULL,
    PRIMARY KEY (calendar_version_id, period_number),
    FOREIGN KEY (calendar_version_id, period_number)
        REFERENCES core.calendar_periods(calendar_version_id, period_number)
);

CREATE TABLE core.calendar_exam_days (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    day_code varchar(8) NOT NULL,
    ordinal smallint NOT NULL CHECK (ordinal > 0),
    UNIQUE (calendar_version_id, day_code),
    UNIQUE (calendar_version_id, ordinal)
);

CREATE TABLE core.calendar_exam_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    session_code varchar(16) NOT NULL,
    starts_at time NOT NULL,
    ends_at time NOT NULL,
    CHECK (ends_at > starts_at),
    UNIQUE (calendar_version_id, session_code),
    UNIQUE (id, calendar_version_id)
);

-- ---------- IDENTITY / AUTH / AUDIT ----------

CREATE TABLE identity.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email varchar(320) NOT NULL,
    display_name text NOT NULL,
    auth_provider varchar(32) NOT NULL,
    provider_subject text,
    password_hash text,
    status varchar(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE','INVITED','SUSPENDED','DISABLED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (email),
    UNIQUE (auth_provider, provider_subject)
);

CREATE TABLE identity.user_role_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES identity.users(id),
    role_code varchar(32) NOT NULL
        CHECK (role_code IN ('admin','department_coordinator','faculty','club')),
    scope_type varchar(32) NOT NULL
        CHECK (scope_type IN ('institute','department','club','resource')),
    scope_id uuid,
    granted_by uuid REFERENCES identity.users(id),
    granted_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz
);
CREATE INDEX ix_role_user_active ON identity.user_role_assignments(user_id, role_code)
WHERE revoked_at IS NULL;

CREATE TABLE identity.auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES identity.users(id),
    refresh_token_hash text NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (expires_at > created_at)
);

CREATE TABLE core.audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id uuid REFERENCES identity.users(id),
    action varchar(96) NOT NULL,
    target_type varchar(96) NOT NULL,
    target_id uuid,
    reason text,
    before_snapshot jsonb,
    after_snapshot jsonb,
    correlation_id uuid,
    dataset_version_id uuid REFERENCES core.dataset_versions(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_target_time ON core.audit_events(target_type, target_id, created_at DESC);
CREATE INDEX ix_audit_actor_time ON core.audit_events(actor_user_id, created_at DESC);

-- ---------- ACADEMIC MASTER DATA ----------

CREATE TABLE academic.rooms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    external_id varchar(128) NOT NULL,
    name text NOT NULL,
    building text,
    room_type varchar(64) NOT NULL,
    capacity integer NOT NULL CHECK (capacity > 0),
    accessible boolean NOT NULL DEFAULT false,
    UNIQUE (dataset_version_id, external_id),
    UNIQUE (id, dataset_version_id)
);

CREATE TABLE academic.room_features (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(64) NOT NULL UNIQUE,
    label text NOT NULL
);

CREATE TABLE academic.room_feature_assignments (
    room_id uuid NOT NULL REFERENCES academic.rooms(id),
    feature_id uuid NOT NULL REFERENCES academic.room_features(id),
    PRIMARY KEY (room_id, feature_id)
);

CREATE TABLE academic.room_allowed_uses (
    room_id uuid NOT NULL REFERENCES academic.rooms(id),
    use_code varchar(32) NOT NULL,
    PRIMARY KEY (room_id, use_code)
);

CREATE TABLE academic.faculty (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    external_id varchar(128) NOT NULL,
    name text NOT NULL,
    department_id uuid REFERENCES core.departments(id),
    max_hours_per_day numeric(4,2) NOT NULL DEFAULT 4 CHECK (max_hours_per_day > 0),
    needs_accessible boolean NOT NULL DEFAULT false,
    UNIQUE (dataset_version_id, external_id),
    UNIQUE (id, dataset_version_id)
);

CREATE TABLE academic.student_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    external_id varchar(128) NOT NULL,
    name text NOT NULL,
    year smallint,
    department_id uuid REFERENCES core.departments(id),
    size integer NOT NULL CHECK (size > 0),
    needs_accessible boolean NOT NULL DEFAULT false,
    UNIQUE (dataset_version_id, external_id),
    UNIQUE (id, dataset_version_id)
);

CREATE TABLE academic.courses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    external_id varchar(128) NOT NULL,
    title text NOT NULL,
    department_id uuid REFERENCES core.departments(id),
    year smallint,
    lecture_hours numeric(5,2) NOT NULL DEFAULT 0 CHECK (lecture_hours >= 0),
    tutorial_hours numeric(5,2) NOT NULL DEFAULT 0 CHECK (tutorial_hours >= 0),
    lab_blocks numeric(5,2) NOT NULL DEFAULT 0 CHECK (lab_blocks >= 0),
    UNIQUE (dataset_version_id, external_id),
    UNIQUE (id, dataset_version_id)
);

CREATE TABLE academic.teaching_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    external_id varchar(128) NOT NULL,
    course_id uuid NOT NULL,
    kind varchar(32) NOT NULL,
    faculty_id uuid,
    size integer NOT NULL CHECK (size > 0),
    duration_periods smallint NOT NULL CHECK (duration_periods > 0),
    needs_accessible boolean NOT NULL DEFAULT false,
    basket_slot varchar(128),
    fixed_day varchar(8),
    fixed_start_period smallint,
    source_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (dataset_version_id, external_id),
    UNIQUE (id, dataset_version_id),
    FOREIGN KEY (course_id, dataset_version_id)
        REFERENCES academic.courses(id, dataset_version_id),
    FOREIGN KEY (faculty_id, dataset_version_id)
        REFERENCES academic.faculty(id, dataset_version_id),
    CHECK ((fixed_day IS NULL AND fixed_start_period IS NULL)
        OR (fixed_day IS NOT NULL AND fixed_start_period IS NOT NULL))
);

CREATE TABLE academic.session_groups (
    session_id uuid NOT NULL REFERENCES academic.teaching_sessions(id),
    student_group_id uuid NOT NULL REFERENCES academic.student_groups(id),
    PRIMARY KEY (session_id, student_group_id)
);

CREATE TABLE academic.session_allowed_room_types (
    session_id uuid NOT NULL REFERENCES academic.teaching_sessions(id),
    room_type varchar(64) NOT NULL,
    PRIMARY KEY (session_id, room_type)
);

CREATE TABLE academic.faculty_unavailability (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    faculty_id uuid NOT NULL REFERENCES academic.faculty(id),
    day_code varchar(8) NOT NULL,
    period_number smallint NOT NULL CHECK (period_number > 0),
    reason text,
    UNIQUE (faculty_id, day_code, period_number)
);

CREATE TABLE academic.room_unavailability (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id uuid NOT NULL REFERENCES academic.rooms(id),
    day_code varchar(8) NOT NULL,
    period_number smallint NOT NULL CHECK (period_number > 0),
    reason text,
    UNIQUE (room_id, day_code, period_number)
);

CREATE TABLE academic.faculty_preferences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    faculty_id uuid NOT NULL REFERENCES academic.faculty(id),
    preference_type varchar(24) NOT NULL CHECK (preference_type IN ('avoid','prefer')),
    day_code varchar(8) NOT NULL,
    period_number smallint NOT NULL CHECK (period_number > 0),
    note text,
    weight numeric(8,3) NOT NULL DEFAULT 1
);

-- ---------- SCHEDULING ----------

CREATE TABLE scheduling.timetable_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    parent_version_id uuid REFERENCES scheduling.timetable_versions(id),
    version_number integer NOT NULL CHECK (version_number > 0),
    status varchar(24) NOT NULL CHECK (status IN
        ('DRAFT','GENERATING','GENERATED','NEEDS_VALIDATION','VALIDATED','APPROVED','PUBLISHED','FAILED','ARCHIVED')),
    created_by uuid REFERENCES identity.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    approved_by uuid REFERENCES identity.users(id),
    approved_at timestamptz,
    published_at timestamptz,
    UNIQUE (dataset_version_id, version_number),
    UNIQUE (id, dataset_version_id),
    FOREIGN KEY (calendar_version_id, dataset_version_id)
        REFERENCES core.calendar_versions(id, dataset_version_id)
);

CREATE TABLE scheduling.timetable_generation_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    requested_by uuid REFERENCES identity.users(id),
    request_config jsonb NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key varchar(128),
    status varchar(24) NOT NULL DEFAULT 'QUEUED',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (requested_by, idempotency_key)
);

CREATE TABLE scheduling.solver_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_request_id uuid REFERENCES scheduling.timetable_generation_requests(id),
    timetable_version_id uuid REFERENCES scheduling.timetable_versions(id),
    solver_name varchar(64) NOT NULL,
    solver_version varchar(64),
    random_seed bigint,
    time_limit_seconds integer CHECK (time_limit_seconds > 0),
    worker_count integer CHECK (worker_count > 0),
    objective_config jsonb NOT NULL,
    solver_status varchar(24) NOT NULL CHECK (solver_status IN
        ('OPTIMAL','FEASIBLE','INFEASIBLE','UNKNOWN','TIME_LIMIT','FAILED')),
    runtime_ms bigint CHECK (runtime_ms >= 0),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE scheduling.timetable_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    timetable_version_id uuid NOT NULL REFERENCES scheduling.timetable_versions(id),
    session_id uuid NOT NULL REFERENCES academic.teaching_sessions(id),
    day_code varchar(8) NOT NULL,
    start_period smallint NOT NULL CHECK (start_period > 0),
    room_id uuid NOT NULL REFERENCES academic.rooms(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (timetable_version_id, session_id),
    UNIQUE (id, timetable_version_id)
);
CREATE INDEX ix_timetable_day_period ON scheduling.timetable_assignments(timetable_version_id, day_code, start_period);
CREATE INDEX ix_timetable_room_slot ON scheduling.timetable_assignments(timetable_version_id, room_id, day_code, start_period);

CREATE TABLE scheduling.timetable_occupancy (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    timetable_version_id uuid NOT NULL REFERENCES scheduling.timetable_versions(id),
    resource_type varchar(24) NOT NULL CHECK (resource_type IN ('room','faculty','student_group')),
    resource_id uuid NOT NULL,
    day_code varchar(8) NOT NULL,
    period_number smallint NOT NULL CHECK (period_number > 0),
    assignment_id uuid NOT NULL REFERENCES scheduling.timetable_assignments(id),
    occupancy_key varchar(160) NOT NULL,
    UNIQUE (timetable_version_id, resource_type, occupancy_key, day_code, period_number)
);
CREATE INDEX ix_occupancy_resource ON scheduling.timetable_occupancy(timetable_version_id, resource_type, resource_id, day_code, period_number);

CREATE TABLE scheduling.solver_metrics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    solver_run_id uuid NOT NULL REFERENCES scheduling.solver_runs(id),
    hard_violation_count integer NOT NULL CHECK (hard_violation_count >= 0),
    soft_s1 numeric(12,3) NOT NULL DEFAULT 0,
    soft_s2 numeric(12,3) NOT NULL DEFAULT 0,
    soft_s3 numeric(12,3) NOT NULL DEFAULT 0,
    soft_s4 numeric(12,3) NOT NULL DEFAULT 0,
    soft_s5 numeric(12,3) NOT NULL DEFAULT 0,
    soft_s6 numeric(12,3) NOT NULL DEFAULT 0,
    objective_value numeric(16,4),
    metrics_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE scheduling.validation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type varchar(32) NOT NULL,
    target_version_id uuid NOT NULL,
    validator_name varchar(64) NOT NULL,
    validator_version varchar(64),
    source_checksum char(64),
    status varchar(24) NOT NULL CHECK (status IN ('PASSED','FAILED','WARNING','ERROR')),
    hard_violation_count integer NOT NULL DEFAULT 0,
    soft_score numeric(16,4),
    report_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE scheduling.validation_violations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_run_id uuid NOT NULL REFERENCES scheduling.validation_runs(id),
    rule_code varchar(24) NOT NULL,
    severity varchar(16) NOT NULL CHECK (severity IN ('HARD','SOFT','WARNING','INFO')),
    entity_type varchar(64),
    entity_external_id varchar(128),
    message text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE scheduling.timetable_publications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    timetable_version_id uuid NOT NULL REFERENCES scheduling.timetable_versions(id),
    published_by uuid REFERENCES identity.users(id),
    published_at timestamptz NOT NULL DEFAULT now(),
    supersedes_publication_id uuid REFERENCES scheduling.timetable_publications(id)
);

CREATE TABLE scheduling.published_timetable_pointers (
    institute_id uuid PRIMARY KEY REFERENCES core.institutes(id),
    timetable_version_id uuid NOT NULL REFERENCES scheduling.timetable_versions(id),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- ---------- BOOKING / FEST WEEK ----------

CREATE TABLE booking.booking_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    external_id varchar(128) NOT NULL,
    submitted_at timestamptz NOT NULL,
    requester_label text NOT NULL,
    requester_role varchar(32) NOT NULL,
    department_id uuid REFERENCES core.departments(id),
    requested_category varchar(64) NOT NULL,
    title text NOT NULL,
    attendance integer NOT NULL CHECK (attendance > 0),
    duration_periods smallint NOT NULL CHECK (duration_periods > 0),
    requested_room_id uuid REFERENCES academic.rooms(id),
    series_id varchar(128),
    raw_text text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_version_id, external_id),
    UNIQUE (id, dataset_version_id)
);

CREATE TABLE booking.booking_cancellations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_request_id uuid NOT NULL UNIQUE REFERENCES booking.booking_requests(id),
    cancelled_at timestamptz NOT NULL,
    cancelled_by_label text,
    note text
);

CREATE TABLE booking.booking_windows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_request_id uuid NOT NULL REFERENCES booking.booking_requests(id),
    day_code varchar(8) NOT NULL,
    from_period smallint NOT NULL CHECK (from_period > 0),
    to_period smallint NOT NULL CHECK (to_period >= from_period)
);

CREATE TABLE booking.booking_allowed_room_types (
    booking_request_id uuid NOT NULL REFERENCES booking.booking_requests(id),
    room_type varchar(64) NOT NULL,
    PRIMARY KEY (booking_request_id, room_type)
);

CREATE TABLE booking.booking_required_features (
    booking_request_id uuid NOT NULL REFERENCES booking.booking_requests(id),
    feature_code varchar(64) NOT NULL,
    PRIMARY KEY (booking_request_id, feature_code)
);

CREATE TABLE booking.booking_mandatory_groups (
    booking_request_id uuid NOT NULL REFERENCES booking.booking_requests(id),
    student_group_id uuid NOT NULL REFERENCES academic.student_groups(id),
    PRIMARY KEY (booking_request_id, student_group_id)
);

CREATE TABLE booking.booking_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_request_id uuid NOT NULL REFERENCES booking.booking_requests(id),
    decision_status varchar(24) NOT NULL CHECK (decision_status IN ('approved','rejected','alternative_offered')),
    effective_category varchar(64) NOT NULL,
    reason text,
    decided_by uuid REFERENCES identity.users(id),
    decided_at timestamptz NOT NULL DEFAULT now(),
    supersedes_decision_id uuid REFERENCES booking.booking_decisions(id),
    is_effective boolean NOT NULL DEFAULT true
);
CREATE UNIQUE INDEX uq_booking_effective_decision
ON booking.booking_decisions(booking_request_id) WHERE is_effective;

CREATE TABLE booking.booking_allocations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_decision_id uuid NOT NULL REFERENCES booking.booking_decisions(id),
    room_id uuid NOT NULL REFERENCES academic.rooms(id),
    day_code varchar(8) NOT NULL,
    start_period smallint NOT NULL CHECK (start_period > 0),
    end_period smallint NOT NULL CHECK (end_period >= start_period),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE booking.booking_alternative_responses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_decision_id uuid NOT NULL REFERENCES booking.booking_decisions(id),
    response varchar(16) NOT NULL CHECK (response IN ('ACCEPTED','DECLINED')),
    responded_by uuid REFERENCES identity.users(id),
    responded_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (booking_decision_id)
);

CREATE TABLE booking.fest_week_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    baseline_timetable_version_id uuid NOT NULL REFERENCES scheduling.timetable_versions(id),
    parent_version_id uuid REFERENCES booking.fest_week_versions(id),
    version_number integer NOT NULL CHECK (version_number > 0),
    status varchar(24) NOT NULL CHECK (status IN ('DRAFT','VALIDATED','APPROVED','PUBLISHED','ARCHIVED','FAILED')),
    created_by uuid REFERENCES identity.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_version_id, version_number)
);

CREATE TABLE booking.fest_week_booking_decisions (
    fest_week_version_id uuid NOT NULL REFERENCES booking.fest_week_versions(id),
    booking_decision_id uuid NOT NULL REFERENCES booking.booking_decisions(id),
    PRIMARY KEY (fest_week_version_id, booking_decision_id)
);

CREATE TABLE booking.session_overrides (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fest_week_version_id uuid NOT NULL REFERENCES booking.fest_week_versions(id),
    session_id uuid NOT NULL REFERENCES academic.teaching_sessions(id),
    baseline_assignment_id uuid NOT NULL REFERENCES scheduling.timetable_assignments(id),
    new_day varchar(8) NOT NULL,
    new_start_period smallint NOT NULL CHECK (new_start_period > 0),
    new_room_id uuid NOT NULL REFERENCES academic.rooms(id),
    displaced_by_booking_decision_id uuid NOT NULL REFERENCES booking.booking_decisions(id),
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (fest_week_version_id, session_id)
);

CREATE TABLE booking.booking_priority_evaluations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fest_week_version_id uuid NOT NULL REFERENCES booking.fest_week_versions(id),
    booking_request_id uuid NOT NULL REFERENCES booking.booking_requests(id),
    effective_category varchar(64) NOT NULL,
    category_rank integer NOT NULL,
    tie_break_timestamp timestamptz NOT NULL,
    explanation jsonb NOT NULL,
    UNIQUE (fest_week_version_id, booking_request_id)
);

-- ---------- APPROVALS ----------

CREATE TABLE approvals.approval_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type varchar(64) NOT NULL,
    target_id uuid NOT NULL,
    assigned_role varchar(32) NOT NULL,
    assigned_scope_type varchar(32) NOT NULL,
    assigned_scope_id uuid,
    assigned_user_id uuid REFERENCES identity.users(id),
    status varchar(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','APPROVED','REJECTED','CHANGES_REQUESTED','CANCELLED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    due_at timestamptz,
    completed_at timestamptz
);

CREATE TABLE approvals.approval_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_task_id uuid NOT NULL REFERENCES approvals.approval_tasks(id),
    actor_user_id uuid NOT NULL REFERENCES identity.users(id),
    action varchar(32) NOT NULL,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_approval_inbox_role ON approvals.approval_tasks(assigned_role, status, created_at);
CREATE INDEX ix_approval_inbox_user ON approvals.approval_tasks(assigned_user_id, status, created_at);

-- ---------- EXAMS ----------

CREATE TABLE exams.exam_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    external_id varchar(128) NOT NULL,
    size integer NOT NULL CHECK (size > 0),
    duration_hours numeric(5,2) NOT NULL CHECK (duration_hours > 0),
    UNIQUE (dataset_version_id, external_id),
    UNIQUE (id, dataset_version_id)
);

CREATE TABLE exams.exam_courses (
    exam_id uuid NOT NULL REFERENCES exams.exam_records(id),
    course_id uuid NOT NULL REFERENCES academic.courses(id),
    PRIMARY KEY (exam_id, course_id)
);

CREATE TABLE exams.exam_groups (
    exam_id uuid NOT NULL REFERENCES exams.exam_records(id),
    student_group_id uuid NOT NULL REFERENCES academic.student_groups(id),
    PRIMARY KEY (exam_id, student_group_id)
);

CREATE TABLE exams.exam_schedule_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    calendar_version_id uuid NOT NULL REFERENCES core.calendar_versions(id),
    parent_version_id uuid REFERENCES exams.exam_schedule_versions(id),
    version_number integer NOT NULL CHECK (version_number > 0),
    status varchar(24) NOT NULL CHECK (status IN ('DRAFT','GENERATING','GENERATED','VALIDATED','APPROVED','PUBLISHED','FAILED','ARCHIVED')),
    created_by uuid REFERENCES identity.users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset_version_id, version_number),
    FOREIGN KEY (calendar_version_id, dataset_version_id)
        REFERENCES core.calendar_versions(id, dataset_version_id)
);

CREATE TABLE exams.exam_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_schedule_version_id uuid NOT NULL REFERENCES exams.exam_schedule_versions(id),
    exam_id uuid NOT NULL REFERENCES exams.exam_records(id),
    day_code varchar(8) NOT NULL,
    session_code varchar(16) NOT NULL,
    UNIQUE (exam_schedule_version_id, exam_id)
);

CREATE TABLE exams.exam_room_allocations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_assignment_id uuid NOT NULL REFERENCES exams.exam_assignments(id),
    room_id uuid NOT NULL REFERENCES academic.rooms(id),
    allocated_capacity integer NOT NULL CHECK (allocated_capacity > 0),
    UNIQUE (exam_assignment_id, room_id)
);

-- ---------- CHANGE MANAGEMENT ----------

CREATE TABLE change_mgmt.disruption_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_artifact_id uuid REFERENCES core.source_artifacts(id),
    status varchar(24) NOT NULL CHECK (status IN ('IMPORTED','VALIDATED','PROPOSED','APPLIED','REJECTED','FAILED')),
    imported_by uuid REFERENCES identity.users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE change_mgmt.disruption_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    disruption_set_id uuid NOT NULL REFERENCES change_mgmt.disruption_sets(id),
    change_type varchar(32) NOT NULL CHECK (change_type IN
        ('faculty_unavailable','room_unavailable','add_faculty','add_session','remove_session')),
    target_external_id varchar(128),
    payload jsonb NOT NULL,
    reason text
);

CREATE TABLE change_mgmt.change_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    disruption_set_id uuid NOT NULL REFERENCES change_mgmt.disruption_sets(id),
    baseline_dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    target_dataset_version_id uuid REFERENCES core.dataset_versions(id),
    baseline_timetable_version_id uuid NOT NULL REFERENCES scheduling.timetable_versions(id),
    proposed_timetable_version_id uuid REFERENCES scheduling.timetable_versions(id),
    status varchar(24) NOT NULL CHECK (status IN ('DRAFT','SOLVING','VALIDATED','PENDING_APPROVAL','APPROVED','REJECTED','APPLIED','INFEASIBLE','FAILED')),
    movement_count integer CHECK (movement_count >= 0),
    created_by uuid REFERENCES identity.users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE change_mgmt.change_proposal_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_proposal_id uuid NOT NULL REFERENCES change_mgmt.change_proposals(id),
    session_id uuid REFERENCES academic.teaching_sessions(id),
    change_kind varchar(32) NOT NULL,
    before_assignment jsonb,
    after_assignment jsonb,
    explanation text
);

CREATE TABLE change_mgmt.change_approvals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_proposal_id uuid NOT NULL REFERENCES change_mgmt.change_proposals(id),
    actor_user_id uuid NOT NULL REFERENCES identity.users(id),
    decision varchar(16) NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE change_mgmt.applied_change_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_proposal_id uuid NOT NULL UNIQUE REFERENCES change_mgmt.change_proposals(id),
    derived_dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    result_timetable_version_id uuid NOT NULL REFERENCES scheduling.timetable_versions(id),
    applied_by uuid NOT NULL REFERENCES identity.users(id),
    applied_at timestamptz NOT NULL DEFAULT now()
);

-- add deferred FK now that change tables exist
ALTER TABLE core.dataset_versions
ADD CONSTRAINT fk_dataset_derived_change
FOREIGN KEY (derived_from_change_set_id) REFERENCES change_mgmt.applied_change_sets(id)
DEFERRABLE INITIALLY DEFERRED;

-- ---------- ANALYTICS / ASSISTANT / NOTIFICATIONS / INTEGRATION ----------

CREATE TABLE analytics.metric_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid REFERENCES core.dataset_versions(id),
    timetable_version_id uuid REFERENCES scheduling.timetable_versions(id),
    fest_week_version_id uuid REFERENCES booking.fest_week_versions(id),
    metric_key varchar(96) NOT NULL,
    metric_value numeric(18,4) NOT NULL,
    dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
    computed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE assistant.conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES identity.users(id),
    title text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE assistant.messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES assistant.conversations(id),
    role varchar(16) NOT NULL CHECK (role IN ('user','assistant','tool','system')),
    content text,
    structured_payload jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE assistant.tool_executions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id uuid NOT NULL REFERENCES assistant.messages(id),
    tool_name varchar(96) NOT NULL,
    input_payload jsonb NOT NULL,
    output_payload jsonb,
    status varchar(20) NOT NULL CHECK (status IN ('PENDING','SUCCEEDED','FAILED','REJECTED')),
    validation_run_id uuid REFERENCES scheduling.validation_runs(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notifications.notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id uuid NOT NULL REFERENCES identity.users(id),
    notification_type varchar(64) NOT NULL,
    title text NOT NULL,
    body text NOT NULL,
    target_type varchar(64),
    target_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    read_at timestamptz
);
CREATE INDEX ix_notifications_inbox ON notifications.notifications(recipient_user_id, read_at, created_at DESC);

CREATE TABLE integration.import_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid REFERENCES core.dataset_versions(id),
    source_artifact_id uuid REFERENCES core.source_artifacts(id),
    status varchar(20) NOT NULL CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    report_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE integration.export_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id uuid NOT NULL REFERENCES core.dataset_versions(id),
    timetable_version_id uuid REFERENCES scheduling.timetable_versions(id),
    fest_week_version_id uuid REFERENCES booking.fest_week_versions(id),
    exam_schedule_version_id uuid REFERENCES exams.exam_schedule_versions(id),
    export_kind varchar(32) NOT NULL,
    status varchar(20) NOT NULL CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
    source_checksum char(64),
    output_artifact_id uuid REFERENCES core.source_artifacts(id),
    created_by uuid REFERENCES identity.users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE integration.validator_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    export_job_id uuid NOT NULL REFERENCES integration.export_jobs(id),
    validator_version varchar(64),
    command_line text,
    status varchar(20) NOT NULL CHECK (status IN ('PASSED','FAILED','ERROR')),
    report_artifact_id uuid REFERENCES core.source_artifacts(id),
    report_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE integration.background_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type varchar(64) NOT NULL,
    payload jsonb NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'QUEUED'
        CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    locked_at timestamptz,
    locked_by varchar(128),
    last_error text,
    result_json jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
CREATE INDEX ix_background_jobs_claim ON integration.background_jobs(status, available_at, created_at);

CREATE TABLE integration.idempotency_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_key varchar(128) NOT NULL,
    idempotency_key varchar(128) NOT NULL,
    request_hash char(64) NOT NULL,
    response_status integer,
    response_body jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    UNIQUE (scope_key, idempotency_key)
);

COMMIT;
