# CIT Campus Scheduling & Venue Management Platform
# API Specification & Backend Domain Contracts — v0.1

**Status:** Proposed contract for review; not frozen  
**Depends on:** Master PRD, Source Audit & Data Dictionary v0.1, ERD & PostgreSQL Schema Design v0.1  
**Competition source:** CrunchWeek Starter Pack, `cit-public-v1`  
**API base path:** `/api/v1`  
**Backend proposal:** FastAPI + Pydantic + SQLAlchemy + PostgreSQL  
**Architecture:** Modular monolith; asynchronous jobs for solver and map processing where needed

> **Authority rule:** The official starter-pack JSON, example export and `validator.py` define the competition input/output contract. This document defines the proposed application API and backend behaviour. Competition rules and additional product policies are distinguished. Do not treat this draft as a frozen API or generate production code from it until reviewed.

---

# 1. Goals and non-goals

## 1.1 Goals
- Define stable communication contracts between React frontend and FastAPI backend.
- Keep business rules in domain services, not UI components or AI prompts.
- Make every state-changing action authenticated, authorized, validated and audited.
- Support dataset import, timetable generation, exams, Spectra booking decisions, disruption repair and exact exports.
- Preserve version history and explain decisions.
- Make the backend testable independently of the frontend.
- Support Campus Navigator without coupling spatial data to timetable logic.
- Keep AI as an assistant that creates drafts and proposals; backend services remain authoritative.

## 1.2 Non-goals for this contract
- It does not decide final reviewer routing where organiser policy is not specified.
- It does not add new competition roles beyond Admin, Department Coordinator, Faculty and Club Representative.
- It does not introduce multi-room venue booking in the current competition export.
- It does not assume recurring bookings are supported merely because `series_id` exists.
- It does not guarantee indoor positioning without a positioning system.
- It does not prescribe the final visual design.

# 2. Global API conventions

## 2.1 Base URL and versioning
All application routes are under `/api/v1`. Breaking contract changes require a new API version or an explicitly versioned endpoint. Competition JSON export remains independent of the API version.

## 2.2 Authentication
Use an established identity provider or secure session/JWT mechanism. The backend derives the actor from the authenticated credential. Never trust `user_id`, `role`, `is_admin` or reviewer identity supplied by the client body.

For each request, resolve:
- authenticated user;
- active role assignments;
- role scope (institution, department, club, or resource);
- permissions for the action;
- actor identity for audit.

The starter pack contains requester labels and role strings, not authenticated accounts. Imported requests may initially have `requester_user_id = null`; do not fabricate an account mapping.

## 2.3 Request headers
Recommended:
- `Authorization: Bearer <token>` when bearer auth is selected.
- `Content-Type: application/json`.
- `Idempotency-Key: <opaque unique value>` for non-idempotent submissions, decisions, imports, generation jobs and publish actions.
- `If-Match: <resource-version>` or explicit `expected_version_id` for optimistic concurrency on updates.

