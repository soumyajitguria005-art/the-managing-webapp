# Requirements Traceability & Open Decisions

## A. Confirmed by supplied competition materials (re-check exact validator before coding)

| Requirement | Evidence location | Implementation target |
|---|---|---|
| Canonical input is JSON | Starter README and `data/cit_public.json` | Import module |
| Weekly timetable generation | Problem statement, examples, validator | Scheduling solver |
| Exams for following week | Problem statement, source exam records | Exam solver |
| Natural language booking requests | Problem statement, sample requests | Assistant parser + booking service |
| User reviews parsed request | Product workflow agreed | Booking draft/review API |
| Priority order and role caps | JSON `priority_order`, `role_category_cap` | Policy engine |
| Cancellation prevents approval | Source cancellation records/validator | Booking decision service |
| Faculty/room unavailability | JSON and CSVs | Constraint model |
| Disruption proposal before apply | Problem statement and sample disruption | Change management |
| Minimal movement | Problem statement | Re-optimization objective |
| Official export format | Starter README/examples/validator | Export serializer |
| No hard constraint violation | Validator | Independent validator |

## B. Approved project boundaries

- Backend and database first.
- No frontend implementation in this milestone.
- Campus Navigator/map implementation deferred to teammate.
- No dummy endpoints.
- AI proposals must be validated by backend code.
- Competition roles are admin, department_coordinator, faculty, club.
- No self-approval.
- Rejection reason required.
- Material edits trigger revalidation.
- Admin approval before applying disruption proposals under the current workflow.
- Department-specific scheduling must preserve unrelated department assignments and respect shared resources.

## C. Proposed engineering defaults

| Topic | Safe default | Why |
|---|---|---|
| Faculty resource | Institute-wide exclusive | Prevent cross-department double booking |
| Room resource | Institute-wide exclusive | Physical room is shared |
| Student group resource | Group-specific | Independent cohorts can attend concurrently |
| Joint session | One session linked to all groups | Prevent duplicate or partial occupancy |
| Department-scoped generation | Lock all outside-scope assignments | Avoid collateral timetable changes |
| Cross-department session movement | Admin approval if requester lacks all scopes | Protect other departments |
| Published timetable | Immutable version; create new version | Audit and rollback |
| Concurrency | Optimistic version check + DB transaction | Avoid stale apply |
| Import | Atomic and idempotent by source fingerprint/version | Safe re-import |
| AI | Parse/propose only; services authorize and validate | No bypass |

## D. Open decisions requiring organiser/team confirmation

1. **Department master data:** Is there a canonical list of department codes/names beyond the free-text values in source rows?
2. **Group overlap:** Are student groups mutually exclusive, or can one real student belong to multiple named groups (e.g. whole-year group plus lab section)?
3. **Joint teaching:** Is cross-department shared class represented in the competition data, or is this an additional application capability?
4. **Co-teaching:** Can a session have multiple faculty? Current source session record provides one faculty ID.
5. **Combined attendance:** For a joint class, should room capacity use sum of group sizes or a separately verified attendance value?
6. **Scoped generation:** Can a Department Coordinator generate only their department, and what happens to cross-department sessions?
7. **Global timetable publication:** Is Admin approval required for every generated timetable? Proposed safe default.
8. **Booking reviewer routing:** Who approves institute, department and club events? The source does not fully define routing.
9. **Alternative offers:** Expiry time, acceptance authority and whether an accepted alternative becomes approved automatically.
10. **Recurring booking series:** Exact expansion and cancellation semantics for `series_id`.
11. **Multi-room bookings:** Not clearly supported by current output contract; defer unless organiser confirms.
12. **Authentication:** Competition authentication requirements and institutional email verification.
13. **Student access:** Read-only timetable access is product policy, not a fifth competition role.
14. **Cross-listed courses:** Can a course have multiple department owners, or is ownership single with multi-department group participation?
15. **Department-specific calendar:** Is the calendar always institute-wide or can departments have separate teaching periods? Current fixture suggests one institute calendar.

Do not block safe implementation of confirmed requirements on every open question. Implement source-compatible behaviour and isolate optional features behind explicit configuration.
