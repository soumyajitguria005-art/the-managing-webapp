# Implementation Status Snapshot — v0.4

| Capability | Status | Notes |
|---|---|---|
| PostgreSQL baseline DDL | Present; live execution pending | 78 tables across 12 schemas |
| Alembic initial migration | Present; offline render passes | Statement-by-statement execution hardened; live run pending |
| Local PostgreSQL Compose | Present | Requires Docker on developer machine |
| Strict source JSON contract | Implemented for canonical fixture shape | Includes nested fields and cross-reference checks |
| Source fingerprint/count/ID helpers | Implemented | No hardcoded production counts |
| SQLAlchemy models | Partial | 15 tables mapped |
| Dataset import transaction | Not implemented | Next after live migration and full mappings |
| Dataset activation transaction | Not implemented | Separate transaction/locking required |
| Authentication | Not implemented | Provider decision open |
| Timetable solver/API | Not implemented | OR-Tools domain implementation is a later backend milestone |
| Booking approval workflow | Not implemented | Reviewer routing decision open |
| Exam scheduler | Not implemented | Must use official constraints/validator |
| Disruption/change proposal workflow | Not implemented | Admin approval and minimal-move objective to implement |
| Analytics/notifications/AI assistant | Not implemented | Later modules; AI output must be code-validated |
| Campus Navigator | Deferred | Teammate-owned integration boundary only |
| Frontend | Deferred | Backend-first agreement |