## 2.4 Response envelope
Successful resource response:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_...",
    "api_version": "1"
  }
}
```

List response:

```json
{
  "data": [],
  "meta": {
    "request_id": "req_...",
    "page": 1,
    "page_size": 25,
    "total": 0
  }
}
```

Long-running operation response:

```json
{
  "data": {
    "job_id": "uuid",
    "status": "queued",
    "status_url": "/api/v1/jobs/uuid"
  },
  "meta": {"request_id": "req_..."}
}
```

Error response:

```json
{
  "error": {
    "code": "SCHEDULE_HARD_CONFLICT",
    "message": "The proposed assignment conflicts with another session.",
    "details": [
      {
        "rule_code": "H4",
        "entity_type": "room",
        "entity_id": "CR-101",
        "message": "Room CR-101 is occupied on MON P2."
      }
    ],
    "retryable": false
  },
  "meta": {"request_id": "req_..."}
}
```

Do not expose SQL errors, stack traces, secrets, provider tokens or raw internal exception details.

## 2.5 Pagination, filtering and sorting
- Default page size: 25; maximum: 100 (proposed).
- Stable sort order required for paginated results.
- Use explicit filters such as `status`, `department_id`, `day`, `role`, `dataset_version_id`.
- Avoid accepting raw SQL, arbitrary filter expressions or client-supplied ORM field names.

## 2.6 Time representation
- API timestamps: RFC 3339 / ISO-8601 with timezone offset.
- Dataset source times: preserve source clock values and timezone.
- Teaching slot: `day_code`, `start_period`, `duration_periods`.
- Booking range: `day_code`, `start_period`, `end_period` inclusive.
- Exam slot: `day_code`, `session_code` (`AM`/`PM`).
- Do not treat teaching period 10–13 as regular teaching periods; they are event periods in this dataset.

## 2.7 IDs
- Internal resource IDs: UUID strings.
- Competition IDs: preserve exact external IDs such as `F07`, `CR-102`, `CS202-T2`, `BR-07`.
- APIs may expose both: `id` (internal UUID) and `external_id` (competition/source ID).
- Do not construct IDs from names or array positions.

# 3. Roles and authorization contract

## 3.1 Official roles
The problem statement names four official roles:
- `admin`
- `department_coordinator`
- `faculty`
- `club` (Club Representative in UI)

Do not silently add a fifth competition role. Student timetable/navigation access may be a read-only product access policy or institution login mapping, but is not a starter-pack competition role.

## 3.2 Permission matrix (proposed baseline)

| Capability | Admin | Department Coordinator | Faculty | Club Representative |
|---|---:|---:|---:|---:|
| View institute timetable | Yes | Scoped / policy | No, own view by default | No |
| View own timetable | Yes | Yes | Yes | No |
| View room availability | Yes | Scoped | Read | Request-time |
| Import dataset | Yes | No | No | No |
| Generate institute timetable | Yes | No | No | No |
| Manually edit timetable | Yes | Scoped proposal only | No | No |
| Submit faculty unavailability | Yes | No | Own only | No |
| Submit department session change | Yes | Own department | No | No |
| Submit venue request | Yes | Department events | Faculty request category | Club category |
| Decide booking request | Authorised reviewer only | Only if explicit policy grants scope | No self-approval | No self-approval |
| Approve disruption repair | Admin | No | No | No |
| Publish timetable | Admin | No | No | No |
| Manage campus map | Admin / delegated map permission | No by default | No | No |

This matrix contains proposed operational defaults. The official problem statement does not fully specify reviewer routing or every view permission. Mark those as policy decisions until confirmed.

## 3.3 No-self-approval
A user must not approve their own request. Backend compares the authenticated requester account ID with the actor account ID. Imported records without an account mapping require an explicit policy path; do not assume a label match is definitive identity.

## 3.4 Scope enforcement
Department Coordinators may only act within their authorised department. A role name alone is not enough: the backend checks `role_assignments.scope_type/scope_id`. Never rely on hiding UI controls as authorization.

# 4. Domain state machines

## 4.1 Timetable version

```text
DRAFT -> GENERATING -> GENERATED -> VALIDATING -> VALIDATED
                                      |                |
                                      v                v
                                    FAILED          APPROVED -> PUBLISHED
                                                       |
                                                       v
                                                  SUPERSEDED
```

A solver run can fail or time out. A timetable with hard violations may exist as a draft/proposal but must not be marked publishable. The official validator is the competition acceptance authority.

## 4.2 Booking request and decision

Request workflow (application state):

```text
DRAFT -> SUBMITTED -> UNDER_REVIEW
                       |       |
                       v       v
                   APPROVED  REJECTED
                       |
             ALTERNATIVE_OFFERED (decision outcome)
```

Better model: keep the request lifecycle separate from the decision outcome. Recommended request states:
`draft`, `submitted`, `under_review`, `decided`, `cancelled`, `withdrawn`.

Decision statuses must match the competition export exactly:
`approved`, `rejected`, `alternative_offered`.

An alternative is an offered decision, not a final approval. If the requester must accept it operationally, track acceptance separately (`offered`, `accepted`, `declined`, `expired`) without changing the competition export status until policy says how accepted alternatives serialize. This acceptance rule is OPEN and needs organiser confirmation.

## 4.3 Approval task

`pending -> assigned -> in_review -> approved | rejected | changes_requested | cancelled`

An approval task is a workflow record; it is not the booking decision itself. One booking may have one or more approval stages if institution policy requires them.

## 4.4 Disruption/change proposal

```text
DRAFT -> SUBMITTED -> VALIDATING -> VALIDATED -> PENDING_ADMIN_APPROVAL
                                             -> REJECTED
PENDING_ADMIN_APPROVAL -> APPROVED -> APPLYING -> APPLIED
                                     -> FAILED
