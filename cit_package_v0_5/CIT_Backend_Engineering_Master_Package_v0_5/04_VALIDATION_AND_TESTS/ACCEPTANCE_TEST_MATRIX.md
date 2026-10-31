# Acceptance Test Matrix — CIT Backend & Database

All tests must be automated where practical. Use synthetic test fixtures in addition to the official fixture. The official validator remains an independent final check.

## A. Department and shared-resource scheduling

| ID | Scenario | Expected result |
|---|---|---|
| DEPT-001 | CSE group and ECE group, different faculty and rooms, same period | Allowed |
| DEPT-002 | CSE and ECE sessions use same faculty at same period | Rejected as faculty conflict |
| DEPT-003 | CSE and ECE sessions use same room at same period | Rejected as room conflict |
| DEPT-004 | CSE-only session and ECE-only session use distinct groups/resources | Both can schedule simultaneously |
| DEPT-005 | One joint CSE+ECE session links both groups | One assignment consumes both groups |
| DEPT-006 | CSE-only session overlaps joint CSE+ECE session | Rejected due to CSE group conflict |
| DEPT-007 | ECE-only session overlaps joint CSE+ECE session | Rejected due to ECE group conflict |
| DEPT-008 | Joint session room capacity below combined required attendance | Rejected |
| DEPT-009 | Department-scoped CSE generation | ECE-only baseline assignments remain unchanged |
| DEPT-010 | CSE scope includes a joint session | Joint session is detected and treated as cross-department |
| DEPT-011 | Scoped CSE request tries to move joint session without authority | Blocked or escalated to Admin approval |
| DEPT-012 | Department coordinator queries ECE-only records | Forbidden unless separately scoped |
| DEPT-013 | CSE scoped solver produces resource collision with locked ECE assignment | Candidate rejected |
| DEPT-014 | Publish scoped timetable | Full institute resource validation runs |
| DEPT-015 | Faculty has multiple department affiliations | Still one global faculty resource |
| DEPT-016 | Two sessions use same logical cohort through overlapping group aliases | Must be rejected if overlap model is configured; otherwise data contract must prevent ambiguous overlapping groups |

## B. Source import and data integrity

| ID | Scenario | Expected result |
|---|---|---|
| IMP-001 | Valid canonical JSON | Imports successfully |
| IMP-002 | Missing required root key | Validation fails; no rows persisted |
| IMP-003 | Unknown extra field | Preserved in source snapshot; strictness policy explicit |
| IMP-004 | Duplicate external ID | Import rejected |
| IMP-005 | Session references unknown course/faculty/group | Import rejected |
| IMP-006 | Session group belongs to another dataset | DB FK rejects |
| IMP-007 | Same source fingerprint submitted twice | Idempotent documented behaviour |
| IMP-008 | Failure midway through import | Entire transaction rolls back |
| IMP-009 | Dataset validation fails | Dataset cannot become active |
| IMP-010 | Activate new dataset concurrently | Exactly one active dataset per institute |
| IMP-011 | Re-import as new version | External IDs preserved; no cross-version FKs |
| IMP-012 | CSV missing calendar/policy data | Canonical JSON remains source of truth |

## C. Scheduling solver

- Exactly one assignment per required session.
- All fixed slots preserved.
- Faculty no-overlap across departments.
- Student-group no-overlap.
- Room no-overlap.
- Capacity/type/accessibility/unavailability.
- Lunch boundary and lab starts/durations.
- Elective basket rules exactly match validator.
- Faculty daily load.
- Soft objective values match validator.
- Infeasible model reports meaningful cause category and does not publish partial result.
- Determinism test with fixed solver seed/config.

## D. Booking

- Priority order and category caps match source.
- Same-category timestamp tie-break deterministic.
- Cancelled booking never approved.
- No self-approval.
- Rejection requires reason.
- Requester cannot edit after decision except through explicit revision flow.
- Room and mandatory-group conflicts are rechecked in transaction.
- Two concurrent approvals for same room/slot: at most one succeeds.
- Alternative acceptance rechecks availability and expiry.
- Stale decision rejected.
- Department/club scope enforced.
- No booking can override regular sessions or exams contrary to source priority/validator.

## E. Disruptions

- Faculty leave triggers affected-session detection.
- Room closure triggers affected-session detection.
- New session added and scheduled exactly once.
- Unaffected assignments remain unchanged where feasible.
- Movement objective minimizes changed assignments.
- Infeasible proposal explains blocking constraints.
- Approval required before apply.
- Stale baseline proposal cannot apply.
- Failed apply rolls back completely.
- Full validator passes after apply.

## F. Exams

- All exam records scheduled.
- No overlapping mandatory groups.
- Room capacity uses official exam capacity rule.
- Multiple room allocations sum to required capacity.
- Room/faculty constraints applied if applicable.
- Exam sessions use configured exam days and time windows.
- Official export and validator pass.

## G. Security and API

- Unauthorized request rejected.
- Cross-department read/write denied.
- Role revocation takes effect.
- No self-approval.
- Idempotency same key/same payload returns same result.
- Same key/different payload returns conflict.
- SQL injection payload treated as data.
- Error response does not leak SQL, secrets or stack traces.
- Audit event records actor, action, target, before/after, reason and correlation ID.
- Health readiness fails when DB unavailable.

## H. Release gate

A milestone is complete only when:
1. automated tests pass;
2. PostgreSQL integration tests pass against a real PostgreSQL instance;
3. official validator passes for required export;
4. migration upgrade and fresh-install paths pass;
5. no critical security or data-integrity defect remains;
6. implementation status and known limitations are updated.
