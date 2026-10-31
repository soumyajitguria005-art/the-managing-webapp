# Migration 0002 Review Notes

This is a proposed corrective migration, not yet applied or live-tested.

It addresses:
- dataset-safe session-to-student-group links;
- multi-department faculty affiliation;
- one-to-many teaching-session faculty assignments (source-compatible);
- dataset-safe timetable assignment to timetable/session/room;
- dataset-safe mandatory booking groups;
- normalized department generation scope;
- locked baseline assignments outside scope;
- explicit owner department for group-less booking requests.

## Preconditions
- v0.4 baseline must be successfully applied to a disposable PostgreSQL database.
- Existing data must be checked for cross-dataset references before migration.
- Existing faculty/session/booking records must be loaded consistently.
- `core.departments` must contain all department IDs referenced by the academic data.

## Important limitations
- This migration does not complete every composite FK in the 78-table schema. Exam joins, room feature joins, unavailability/preferences, overrides, and other child relations still require a systematic integrity pass.
- It does not create a student-group overlap/atomic-cohort model. The official fixture only provides group-level resources; overlapping real-world groups need an explicit data contract.
- It does not implement solver logic or permissions.
- `scope_fingerprint` and `baseline_hash` must be calculated by application services using canonical serialization.
- The migration assumes department IDs have already been mapped from source department labels. If the current import mapping is not complete, defer the owner_department column backfill and use a staged mapping table.
- Before production, add composite dataset FKs to `generation_scope_sessions` and `locked_assignments` through their parent version chain, and add RLS or service-layer isolation as selected.

## Execution policy
Run first on a disposable database. Inspect the schema after migration. Run all DB integration tests. Do not edit migration 0001 after it has been applied; if this migration needs changes after application, create 0003.