```

Only an Admin-approved repair may be applied, per the problem statement. A proposal is bound to a baseline timetable version and target dataset version.

## 4.5 Campus map version

`DRAFT -> PROCESSING -> REVIEW_REQUIRED -> VALIDATED -> APPROVED -> PUBLISHED -> SUPERSEDED`

A published map version is immutable. Corrections create a new version; rollback points publication to a previously approved version.

# 5. API endpoint catalogue

All paths below are relative to `/api/v1`. Endpoints are proposed. Exact response schemas are defined in later sections.

## 5.1 Authentication and current user
- `GET /auth/me` — current identity, roles and scopes.
- `POST /auth/session/refresh` — refresh session if using refresh-token auth.
- `POST /auth/logout` — revoke session if applicable.

## 5.2 Dataset and configuration
- `GET /datasets` — list imported datasets.
- `POST /datasets/import` — upload/import canonical JSON (Admin).
- `GET /datasets/{dataset_id}` — dataset metadata and import report.
- `GET /datasets/{dataset_id}/configuration` — calendar, priority order and role caps.
- `POST /datasets/{dataset_id}/activate` — select active dataset (Admin; concurrency protected).
- `GET /datasets/{dataset_id}/import-report` — counts, unresolved references and warnings.

## 5.3 Academic master data
- `GET /rooms`
- `GET /rooms/{room_id}`
- `GET /faculty`
- `GET /faculty/{faculty_id}`
- `GET /student-groups`
- `GET /courses`
- `GET /sessions`
- `GET /sessions/{session_id}`

Filters: `dataset_version_id`, `department`, `day` (only where relevant), `room_type`, `capacity_min`, `feature`, `faculty_id`, `group_id`, `course_id`, `kind`.

Master data mutation is not generally exposed for the imported competition dataset. Permanent changes should use the disruption/change-management workflow, not arbitrary CRUD.

## 5.4 Timetable
- `POST /timetables/generation-jobs`
- `GET /timetables`
- `GET /timetables/{timetable_id}`
- `GET /timetables/{timetable_id}/assignments`
- `GET /timetables/{timetable_id}/views/groups/{group_id}`
- `GET /timetables/{timetable_id}/views/faculty/{faculty_id}`
- `GET /timetables/{timetable_id}/views/rooms/{room_id}`
- `POST /timetables/{timetable_id}/validate`
- `POST /timetables/{timetable_id}/approve`
- `POST /timetables/{timetable_id}/publish`
- `POST /timetables/{timetable_id}/manual-assignments`
- `POST /timetables/{timetable_id}/clone`

## 5.5 Solver jobs
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/cancel` (only if solver implementation supports safe cancellation)
- `GET /solver-runs/{solver_run_id}`
- `GET /solver-runs/{solver_run_id}/metrics`

## 5.6 Bookings and approvals
- `POST /bookings/parse`
- `POST /bookings`
- `GET /bookings`
- `GET /bookings/{booking_id}`
- `POST /bookings/{booking_id}/submit`
- `POST /bookings/{booking_id}/cancel`
- `POST /bookings/{booking_id}/decisions`
- `POST /bookings/{booking_id}/alternative-response` (accept/decline; OPEN semantics)
- `GET /approvals/inbox`
- `GET /approvals/{approval_task_id}`
- `POST /approvals/{approval_task_id}/actions`

## 5.7 Exams
- `POST /exam-schedules/generation-jobs`
- `GET /exam-schedules`
- `GET /exam-schedules/{exam_schedule_id}`
- `POST /exam-schedules/{exam_schedule_id}/validate`
- `POST /exam-schedules/{exam_schedule_id}/approve`
- `POST /exam-schedules/{exam_schedule_id}/publish`

## 5.8 Disruptions and repair
- `POST /disruptions/import`
- `GET /disruptions`
- `GET /disruptions/{disruption_id}`
- `POST /disruptions/{disruption_id}/validate`
- `POST /change-proposals`
- `GET /change-proposals/{proposal_id}`
- `GET /change-proposals/{proposal_id}/diff`
- `POST /change-proposals/{proposal_id}/validate`
- `POST /change-proposals/{proposal_id}/approve`
- `POST /change-proposals/{proposal_id}/reject`
- `POST /change-proposals/{proposal_id}/apply`

## 5.9 Campus Navigator
- `GET /campus-map/versions`
- `GET /campus-map/current`
- `POST /admin/campus-map/assets`
- `POST /admin/campus-map/assets/{asset_id}/process`
- `GET /admin/campus-map/review-items`
- `POST /admin/campus-map/review-items/{item_id}/decision`
- `POST /admin/campus-map/versions/{version_id}/validate`
- `POST /admin/campus-map/versions/{version_id}/approve`
- `POST /admin/campus-map/versions/{version_id}/publish`
- `POST /admin/campus-map/rollback`
- `GET /places/search`
- `GET /places/{place_id}`
- `POST /navigation/routes`
- `GET /students/me/next-class`
- `POST /navigation/qr/resolve` (optional later phase)

## 5.10 AI assistant
- `POST /assistant/conversations`
- `GET /assistant/conversations/{conversation_id}`
- `POST /assistant/conversations/{conversation_id}/messages`
- `GET /assistant/tool-executions/{execution_id}`

## 5.11 Exports and validator
- `POST /exports/schedule`
- `POST /exports/schedule-after`
- `GET /exports/{export_id}`
- `POST /exports/{export_id}/validate`
- `GET /validation-runs/{validation_id}`

# 6. Detailed request and response contracts

## 6.1 Import canonical dataset

`POST /datasets/import` (multipart upload or signed storage reference; Admin only)

