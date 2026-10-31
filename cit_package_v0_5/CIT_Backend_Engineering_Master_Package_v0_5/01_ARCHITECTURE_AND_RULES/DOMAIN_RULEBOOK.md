# CIT Backend Domain Rulebook

Status labels used throughout:
- **SOURCE-CONFIRMED:** explicitly present in the official starter pack or validator.
- **APPROVED PRODUCT RULE:** established in the project conversation/decision register.
- **PROPOSED ENGINEERING RULE:** recommended to make the system safe and implementable; confirm if it changes competition behaviour.
- **OPEN:** needs organiser/team decision.
- **DEFERRED:** intentionally outside current backend scope.

## 1. Core domain entities

### Institute
The tenant boundary. A deployment may serve one institute now but the data model should not assume every identifier is globally unique across all institutes.

### Department
An institute-owned organizational unit. It owns academic offerings and scopes department-coordinator authority. Department membership does not isolate shared resources.

### Dataset version
An immutable imported snapshot of canonical competition data. Each timetable, solver run, booking evaluation and export must identify the dataset version it was computed against.

### Student group
The smallest competition-provided cohort unit that is scheduled as a whole (for example, a named department/year/section group). A group is a schedulable resource. Do not infer individual student overlap unless individual membership data exists.

### Course
An academic subject. Course ownership department is administrative. A course may be cross-listed or taught to groups from multiple departments if explicitly modelled; do not assume course department and participating student-group departments must always match.

### Teaching session
One schedulable occurrence/requirement for a course activity (lecture/tutorial/lab etc.). It has one or more participating student groups, one or more faculty assignments, duration, permitted room types, accessibility requirements, optional fixed slot and optional elective basket key.

### Faculty
An institute-level human resource. Department affiliation is not a partition of availability. A faculty member may have a primary department and, where needed, multiple department affiliations. A scheduled teaching session consumes the faculty member institute-wide.

### Room
An institute-level physical resource. Room capacity, type, permitted uses, features, accessibility and unavailability are checked globally.

### Timetable version
An immutable candidate snapshot of assignments for one dataset/calendar version. Drafts are not published schedules. Publishing requires validation and the configured approval gate.

### Booking request
A request for a venue/time. A booking decision consumes room time and, where mandatory groups are specified, those group resources. If a booking uses faculty/staff, the resource must be represented explicitly before conflict checking.

## 2. Resource conflict model

Every scheduled activity is converted into atomic occupied periods. For each period:
- room resource: one room;
- faculty resource: every assigned faculty member;
- student-group resource: every mandatory/participating group.

Two activities conflict if they occupy the same resource at the same institute-local day/period. The resource key is `(resource_type, resource_id, day_code, period_number)` within a timetable version (and any required schedule scope). Department code is deliberately not part of the conflict key.

This means:
- CSE-A and ECE-A can be simultaneous if they are distinct groups, rooms and faculty.
- Two CSE groups sharing one teacher cannot overlap.
- CSE and ECE classes sharing one room cannot overlap.
- A joint CSE+ECE session occupies both group resources and therefore conflicts with a simultaneous CSE-only or ECE-only class for either participating group.
- A teacher's department affiliation never makes their availability independent by department.

## 3. Hard constraints

The official validator is authoritative. Based on the supplied competition description and source, expected hard constraints include:
- each required teaching session appears exactly once;
- no faculty overlap;
- no participating/mandatory student-group overlap;
- no room overlap;
- room capacity and allowed room type/use;
- faculty and room unavailability;
- accessibility compatibility;
- no crossing the lunch break;
- lab duration/start restrictions;
- elective basket sessions follow the source's same-slot/different-room/no-overlap semantics;
- faculty daily-hour limit;
- fixed slots preserved;
- booking approvals do not conflict with sessions, bookings or mandatory groups;
- cancelled requests are never approved;
- authorization and approval rules cannot be bypassed.

Before implementation, inspect `validator.py` to confirm exact scoring and edge-case semantics. Do not infer exact formulas from prose summaries.

## 4. Soft objectives

Previously identified objective families include faculty preferences, group gaps, long daily loads, repeated same-course lectures, room utilisation and late-period usage. Exact weights and formulas must be copied from the official validator, not re-created from this summary.

Use a lexicographic or safely scaled objective strategy so hard feasibility is never traded for a soft-score improvement. Persist component scores and the validator version.

## 5. Role and authorization model

Competition roles are exactly:
- `admin`
- `department_coordinator`
- `faculty`
- `club`

"Club Representative" is a display label, not a fifth role.

A user may hold multiple active role assignments with different scopes. Scopes can include institute, department, club or resource as supported by the existing design. Enforce the scope at service layer and test it. A department coordinator's default scope is their assigned department, not all departments.

No self-approval. Admin approval is required for publication and applying a disruption proposal under the current proposed workflow. Department-scoped edits must not silently affect other departments.

## 6. Booking priority and approval

The source priority order is:
1. exam
2. regular_session
3. institute_event
4. guest_lecture
5. department_event
6. club_event

The dataset provides role-category caps. Same-category tie-breaking uses earlier submission timestamp. The official validator contains category weights and must be inspected for exact ranking implementation.

- Cancelled requests cannot be approved.
- No self-approval.
- Every rejection has a reason.
- Alternative offers have explicit expiry/acceptance semantics (OPEN).
- A booking decision is immutable history; a new decision supersedes the previous effective decision.
- Booking allocations must be validated atomically against all occupied resources.
- Approval routing is not fully specified by source; do not invent a definitive routing matrix.

## 7. Disruptions and minimal change

Disruptions include faculty unavailability, room closure and added/removed sessions where supported by the source. A disruption first creates a proposal. Solver output must be independently validated. Show every moved/added/removed session and the reason. Minimize movement without violating hard constraints. Admin approval precedes application. Applying the approved proposal must be atomic and version-checked.

## 8. Imports and exports

Canonical input is `cit_public.json`; CSVs are supporting material and may omit root-level policy/calendar configuration. Preserve raw source snapshot and SHA-256 fingerprint. Import all records in a single transaction; failed import rolls back. A dataset version becomes active only after import and validation succeed.

The application generates the required export JSON; do not hand-edit it. Compare output with examples and official validator. Do not assume internal UUIDs are export identifiers; preserve original external IDs.

## 9. Time and recurrence

Use institute timezone from dataset/configuration (current fixture is Asia/Kolkata). Store event timestamps timezone-aware; calendar periods are local wall-clock times tied to a calendar version.

Recurring booking `series_id` exists in source, but recurrence expansion/cancellation semantics remain OPEN. Do not assume recurrence means a weekly repeating reservation without explicit confirmation.
