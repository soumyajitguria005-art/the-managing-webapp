# Backend Modules & API Behaviour — Implementation Contract

This is a domain contract, not a claim that every endpoint currently exists. Implement only after the v0.4 audit and database hardening.

## 1. Proposed package layout

```text
backend/
  app/
    main.py
    core/                 # settings, logging, errors, security, permissions
    db/                   # SQLAlchemy base, sessions, transaction helpers
    modules/
      identity/
      institutes/
      departments/
      academic/
      datasets/
      calendar/
      scheduling/
      solver/
      exams/
      bookings/
      approvals/
      change_management/
      analytics/
      assistant/
      notifications/
      integrations/
    workers/
    schemas/
    tests/
  migrations/
```

Keep a modular monolith first. Do not split into microservices for hackathon scope.

## 2. Cross-cutting service requirements

Every write route:
- authenticates actor;
- checks active role and scope;
- validates Pydantic request;
- calls a service method;
- applies transaction/idempotency where needed;
- writes audit event;
- returns stable response schema.

Routes should be thin. Business rules belong in services/domain modules. Solver adapters must not depend on HTTP request objects.

## 3. Core API groups

### Identity and authorization
- `POST /auth/session` or identity-provider callback
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /me`
- `GET /me/permissions`

Use provider identity or secure password hashing as selected. Never store raw refresh tokens. Authorization uses active role assignments plus institute/department/club/resource scope.

### Dataset and imports
- `POST /admin/datasets/import` (file upload or registered source artifact)
- `GET /admin/datasets`
- `GET /admin/datasets/{dataset_id}`
- `POST /admin/datasets/{dataset_id}/validate`
- `POST /admin/datasets/{dataset_id}/activate`
- `GET /admin/datasets/{dataset_id}/import-report`

Import must be background-capable, idempotent and atomic. Activation is separate from import.

### Academic master data
- `GET /departments`
- `GET /academic/faculty`
- `GET /academic/student-groups`
- `GET /academic/courses`
- `GET /academic/rooms`
- `GET /academic/sessions`

All list APIs support dataset version and authorized scope filters. A filter is not permission enforcement; services must enforce scope.

### Timetable generation and publication
- `POST /timetables/generation-requests`
- `GET /timetables/generation-requests/{id}`
- `GET /timetables/versions/{id}`
- `POST /timetables/versions/{id}/validate`
- `POST /timetables/versions/{id}/submit-for-approval`
- `POST /timetables/versions/{id}/approve`
- `POST /timetables/versions/{id}/publish`
- `GET /timetables/views/group/{group_id}`
- `GET /timetables/views/faculty/{faculty_id}`
- `GET /timetables/views/room/{room_id}`
- `GET /timetables/views/department/{department_id}`

Generation request records scope, baseline version, preserve-outside-scope flag, solver settings and idempotency key. Generation returns a job/request ID; polling or notifications report completion. Never report a schedule as published merely because solving completed.

### Exams
- `POST /exams/schedule-requests`
- `GET /exams/schedule-requests/{id}`
- `POST /exams/schedules/{id}/validate`
- `POST /exams/schedules/{id}/submit-for-approval`
- `POST /exams/schedules/{id}/publish`

Exam room allocation may use multiple rooms when source/validator permits. Validate total allocated capacity and no room/group overlap.

### Bookings
- `POST /bookings/parse-request` (AI/parser returns draft only)
- `POST /bookings` (user-reviewed structured request)
- `GET /bookings`
- `GET /bookings/{id}`
- `POST /bookings/{id}/submit`
- `POST /bookings/{id}/decisions`
- `POST /bookings/{id}/alternatives`
- `POST /bookings/{id}/alternative-response`
- `POST /bookings/{id}/cancel`

Decision endpoint re-checks priority, role cap, cancellation, permissions, no-self-approval, availability and resource conflicts inside a transaction.

### Disruptions
- `POST /disruptions/import`
- `POST /disruptions/{id}/proposals`
- `GET /disruptions/proposals/{id}`
- `POST /disruptions/proposals/{id}/validate`
- `POST /disruptions/proposals/{id}/submit-for-approval`
- `POST /disruptions/proposals/{id}/approve`
- `POST /disruptions/proposals/{id}/apply`

Apply only after fresh baseline check, approval, full validation and atomic commit.

### Analytics
- `GET /analytics/room-utilisation`
- `GET /analytics/conflicts`
- `GET /analytics/pending-approvals`
- `GET /analytics/schedule-summary`

Metrics must identify dataset and timetable version. Do not mix draft and published schedules silently.

### Assistant
- `POST /assistant/conversations`
- `POST /assistant/conversations/{id}/messages`
- `POST /assistant/actions/{action_id}/confirm`

AI returns typed proposed actions; backend re-authenticates and revalidates on confirmation. No AI direct database access.

## 4. Error model

Use stable machine-readable error codes, e.g.:
- `VALIDATION_ERROR`
- `AUTHENTICATION_REQUIRED`
- `FORBIDDEN_SCOPE`
- `RESOURCE_CONFLICT`
- `HARD_CONSTRAINT_VIOLATION`
- `STALE_BASELINE`
- `INVALID_STATE_TRANSITION`
- `IDEMPOTENCY_KEY_REUSED`
- `DATASET_REFERENCE_MISMATCH`
- `SOLVER_INFEASIBLE`
- `APPROVAL_REQUIRED`

Return a correlation ID. Do not expose SQL or secrets in API errors.

## 5. Background processing

Use DB-backed jobs for initial scope; workers must claim jobs safely, retry transient errors, mark terminal failures and be idempotent. Keep solver runs isolated from HTTP request lifecycle. Redis/Celery/RQ may be introduced only if actual concurrency/throughput needs justify it.

## 6. Health and observability

- `GET /health/live`: process alive.
- `GET /health/ready`: DB and required dependencies reachable.
- Structured logs with correlation ID, actor, operation, dataset and version IDs.
- Metrics for solver duration/status, job retries, import failures, booking conflicts and API latency.
- Never log passwords, tokens or sensitive raw data.