Request fields:
- `file`: `cit_public.json`
- `activate`: boolean, default false
- `dry_run`: boolean, default false
- `expected_dataset_id`: optional assertion

Response:
```json
{
  "data": {
    "import_job_id": "uuid",
    "dataset_version_id": "uuid",
    "external_dataset_id": "cit-public-v1",
    "status": "completed",
    "counts": {
      "rooms": 27,
      "faculty": 40,
      "student_groups": 14,
      "courses": 62,
      "sessions": 189,
      "booking_requests": 25,
      "cancellations": 1,
      "exams": 41
    },
    "warnings": []
  }
}
```

Rules:
- Validate root keys and field types before persistence.
- Validate all foreign references.
- Preserve original file/checksum.
- Import atomically.
- Never overwrite an existing immutable dataset version with same external ID and different content.
- `dry_run=true` performs validation and returns report without activating/persisting source records (temporary import-job record may be retained).
- Activation is a separate action unless explicitly requested and authorised.

## 6.2 Generate timetable

`POST /timetables/generation-jobs`

Request:
```json
{
  "dataset_version_id": "uuid",
  "base_timetable_version_id": null,
  "objective_profile": "balanced",
  "time_limit_seconds": 60,
  "random_seed": 17,
  "include_explanations": true
}
```

`objective_profile` is an application-level preset; exact weights must map to official S1–S6 penalties. Do not allow client to change hard constraints. For competition output, use official penalty weights.

Response:
```json
{
  "data": {
    "job_id": "uuid",
    "solver_run_id": "uuid",
    "status": "queued",
    "status_url": "/api/v1/jobs/uuid"
  }
}
```

Job status:
`queued`, `running`, `succeeded`, `failed`, `cancelled`, `timed_out`.

On success, job result includes:
- timetable_version_id;
- assigned session count;
- unassigned session IDs;
- hard violation count;
- S1–S6 penalty breakdown and total;
- solver objective and best bound if available;
- run duration;
- validator report ID.

The API must not return `succeeded/publishable` merely because OR-Tools found a feasible assignment. Run the official validator on the exact serialized schedule.

## 6.3 Read timetable view

`GET /timetables/{id}/views/groups/{group_id}?week=regular`

Response:
```json
{
  "data": {
    "timetable_version_id": "uuid",
    "group": {"id": "uuid", "external_id": "Y1-A", "name": "Year 1 A"},
    "items": [
      {
        "session_id": "uuid",
        "external_session_id": "MA101-AB-L1",
        "course": {"external_id": "MA101", "title": "Mathematics"},
        "day": "MON",
        "start_period": 2,
        "end_period": 2,
        "start_time": "09:00",
        "end_time": "10:00",
        "room": {"external_id": "LH-1", "name": "Lecture Hall 1"},
        "faculty": {"external_id": "F19", "name": "Faculty name"}
      }
    ]
  }
}
```

This is an illustrative response; values must be loaded from the database, not hardcoded. Similar views exist for faculty and rooms. Week 7 view incorporates only validated `fest_week.session_overrides`.

## 6.4 Manual assignment

`POST /timetables/{id}/manual-assignments`

Request:
```json
{
  "expected_timetable_version": 3,
  "assignments": [
    {
      "session_external_id": "MA101-AB-L1",
      "day": "MON",
      "start_period": 2,
      "room_external_id": "LH-1"
    }
  ],
  "reason": "Approved manual adjustment"
}
```

Rules:
- Admin may directly edit a draft; Department Coordinator may submit a scoped proposal only if permission policy grants it.
- Validate all hard constraints before persisting.
- Do not permit partial writes if any item in a batch fails unless API explicitly supports partial mode.
- Use optimistic concurrency; reject stale version with `409 VERSION_CONFLICT`.
- Record before/after assignments and actor.
- Run official validator on the resulting timetable version.

## 6.5 Parse natural-language booking

`POST /bookings/parse`

Request:
```json
{
  "text": "Need a room for 45 people on Tuesday 6 to 8 pm, projector please.",
  "locale": "en-IN",
  "reference_datetime": "2027-01-26T10:00:00+05:30",
  "dataset_version_id": "uuid"
}
```

Response:
```json
{
  "data": {
    "draft": {
      "attendance": 45,
      "duration_periods": 2,
      "windows": [
        {"day": "TUE", "from_period": 10, "to_period": 11}
      ],
      "needs": ["projector"],
      "room_types": ["classroom", "lecture_hall", "seminar_hall"],
      "mandatory_for_groups": []
    },
    "missing_fields": [],
    "assumptions": [],
    "conflicts": [],
    "follow_up": null,
    "requires_user_confirmation": true
  }
}
```

