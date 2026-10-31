# Implementation Status & Release Gates

## Current verified baseline

| Area | Status |
|---|---|
| Product and competition requirements documentation | Available |
| Official starter data and validator | Included |
| PostgreSQL DDL baseline | Exists; offline rendering previously passed |
| Live PostgreSQL migration | NOT VERIFIED |
| SQLAlchemy mappings | Partial |
| Pydantic source contract | Partial foundation |
| Transactional dataset import | Not implemented |
| Authentication/authorization services | Not implemented |
| Department-scoped timetable generation | Specification added; not implemented |
| Joint cross-department teaching | Specification added; not implemented |
| OR-Tools timetable solver | Not implemented |
| Exam solver | Not implemented |
| Booking workflow | Schema foundation only |
| Disruption workflow | Schema foundation only |
| Analytics APIs | Not implemented |
| AI assistant tools | Not implemented |
| Frontend | Deferred |
| Campus Navigator | Deferred |

## Gate 1 — Database
Live Postgres migration, schema acceptance, all composite FKs, ORM coverage and upgrade path.

## Gate 2 — Import
Strict source contract, transactional import, fingerprint, idempotency, rollback and dataset activation.

## Gate 3 — Identity and scope
Authentication, four official roles, institute/department/club/resource scopes, audit and authorization tests.

## Gate 4 — Scheduling
Department isolation, global shared resource occupancy, joint teaching, solver and independent validation.

## Gate 5 — Exams and bookings
Official constraints, priority, approval and alternatives.

## Gate 6 — Disruptions
Minimal-change proposals, Admin approval, atomic application.

## Gate 7 — API hardening and release
Observability, rate limits, load/edge tests, official exports and final validator.

Do not mark a gate complete based on generated code alone.
