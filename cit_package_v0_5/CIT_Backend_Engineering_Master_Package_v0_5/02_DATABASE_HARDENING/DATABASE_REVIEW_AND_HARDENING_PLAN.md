# Database Review & Hardening Plan — v0.5

## 1. Existing v0.4 baseline review

The v0.4 baseline has 12 schemas and 78 tables. It is a useful broad relational design, but it is not a complete or live-tested database implementation.

Known strengths:
- Dataset-version concept and source snapshot.
- Separate academic, scheduling, booking, exam, change-management, approvals, analytics and integration schemas.
- Calendar versions.
- Timetable versions and assignment/occupancy tables.
- Explicit booking decisions and alternative responses.
- Audit events and idempotency/background-job concepts.
- Initial SQLAlchemy mappings and source-contract Pydantic validation.

Known gaps to resolve:
- Live PostgreSQL migration has not been run.
- Only partial ORM coverage exists.
- Import service is not implemented.
- Several child association tables use simple foreign keys and can potentially cross dataset versions.
- Timetable assignment does not directly carry dataset_version_id, making composite dataset integrity harder to enforce.
- `session_groups` lacks dataset-scoped composite foreign keys.
- `session_allowed_room_types`, room feature assignments, room allowed uses, unavailability and preference relationships need dataset integrity review.
- Teaching session currently has one `faculty_id`; multi-faculty support is not modelled.
- Faculty has one department_id; multiple department affiliations are not modelled.
- Department-scoped generation/locked-outside-scope baseline is not normalized.
- Session scope cannot be safely inferred from course department alone.
- No explicit cross-department session flag or derivation exists.
- Conflict occupancy must be generated from all group/faculty/room resources and validated independently.
- Polymorphic `scope_id` and target IDs cannot use ordinary foreign keys; service validation and audit are essential.
- Dataset activation and timetable publication need concurrency-safe transactions.
- No database-level exclusion constraint currently guarantees no overlapping period assignments; application/solver plus independent validation is required. Consider PostgreSQL exclusion constraints only after deciding a normalized time-range representation.
- Status columns use CHECK constraints but transition graphs must be enforced in services.
- Soft-delete and immutable snapshot policies need explicit rules.

## 2. Recommended database additions

### 2.1 Faculty affiliations
Add `academic.faculty_departments(faculty_id, department_id, is_primary, valid_from, valid_to)` so one faculty member can be affiliated with multiple departments while remaining one global resource. Preserve `faculty.department_id` as legacy/source primary department during transition.

### 2.2 Multiple teaching faculty
Add `academic.teaching_session_faculty(session_id, faculty_id, assignment_role, is_primary)` with unique `(session_id, faculty_id)` and one primary instructor per session where the source model requires it. Backfill current `teaching_sessions.faculty_id`. Source import remains compatible with its single faculty_id field.

### 2.3 Dataset-safe joins
Add dataset_version_id to association/assignment rows where needed and composite foreign keys:
- session_groups -> teaching_sessions and student_groups within same dataset;
- session faculty -> teaching_sessions and faculty within same dataset;
- timetable assignments -> timetable version, teaching session and room within same dataset;
- booking mandatory groups -> booking request and group within same dataset;
- exam courses/groups -> exam and course/group within same dataset;
- unavailability/preferences -> faculty/room in same dataset;
- session overrides -> same dataset as fest-week/timetable/session/room.

Do not use a migration that guesses relationships. Backfill by joining the parent record and fail migration if any mismatch is found.

### 2.4 Scoped generation
Normalize generation scope:
- `scheduling.generation_scope` linked to generation request, baseline timetable version, preserve_outside_scope flag, scope status and scope fingerprint.
- `scheduling.generation_scope_departments` list target departments.
- `scheduling.generation_scope_sessions` records included target sessions and inclusion reason (direct department, participating group, cross-department, explicit event).
- `scheduling.locked_assignments` records assignments that must remain fixed in this run, including outside-scope baseline assignments.
Store a baseline hash/version and reject apply if stale.

### 2.5 Explicit ownership for non-class activities
Bookings/events without student groups need `owner_department_id` or `owner_club_id` where applicable. Do not overload the event requester's department text as a reliable authorization scope.

### 2.6 Shared class attendance
Store participation group links and derive attendance as sum of group sizes only when group sets are known to be disjoint. If overlap is possible, require an explicit verified expected_attendance override. Record the derivation method and snapshot for audit.

## 3. Transaction and concurrency rules

- Dataset import: one transaction; failed validation/import rolls back all rows.
- Dataset activation: lock institute active-dataset row or use serializable/explicit advisory lock; only one active dataset.
- Timetable publication: compare expected baseline version, validate candidate, insert publication pointer and audit event atomically.
- Booking decision: lock request and target resource slots; re-evaluate availability inside transaction; create decision and allocation atomically.
- Alternative acceptance: lock alternative and request; ensure not expired and still available; revalidate, then convert to approved allocation atomically.
- Disruption apply: lock proposal and baseline pointer; verify approvals and version; revalidate full affected resource graph; create new active dataset/timetable pointer atomically.
- Idempotency: store request key, actor, operation, request hash and response reference; same key with different payload must return conflict.
- Background jobs: at-least-once execution; handlers must be idempotent.

## 4. Immutability and versioning

- Imported dataset snapshots are immutable after successful import.
- Timetable versions are immutable after validation/publication; corrections create a new version.
- Solver runs record exact solver/library version, parameters, random seed, source dataset, baseline timetable and objective config.
- Booking decision history is append-only; supersede rather than rewrite.
- Audit events are append-only.
- Never mutate a published version in place.

## 5. Indexing priorities

Add indexes only after query patterns are explicit. Initial critical candidates:
- active dataset by institute;
- active role assignment by user/scope;
- session groups by student_group_id and session_id;
- faculty teaching assignments by faculty_id;
- timetable assignments by timetable_version/day/start and room/day;
- occupancy by timetable/resource/day/period;
- pending approvals by role/scope/status/created_at;
- booking requests by dataset/status/submitted_at;
- booking allocations by room/day/start/end;
- solver/background job status and created_at.

## 6. Migration policy

1. Run v0.4 migration against disposable PostgreSQL.
2. Save schema dump and migration output.
3. Apply hardening in new Alembic revisions; never rewrite applied revisions.
4. Backfill and validate before NOT NULL/composite FK constraints.
5. Test fresh install and upgrade-from-v0.4 separately.
6. Test downgrade only where safe; for data-bearing changes prefer forward-only corrective migrations.
7. Add metadata parity tests, migration smoke tests and schema acceptance tests.
8. Keep SQL and ORM constraints aligned.

## 7. Required database tests

- Fresh database migration.
- Upgrade from v0.4.
- Dataset cross-reference rejection.
- Two datasets cannot share child references accidentally.
- CSE/ECE independent group rows can coexist.
- Joint session group links must all reference same dataset.
- Same faculty/room occupancy uniqueness is enforced by occupancy builder and independent validator.
- Stale timetable publish rejected.
- Two simultaneous booking approvals cannot reserve same room/time.
- Failed import leaves no partial rows.
- Same source fingerprint import is idempotent or produces a documented new immutable version.