Rules:
- Parsing creates no booking and reserves no room.
- The structured draft is editable by the user.
- Resolve relative dates using explicit reference datetime and campus timezone; never rely on an ambiguous server clock.
- In Hindi/Hinglish, “kal” is interpreted as tomorrow for booking requests in the supplied examples, but display the resolved weekday and allow correction.
- Vague time/attendance must create a follow-up or a clearly displayed assumption.
- Named room conflicting with accessibility need should surface the conflict and offer valid alternatives; never silently replace the named room.
- AI output must pass Pydantic/domain validation; unknown values remain unresolved, not fabricated.

## 6.6 Create and submit booking

`POST /bookings`

Request:
```json
{
  "title": "Coding contest",
  "attendance": 60,
  "duration_periods": 3,
  "windows": [
    {"day": "THU", "from_period": 6, "to_period": 9}
  ],
  "room_types": ["lab_cs"],
  "needs": ["projector"],
  "mandatory_for_groups": [],
  "requested_room_external_id": null,
  "raw_text": "Can I get a lab with computers for a 3-hour coding contest on Thursday afternoon?"
}
```

Response returns draft `booking_id` and normalized fields. `POST /bookings/{id}/submit` moves it to `submitted`.

Rules:
- Backend derives role and effective category from authenticated actor and configured cap; do not trust client role/category.
- Validate day/period values against calendar.
- Validate `duration_periods` can fit at least one window.
- Preserve original raw text.
- Do not allocate a room on submit.
- Idempotency key prevents duplicate submissions.
- Imported starter requests are linked to user accounts only through explicit identity reconciliation.

## 6.7 Booking decision

`POST /bookings/{id}/decisions`

Request:
```json
{
  "status": "alternative_offered",
  "room_external_id": "AUD",
  "day": "THU",
  "start_period": 10,
  "end_period": 12,
  "reason": "The requested seminar hall is unavailable; the auditorium has the required capacity and stage."
}
```

For rejection, room/time fields are omitted and a reason is mandatory. For approval, allocation must fit entirely inside one requested window. For alternative, the allocation may be outside requested windows but must satisfy every other room/time/conflict requirement.

Backend checks:
1. authenticated reviewer;
2. reviewer role and scope;
3. no self-approval;
4. request not cancelled/withdrawn;
5. no stale request/decision version;
6. effective category and priority order from dataset;
7. room event permission, type, capacity and features;
8. requested/alternative time rules;
9. room unavailability;
10. current Week 7 timetable and existing bookings;
11. mandatory student groups free;
12. no overlap with higher-priority commitments under the priority policy;
13. decision and allocation persisted atomically;
14. audit record written in same transaction;
15. notification dispatched after commit.

A decision is not valid just because the UI shows a green availability indicator; re-check all conflicts inside the transaction.

## 6.8 Approval inbox and actions

`GET /approvals/inbox?status=pending`

Response returns tasks assigned to current actor or role scope, with request summary, deadline and permitted actions.

`POST /approvals/{task_id}/actions`

Request:
```json
{
  "action": "approve",
  "reason": "Room, capacity and priority checks passed.",
  "expected_task_version": 2
}
```

Allowed actions: `approve`, `reject`, `request_changes`, `reassign` (reassign requires permission). The action updates approval task/event and, when appropriate, creates booking decision. A reviewer cannot approve their own request. A role scope mismatch returns 403.

The exact reviewer routing matrix remains OPEN pending organiser policy.

## 6.9 Exam schedule generation

`POST /exam-schedules/generation-jobs`

Request:
```json
{
  "dataset_version_id": "uuid",
  "time_limit_seconds": 60,
  "random_seed": 17
}
```

Rules:
- Every source exam exactly once.
- Day and exam session from `calendar.exam_week`.
- Room must allow exams.
- Effective room capacity = `floor(room.capacity / 2)`.
- Multi-room allocations allowed; summed effective capacity must cover exam size.
- No room/group overlap in same day/session.
- Soft penalty: 5 per additional exam for a group on the same day.
- Preserve `duration_hours`; official validator does not explicitly compare it to the AM/PM window duration.
- Validate with official validator before marking complete.

## 6.10 Disruption import and change proposal

`POST /disruptions/import`

Accepts JSON matching the official `{"changes":[...]}` format and optional `id`, `dataset`, `description`.

Supported source change types:
- `faculty_unavailable`
- `room_unavailable`
- `add_faculty`
- `add_session`
- `remove_session`

The application validates each payload shape and all references. The official validator applies changes in order to a deep copy. Preserve that order.

`POST /change-proposals`

Request:
```json
{
  "disruption_set_id": "uuid",
  "baseline_timetable_version_id": "uuid",
  "objective": "minimize_moved_sessions_then_soft_penalty",
  "time_limit_seconds": 90
}
```

Repair acceptance:
- No hard violations under target dataset.
- Fixed sessions remain fixed.
- New session included exactly once.
- Removed session absent from target schedule.
- Minimize moved sessions, then optimize soft score (proposed lexicographic objective; align with organisers if they specify another).
- Compare baseline and proposed assignments.
- Explain moved, added, removed and infeasible sessions.
- Do not apply automatically.

