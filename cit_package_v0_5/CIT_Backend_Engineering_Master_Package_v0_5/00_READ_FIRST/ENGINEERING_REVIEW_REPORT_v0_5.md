# CIT Engineering Review Report v0.5

Date: 31 October 2026  
Scope: Backend and database only.

## Executive finding

The existing v0.4 database baseline is a broad first-pass relational foundation, but it is not yet a functional backend. It has a large schema surface, partial ORM coverage, source-contract validation and offline migration rendering. It has not been executed against live PostgreSQL, and the dataset import/business workflows remain unimplemented.

The most important new domain clarification is department-aware scheduling with institute-wide shared-resource collision detection. A department is a management scope, not a separate physical universe.

## Specific CSE/ECE rule

A CSE class and an ECE class can occur simultaneously if their student groups, teachers and rooms are distinct. They cannot occur simultaneously if they share a teacher or room. A single joint CSE+ECE class must link both groups to one session and consume both group resources, its faculty resources and its room. A department-only generation must preserve unrelated department assignments while validating all global resource conflicts.

This is now specified in:
- `01_ARCHITECTURE_AND_RULES/DEPARTMENT_AND_SHARED_CLASS_SCHEDULING.md`
- `04_VALIDATION_AND_TESTS/ACCEPTANCE_TEST_MATRIX.md`

## Existing v0.4 technical review findings

1. The schema uses `academic.teaching_sessions.faculty_id` as a single faculty assignment. The source fixture is compatible with this, but the application needs a path for multi-faculty/shared teaching if that is supported.
2. `academic.session_groups` has simple foreign keys and no dataset_version_id, so the DB does not fully guarantee that both session and group belong to the same dataset version.
3. `scheduling.timetable_assignments` does not store dataset_version_id and its independent foreign keys do not guarantee that timetable, session and room belong to one dataset.
4. Several other association tables require the same dataset integrity audit.
5. The generation request has a JSON config but no normalized generation scope or locked-outside-scope baseline records.
6. `academic.faculty.department_id` is single-department. A multi-affiliation association is appropriate, while faculty remains one global conflict resource.
7. There is no explicit group-overlap model. Treating each provided student group as an atomic conflict unit is safe only if source groups are mutually exclusive or represent disjoint cohorts.
8. There is no full import service, solver, booking decision service, disruption apply service or API implementation yet.
9. The initial database migration was only rendered offline; live Postgres execution remains pending.

## New v0.5 additions

- Master AI Studio instruction scoped to backend/database.
- Domain rulebook and source-authority distinctions.
- Department/shared-class scheduling design.
- Requirements traceability and open decisions.
- Database hardening plan.
- Proposed SQL migration 0002.
- Backend module/API behaviour contract.
- Acceptance test matrix with 16 department/shared-resource cases.
- Implementation status and release gates.

## Not done and not claimed

- No live database migration was executed.
- Migration 0002 has not been applied.
- ORM mappings are not complete for all 78 tables.
- Transactional import is not implemented.
- Solver and API workflows are not implemented.
- No official final schedule export has been generated or validated.
- Frontend and Campus Navigator remain deferred.

## Next engineering action

Run v0.4 on disposable PostgreSQL; inspect and fix baseline errors; apply hardening migration 0002 in a new Alembic revision; add migration and integrity tests; complete ORM mappings; then implement transactional dataset import. Do not begin timetable solver work until the imported domain model and resource relationships are verified.
