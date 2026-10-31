# CIT Backend & Database Engineering Master Package v0.5

**Scope:** Backend and database only. Frontend implementation and Campus Navigator are explicitly deferred.

This package combines the prior source documents and starter pack with a new engineering review and detailed domain rules for department isolation, shared teaching, resource conflicts, scoped timetable generation, multi-department permissions, and production-grade backend workflows.

## Read in this order

1. `00_READ_FIRST/MASTER_AI_STUDIO_INSTRUCTION.md`
2. `01_ARCHITECTURE_AND_RULES/DOMAIN_RULEBOOK.md`
3. `01_ARCHITECTURE_AND_RULES/DEPARTMENT_AND_SHARED_CLASS_SCHEDULING.md`
4. `01_ARCHITECTURE_AND_RULES/REQUIREMENTS_TRACEABILITY_AND_OPEN_DECISIONS.md`
5. `02_DATABASE_HARDENING/DATABASE_REVIEW_AND_HARDENING_PLAN.md`
6. `03_BACKEND_IMPLEMENTATION_PLAN/BACKEND_MODULES_AND_API_BEHAVIOUR.md`
7. `04_VALIDATION_AND_TESTS/ACCEPTANCE_TEST_MATRIX.md`
8. `CURRENT_BACKEND_DATABASE_BASELINE_v0_4/` (actual current source baseline)
9. `REFERENCE_MATERIAL/` (original evidence, official validator, original dataset and historical documents)

## Critical status statement

v0.4 is a partial database foundation, not a completed backend. Its SQL migration has only been rendered offline; no live PostgreSQL migration has been confirmed. ORM coverage is partial. Dataset import, scheduling solver, exam solver, booking workflows, disruption workflows and the API are not complete.

The new v0.5 material is a reviewed specification and implementation plan. It does not falsely claim that these workflows have already been implemented.

## Department isolation principle

A department filter is not a conflict-isolation boundary. CSE and ECE may schedule independently only when their actual student groups, faculty, rooms and other shared resources do not collide.

- CSE-only class: consumes CSE group(s), its faculty, and its room.
- ECE-only class: consumes ECE group(s), its faculty, and its room.
- Joint CSE+ECE class: one shared teaching session consumes every participating group, the assigned faculty member(s), and the shared room.
- A teacher is an institute-wide exclusive resource by default, not a department-local resource.
- A room is an institute-wide exclusive resource by default.
- A student group is a distinct conflict resource. CSE group occupancy must not block an unrelated ECE group, but a joint session must occupy both groups.
- Department-scoped generation must preserve and lock unaffected departments' assignments while still checking every shared resource globally.

## Package integrity

The original competition starter pack and validator are retained under `REFERENCE_MATERIAL/04_OFFICIAL_COMPETITION_SOURCE/`. Do not replace or edit the original validator. The official validator remains the final authority for competition output acceptance.