`POST /change-proposals/{id}/approve` is Admin-only. `POST /apply` rechecks current baseline or revalidates, then atomically activates the derived dataset and repaired timetable. A stale baseline returns 409.

## 6.11 Campus map upload and publish

Upload:
`POST /admin/campus-map/assets` — multipart PDF/image/map data, Admin or delegated map permission.

Processing:
`POST /admin/campus-map/assets/{asset_id}/process` — creates background job; output is a draft map version and review items.

Review:
`GET /admin/campus-map/review-items`
`POST /admin/campus-map/review-items/{id}/decision`

Map validation checks:
- geometry validity;
- floor coordinate system;
- room/space references;
- entrance connectivity;
- graph edge endpoints;
- duplicate/isolated nodes;
- route reachability between published places;
- accessibility metadata;
- consistency of room links.

Publish requires authorised reviewer approval. Published map versions are immutable. Rollback republishes a previous approved version. AI extraction never publishes directly.

Student:
- `GET /places/search?q=CR-101`
- `GET /places/{place_id}`
- `POST /navigation/routes`
- `GET /students/me/next-class`

Route request:
```json
{
  "map_version_id": "uuid",
  "origin": {"type": "place", "place_id": "uuid"},
  "destination": {"type": "room", "external_id": "CR-101"},
  "travel_profile": "walking",
  "accessibility_required": false
}
```

Indoor starting location cannot be inferred without indoor positioning. If no known location is available, ask user to select a start point or scan a supported QR code. Do not pretend GPS can locate a user precisely inside a building.

## 6.12 AI assistant messages and tools

`POST /assistant/conversations/{id}/messages`

Request:
```json
{
  "message": "Move my Wednesday class because I will be on leave.",
  "context": {
    "module": "faculty_schedule",
    "dataset_version_id": "uuid"
  }
}
```

Backend flow:
1. Authenticate and authorize user.
2. Retrieve only permitted context.
3. Send constrained prompt/tools to Gemini.
4. Validate structured tool arguments.
5. Execute read-only or proposal-producing domain tools.
6. Validate proposals with deterministic backend services.
7. Ask user to confirm draft submission where needed.
8. Require normal approval workflow for state changes.
9. Record tool inputs, outputs, validation and audit.
10. Return explanation and next action.

Allowed tool families:
- `get_my_schedule`
- `get_available_rooms`
- `parse_booking_request`
- `validate_booking_candidate`
- `propose_schedule_change`
- `validate_timetable`
- `explain_validation_result`
- `search_campus_places`
- `calculate_campus_route`

Never expose unrestricted SQL, generic database mutation, approval bypass, direct timetable publish or map publish tools to Gemini.

## 6.13 Export and official validator

`POST /exports/schedule`

Request:
```json
{
  "dataset_version_id": "uuid",
  "timetable_version_id": "uuid",
  "exam_schedule_version_id": "uuid",
  "include_fest_week": true,
  "run_validator": true
}
```

Export adapter must emit exact competition fields:
- top level: `team`, `dataset_id`, `sessions`, `fest_week`, `exams`;
- session item: `session_id`, `day`, `start_period`, `room_id`;
- booking decision status exactly one of `approved`, `rejected`, `alternative_offered`;
- `end_period` inclusive;
- overrides only when allowed by validator;
- exam item: `exam_id`, `day`, `session`, `rooms`.

`POST /exports/schedule-after` additionally requires:
- baseline `schedule.json` export/version;
- approved disruption set;
- repaired timetable version;
- optional exam schedule version.

The application must invoke the supplied official validator (pinned copy/version) on the exact generated JSON. Save stdout/stderr or JSON report, validator version/hash, export checksum and hard/soft/booking metrics. Do not mark export as ready if hard violations remain. Do not edit exports by hand.

# 7. Domain service boundaries

Keep route handlers thin. Proposed services:

| Service | Responsibility |
|---|---|
| `DatasetImportService` | Parse, validate, import source JSON atomically |
| `CalendarService` | Resolve days/periods and time boundaries |
| `AuthorizationService` | Roles, scopes, permissions, no-self-approval |
| `AcademicReadService` | Read rooms/faculty/groups/courses/sessions |
| `TimetableGenerationService` | Create solver job and persist output version |
| `SchedulingConstraintService` | Hard/soft validation and conflict checks |
| `TimetableRepairService` | Apply disruptions to derived dataset and propose minimal repair |
| `BookingParserService` | Gemini parsing into editable draft |
| `BookingService` | Submit/cancel booking and effective category |
| `BookingDecisionService` | Priority, allocation, decision transaction |
| `ApprovalWorkflowService` | Tasks, reviewer routing, decisions and audit |
| `ExamSchedulingService` | Exam slot and multi-room allocation |
| `ExportService` | Exact competition JSON serialization |
| `OfficialValidatorService` | Invoke validator and persist report |
| `CampusMapIngestionService` | Asset processing and map draft creation |
| `CampusMapValidationService` | Geometry/graph validation |
| `NavigationRoutingService` | A*/Dijkstra over published graph |
| `AssistantOrchestrator` | Gemini tool orchestration; no direct DB writes |

