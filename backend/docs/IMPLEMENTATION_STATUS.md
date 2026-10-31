# Implementation Status Snapshot — v0.5 (Milestone 3 Complete)

| Capability | Status | Notes |
|---|---|---|
| PostgreSQL live environment | COMPLETED | PostgreSQL 15.19 cluster running on 127.0.0.1:5432 with cit_dev database |
| Alembic migrations (0001, 0002) | COMPLETED | Applied cleanly to head (`0002_dept_scope_shared_teaching`); fresh reproducible |
| SQLAlchemy ORM Mappings | COMPLETED | All 84 PostgreSQL tables mapped 1-to-1 across 12 schemas; compiles to valid DDL |
| Strict source JSON contract | COMPLETED | Strict Pydantic models with extra="forbid"; clear JSON path error diagnostics |
| Canonical Fixture Ingestion | COMPLETED | Official cit_public.json (SHA-256: 83513621...) ingested without CSV fallback |
| Transactional Import Pipeline | COMPLETED | Atomic all-or-nothing pipeline with rollback on failure and autonomous failed job audit |
| Source ID Preservation | COMPLETED | 100% matched across rooms, faculty, groups, courses, sessions, bookings, exams |
| Joint Session Preservation | COMPLETED | Single session row with multiple group links (HS201, ID101, OE301-303) |
| Multi-Department Faculty | COMPLETED | Supported via core.departments and academic.faculty_departments |
| Dataset Versioning & Idempotency | COMPLETED | Unique version increments; idempotent re-import of identical fingerprints |
| Dataset Activation Service | COMPLETED | Atomic activation with SELECT FOR UPDATE lock; supersedes and archives previous |
| Dataset FastAPI Endpoints | COMPLETED | Full REST API on /api/v1/datasets (validate, import, jobs, reconciliation, activate) |
| Relationship Reconciliation | COMPLETED | Verified entity relationships: sessions/groups, rooms/features, faculty/dept, bookings |
| Integration Test Suite | COMPLETED | 48 / 48 tests passing against live PostgreSQL in 23.13s |
| Authentication & RBAC (Milestone 4) | COMPLETED | 4 official roles (admin, department_coordinator, faculty, club), JWT + Refresh rotation with reuse detection, lockout, scoped authority |
| Academic Master Data Query API | Milestone 5 | Next milestone |
| Timetable solver (OR-Tools CP-SAT) | Milestone 6 | Option A locked joint sessions; H1-H14, S1-S6 |
| Exam scheduler | Milestone 7 | Half-capacity multi-room allocation; E1-E2 |
| Booking & Priority Engine | Milestone 8 | Priority ranks, role category caps, fest week overrides |
| Disruption & Minimal-Change Reopt | Milestone 9 | Minimal-move objective; stability tracking |
| Analytics & Schedule Query APIs | Milestone 10 | Timetable and booking query endpoints |
| Gemini AI Integration | Milestone 11 | Structured booking extraction with backend validation |
| Export Serializer & Validator | Milestone 12 | End-to-end verification against official validator.py |
| Campus Navigator | DEFERRED | Teammate-owned integration boundary only |
| Frontend | DEFERRED | Backend-first agreement |