# 8. Transaction boundaries and concurrency

## 8.1 Booking decision transaction
Within one transaction:
1. Lock booking request and relevant room/time allocation keys.
2. Confirm current request status and no cancellation.
3. Confirm actor permission and no-self-approval.
4. Recompute effective category from immutable dataset configuration.
5. Re-check room/time/capacity/features/group/timetable conflicts.
6. Re-check higher-priority booking allocations.
7. Insert decision and allocation.
8. Append approval/audit event.
9. Commit.
10. Send notifications asynchronously after commit.

If a concurrent decision reserves the same room/time first, the second transaction must fail or re-evaluate. Do not rely on an earlier availability search.

## 8.2 Timetable publish transaction
- Lock or compare-and-swap active timetable pointer.
- Verify target timetable version belongs to active dataset.
- Confirm official validator report has zero hard violations.
- Confirm approval actor is authorised.
- Update publication pointer and audit record atomically.
- Notify after commit.

## 8.3 Disruption apply transaction
- Verify Admin approval.
- Verify baseline timetable still current; otherwise revalidate proposal.
- Verify derived dataset and proposed timetable passed validator.
- Activate new dataset/timetable version atomically.
- Preserve old versions.
- Append audit record.
- Notify after commit.

## 8.4 Idempotency
For imports, solver generation, booking submission/decision, disruption application, map publishing and export generation, persist the idempotency key with actor and endpoint. Repeated identical requests return the original result; conflicting reuse returns `409 IDEMPOTENCY_KEY_REUSED`.

# 9. Standard error catalogue

| HTTP | Code | Meaning |
|---:|---|---|
| 400 | `INVALID_REQUEST` | Malformed payload or invalid basic value |
| 401 | `UNAUTHENTICATED` | Missing/invalid credentials |
| 403 | `FORBIDDEN` | Role/scope does not permit action |
| 404 | `RESOURCE_NOT_FOUND` | Resource absent or not visible |
| 409 | `VERSION_CONFLICT` | Stale timetable/request/map version |
| 409 | `RESOURCE_CONFLICT` | Room/time/resource already occupied |
| 409 | `IDEMPOTENCY_KEY_REUSED` | Key reused with different payload |
| 422 | `DOMAIN_VALIDATION_FAILED` | Domain rules failed |
| 422 | `SCHEDULE_HARD_CONFLICT` | Timetable violates hard constraints |
| 422 | `BOOKING_NOT_ELIGIBLE` | Cancelled/invalid/priority or booking constraints |
| 422 | `IMPORT_REFERENCE_ERROR` | Source reference unresolved |
| 422 | `MAP_VALIDATION_FAILED` | Geometry/graph/map validation failed |
| 429 | `RATE_LIMITED` | Request throttled |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `DEPENDENCY_UNAVAILABLE` | Solver/AI/storage dependency unavailable |

Validation errors should include field paths and rule codes, but never expose secrets or stack traces.

# 10. Background jobs and event handling

Use background jobs for:
- timetable solver;
- exam solver;
- disruption repair solver;
- official validator;
- large imports/exports;
- map OCR/vectorization/AI extraction;
- route graph validation.

MVP can use a simple worker process and database-backed job queue. Redis + Celery/RQ may be introduced if team needs reliable distributed jobs. Do not add queue infrastructure unless deployment and team capacity justify it.

Job record should include `queued_at`, `started_at`, `completed_at`, `status`, `progress`, `result_resource_id`, `error_code`, `safe_error_message`, retry count and worker version.

Notifications should be generated after durable state changes. Use an outbox pattern if reliability requires it.

# 11. Testing and acceptance strategy

## 11.1 Contract tests
- Request/response JSON matches OpenAPI schemas.
- Unknown fields rejected or handled according to explicit Pydantic policy.
- IDs and enum values remain stable.
- Pagination and filters are deterministic.
- Permission failures return correct status.

## 11.2 Source import tests
- Import canonical JSON.
- Counts match source counts.
- All references resolve.
- Nulls and empty arrays remain distinct.
- Dataset checksum retained.
- Duplicate import is idempotent or safely rejected.
- Invalid reference causes transaction rollback/quarantine, never phantom rows.

## 11.3 Timetable tests
- H1–H12 and H14 cases, including boundary tests.
- Basket sessions same time and group occupancy semantics.
- Multi-period overlap at every occupied period.
- Lunch crossing and P9 edge cases.
- Faculty and room unavailability.
- Hard constraints cannot be overridden by API or AI.
- Generated export passes official validator.

## 11.4 Booking tests
- All role caps and effective category behaviour.
- Same-category earlier timestamp wins.
- Cancelled request cannot be approved or alternative-offered (B3).
- Missing decisions/reasons are surfaced.
- Approved booking inside requested window; alternative can be outside.
- Room event permission/type/capacity/features.
- Mandatory group timetable clash.
- Existing Week 7 session and booking conflicts.
- Priority inversion detection.
- Concurrent requests cannot double-book same room/time.
- No-self-approval and department scope.

## 11.5 Exam tests
- Every exam exactly once.
- Invalid day/session.
- Half-capacity rounding down.
- Multi-room capacity sum.
- Room and group same-slot conflicts.
- Same-day group soft penalty.

## 11.6 Disruption tests
- Each supported change type.
- Change order preserved.
- Unknown change type rejected.
- Added/removed sessions represented correctly.
- Permanent derived dataset version.
- Sample disruption produces valid repaired schedule.
- Stale baseline requires revalidation.
- No apply without Admin approval.

## 11.7 Navigator tests
- WGS84 vs local coordinate separation.
- Broken graph endpoints.
- Isolated nodes and disconnected entrances.
- Route reachability.
- Accessibility filters.
- Published version immutability and rollback.
- AI map extraction cannot auto-publish.

## 11.8 End-to-end acceptance
1. Import `cit_public.json`.
2. Generate regular timetable.
3. Export `exports/schedule.json`.
4. Run official validator; record report.
5. Generate exam schedule and include it in export.
6. Process booking decisions and Week 7 overrides.
7. Apply `sample_disruption.json` through application.
8. Generate repaired schedule.
9. Export `exports/schedule_after.json`.
10. Run official validator with `--disruption` and `--baseline`.
11. Verify both outputs were generated by application and not hand-edited.

# 12. Implementation order after API contract approval

1. Confirm team stack and unresolved product policies.
2. Freeze schema and API v1 contracts.
3. Create repository and environment configuration.
4. Set up PostgreSQL, SQLAlchemy and Alembic.
5. Implement dataset import and exact source mapping.
6. Implement read APIs for rooms/faculty/groups/courses/sessions.
7. Implement official validator wrapper and report persistence.
8. Implement timetable generation and versioning.
9. Implement export adapter and prove validator compatibility.
10. Implement booking workflow and approvals.
11. Implement exams.
12. Implement disruptions and repair.
13. Build frontend vertical slices against the stable APIs.
14. Implement Campus Navigator.
15. Add Gemini assistant tools.
16. Complete integration/security/performance tests and deployment.

Do not wait until every backend module is done before starting UI work. Each feature is developed as a vertical slice: database → service/API → UI → tests. UI mock data is permitted for design, but integrated features must call real APIs.

# 13. Open decisions requiring confirmation

| ID | Question | Current treatment |
|---|---|---|
| API-01 | Team Python vs TypeScript capability? | FastAPI proposal remains conditional |
| API-02 | Exact booking reviewer routing? | Open; organiser policy needed |
| API-03 | Can alternative offers be accepted/declined in app? | Product extension; export semantics need confirmation |
| API-04 | Does Admin approve all timetable generation outputs before publish? | Proposed approval gate |
| API-05 | Can Department Coordinator make direct schedule edits or only propose? | Proposal-only default |
| API-06 | Who can see institute-wide timetable? | Scope policy needs confirmation |
| API-07 | Student authentication/read access mechanism? | Not a competition role; product policy |
| API-08 | Recurring bookings semantics? | Defer |
| API-09 | Booking multiple rooms? | Not current export contract |
| API-10 | Indoor positioning source? | Manual origin/QR optional; no GPS precision assumption |
| API-11 | Queue technology? | Start simple; add Redis only if justified |
| API-12 | Notification channels? | In-app first; email/push later if time |

# 14. Acceptance checklist for this milestone

- [ ] All endpoint paths and methods reviewed.
- [ ] Request and response schemas reviewed.
- [ ] Official roles and permission scopes approved.
- [ ] Booking reviewer routing clarified.
- [ ] Booking alternative acceptance semantics clarified.
- [ ] Timetable/exam/disruption workflows approved.
- [ ] Error codes and concurrency rules approved.
- [ ] AI tool authority boundaries approved.
- [ ] Export and validator integration contract approved.
- [ ] Team stack confirmed.
- [ ] OpenAPI generated from approved Pydantic schemas.
- [ ] API contract tests pass.

**Next milestone:** review and freeze architecture decisions, then produce an implementation-ready backend foundation specification and migration plan. No application code should be generated until the team confirms the unresolved decisions that materially affect schema and permissions.
