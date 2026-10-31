# CIT Campus Scheduling & Venue Management Platform
# Source Data Audit and Data Dictionary — v0.1

**Status:** Working technical foundation; not yet schema-frozen  
**Source package:** CrunchWeek Starter Pack  
**Dataset:** `cit-public-v1`  
**Institution:** Chilika Institute of Technology (fictional)  
**Purpose:** Define the exact source-data contract before designing PostgreSQL tables, backend APIs, solver models or frontend integration.

> **Authority rule:** The official starter-pack JSON and `validator.py` define the competition input/output contract. This document distinguishes source facts from proposed application architecture. Where the validator does not enforce a business rule, this document says so rather than pretending it does.

## 1. Executive summary

The starter pack provides one canonical JSON dataset, supporting CSV extracts, an official Python validator, a sample disruption, sample natural-language booking requests and an example schedule export.

The application must import the dataset and live change files rather than hard-code their contents. Judges may reset the application, generate a timetable and apply their own change files. Both required export files must be produced by the application, not edited by hand.

## 2. Verified source inventory

| Collection | Count | Meaning |\n|---|---:|---|\n| `rooms` | 27 | Rooms |\n| `room_unavailability` | 2 | Room unavailability entries |\n| `faculty` | 40 | Faculty |\n| `student_groups` | 14 | Student groups |\n| `courses` | 62 | Courses |\n| `sessions` | 189 | Schedulable sessions |\n| `booking_requests` | 25 | Spectra booking requests |\n| `cancellations` | 1 | Cancellations |\n| `exams` | 41 | Midsem exams |\n
Other verified facts:
- 189 sessions represent 243 teaching hours per week.
- One booking request is cancelled in the public dataset.
- The README states that a zero-hard-violation timetable exists.
- JSON is the complete canonical source; CSVs are supporting views and omit root-level configuration.
- Root configuration includes the calendar, priority order and role-category caps.

## 3. Canonical source and import rules

### 3.1 Canonical file
`data/cit_public.json` is authoritative. CSVs must not be used as the only import source because they do not represent all configuration keys and nested arrays.

### 3.2 Import principles
1. Preserve the original source file and its checksum.
2. Parse and validate the complete JSON before writing any records.
3. Import in a transaction; either the dataset version is fully imported or none of it is.
4. Preserve external IDs exactly (`F01`, `CR-101`, `MA101`, `BR-01`, etc.).
5. Preserve nullable values (`null`) distinctly from empty arrays (`[]`).
6. Preserve original timestamps and offsets.
7. Preserve original raw natural-language booking text.
8. Record dataset version and import provenance.
9. Do not silently coerce invalid references into new records.
10. Produce an import report with counts, warnings, rejected records and unresolved references.

### 3.3 Recommended dataset-version model
A `dataset_versions` record should identify each imported dataset with:
- internal UUID
- external `dataset_id`
- source filename and SHA-256 checksum
- imported timestamp and importing user/system
- import status
- schema version (our internal mapping version)
- source metadata and import report reference

A dataset version is immutable after import. Corrections or disruptions create a new derived version, not an in-place rewrite of historical source data.

## 4. Full source data dictionary

The following tables document the source fields. “Required” means present in the supplied public JSON shape; optional/nullable semantics are identified separately.

### `Root.dataset_id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Dataset identity/version token. Current value cit-public-v1.\n- **Implementation / validation:** Unique dataset identifier; preserve exactly in exports.\n\n### `Root.institute`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Institute display name; source marks institution fictional.\n- **Implementation / validation:** Configuration metadata.\n\n### `Root.calendar.days`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Allowed teaching weekdays, MON–FRI.\n- **Implementation / validation:** Do not hardcode weekdays; read from imported calendar.\n\n### `Root.calendar.periods[].id`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Period identifier 1–13.\n- **Implementation / validation:** Unique within calendar; periods 1–9 teaching, 10–13 event-only in this dataset.\n\n### `Root.calendar.periods[].start/end`\n- **Type:** HH:MM string\n- **Presence:** Required\n- **Meaning:** Local clock boundaries for each period.\n- **Implementation / validation:** Store as time or normalized minute offsets; preserve source values for export.\n\n### `Root.calendar.periods[].teaching`\n- **Type:** boolean\n- **Presence:** Required\n- **Meaning:** Whether period is a teaching period.\n- **Implementation / validation:** Solver must use this flag, not infer solely from period number.\n\n### `Root.calendar.lunch.after_period`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Lunch follows the specified period; current value 5.\n- **Implementation / validation:** Validator rejects teaching sessions crossing P5/P6.\n\n### `Root.calendar.lunch.start/end`\n- **Type:** HH:MM string\n- **Presence:** Required\n- **Meaning:** Lunch interval boundaries.\n- **Implementation / validation:** Calendar configuration; not a session.\n\n### `Root.calendar.lab_start_periods`\n- **Type:** array<integer>\n- **Presence:** Required\n- **Meaning:** Permitted lab start periods; current [2,6].\n- **Implementation / validation:** Hard scheduling rule for kind=lab.\n\n### `Root.calendar.event_only_periods`\n- **Type:** array<integer>\n- **Presence:** Required\n- **Meaning:** Periods available for events; current [10,11,12,13].\n- **Implementation / validation:** Events can use evening periods; regular sessions cannot.\n\n### `Root.calendar.fest_week`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Human-readable fest-week label.\n- **Implementation / validation:** Metadata; Week 7 Spectra '27 in current source.\n\n### `Root.calendar.exam_week.days`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Allowed exam days; current MON–SAT.\n- **Implementation / validation:** Separate from teaching calendar days.\n\n### `Root.calendar.exam_week.sessions[].id/start/end`\n- **Type:** string / HH:MM\n- **Presence:** Required\n- **Meaning:** Exam session identifier and clock window; AM and PM.\n- **Implementation / validation:** Exam schedule slot is (day, session_id), not teaching period.\n\n### `Root.priority_order`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Ordered request categories, highest priority first.\n- **Implementation / validation:** Do not hardcode; effective category determined using role cap.\n\n### `Root.role_category_cap`\n- **Type:** object<string,string>\n- **Presence:** Required\n- **Meaning:** Maximum category a role may claim.\n- **Implementation / validation:** Role caps apply to requested category via effective_category().\n\n### `rooms[].id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Stable room code, e.g. AUD, CR-101.\n- **Implementation / validation:** Primary key; referenced by sessions, unavailability, booking allocations and exam allocations.\n\n### `rooms[].name`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Human-readable room name.\n- **Implementation / validation:** Display field.\n\n### `rooms[].building`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Building name as provided by source.\n- **Implementation / validation:** No separate building entity in starter data; normalize to buildings only if campus-map records are verified.\n\n### `rooms[].type`\n- **Type:** enum-like string\n- **Presence:** Required\n- **Meaning:** Room category (classroom, lecture_hall, auditorium, seminar_hall, outdoor, lab_cs, lab_elec, lab_phy, workshop, lab_civil).\n- **Implementation / validation:** Use source value; don't infer types from room name.\n\n### `rooms[].capacity`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Normal room capacity.\n- **Implementation / validation:** For exams, validator uses floor(capacity/2) per room.\n\n### `rooms[].features`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Room equipment/features, e.g. projector, stage, pa_system, ac.\n- **Implementation / validation:** Normalize to room_feature join table or JSONB; retain exact source feature codes.\n\n### `rooms[].accessible`\n- **Type:** boolean\n- **Presence:** Required\n- **Meaning:** Whether room is accessible.\n- **Implementation / validation:** Booking feature matching treats accessible as a feature when true.\n\n### `rooms[].allowed_uses`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Allowed activity categories, e.g. lecture, tutorial, lab, exam, event.\n- **Implementation / validation:** Hard gate for exam/event allocation; source README notes seminar halls and OAT do not host regular classes.\n\n### `room_unavailability[].room_id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Room that is unavailable.\n- **Implementation / validation:** FK to rooms.id.\n\n### `room_unavailability[].day`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Unavailable weekday.\n- **Implementation / validation:** Validate against calendar days.\n\n### `room_unavailability[].periods`\n- **Type:** array<integer>\n- **Presence:** Required\n- **Meaning:** Unavailable period identifiers.\n- **Implementation / validation:** One record can represent multiple periods; recommended relational expansion to one row per period.\n\n### `room_unavailability[].reason`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Reason for unavailability.\n- **Implementation / validation:** Preserve for UI and audit.\n\n### `faculty[].id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Faculty identifier, e.g. F01.\n- **Implementation / validation:** Primary key.\n\n### `faculty[].name`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Faculty display name.\n- **Implementation / validation:** Personal data; restrict to authorised academic users.\n\n### `faculty[].department`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Department code.\n- **Implementation / validation:** Department reference; source does not provide a separate department master table.\n\n### `faculty[].max_hours_per_day`\n- **Type:** integer\n- **Presence:** Required in source; validator fallback 4\n- **Meaning:** Hard daily teaching limit.\n- **Implementation / validation:** Persist explicitly; do not silently replace missing values with fallback.\n\n### `faculty[].needs_accessible`\n- **Type:** boolean\n- **Presence:** Required\n- **Meaning:** Faculty accessibility requirement.\n- **Implementation / validation:** Room accessibility is checked for sessions only when session.needs_accessible is true; faculty flag is source metadata and should be mapped carefully. Do not assume validator enforces it.\n\n### `faculty[].unavailable[].day/periods/reason`\n- **Type:** object\n- **Presence:** Optional/repeatable\n- **Meaning:** Faculty time unavailability with reason.\n- **Implementation / validation:** Expand periods into individual normalized rows; enforce as hard constraint.\n\n### `faculty[].preferences[].type/days/periods/note`\n- **Type:** object\n- **Presence:** Optional/repeatable\n- **Meaning:** Soft preference; documented avoid type.\n- **Implementation / validation:** Current sample may be empty for some/all faculty. For avoid preference, penalty is 2 per overlapping hour.\n\n### `student_groups[].id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Student group identifier, e.g. Y1-A.\n- **Implementation / validation:** Primary key; referenced by sessions and exams.\n\n### `student_groups[].name`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Display name.\n- **Implementation / validation:** Display field.\n\n### `student_groups[].year`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Academic year.\n- **Implementation / validation:** Filter/grouping field.\n\n### `student_groups[].department`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Department code; COMMON appears for first-year shared groups.\n- **Implementation / validation:** Department reference or code.\n\n### `student_groups[].size`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Nominal group size.\n- **Implementation / validation:** Source metadata; session.size and exam.size are the attendance/capacity values used by validator.\n\n### `student_groups[].needs_accessible`\n- **Type:** boolean\n- **Presence:** Required\n- **Meaning:** Group accessibility requirement.\n- **Implementation / validation:** Validator uses session.needs_accessible and booking needs; it does not directly inspect group flag in check_timetable.\n\n### `courses[].id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Course identifier.\n- **Implementation / validation:** Primary key; referenced by sessions and exams.\n\n### `courses[].title`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Course title.\n- **Implementation / validation:** Display field.\n\n### `courses[].department`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Owning department code.\n- **Implementation / validation:** Academic filtering.\n\n### `courses[].year`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Course year.\n- **Implementation / validation:** Academic filtering.\n\n### `courses[].lecture_hours/tutorial_hours/lab_blocks`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Reference workload counts.\n- **Implementation / validation:** These are reference data; solver schedules sessions, not course-hour totals directly.\n\n### `sessions[].id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Unique schedulable teaching unit.\n- **Implementation / validation:** Primary key; exactly one assignment required.\n\n### `sessions[].course_id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Owning course.\n- **Implementation / validation:** FK to courses.id.\n\n### `sessions[].kind`\n- **Type:** enum-like string\n- **Presence:** Required\n- **Meaning:** lecture, tutorial or lab.\n- **Implementation / validation:** Lab start restriction applies when kind=lab.\n\n### `sessions[].groups`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Every student group that must attend.\n- **Implementation / validation:** Many-to-many relationship; use session_groups join table.\n\n### `sessions[].faculty_id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Assigned faculty member.\n- **Implementation / validation:** FK to faculty.id; source preassigns faculty.\n\n### `sessions[].size`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Number of attendees for this session.\n- **Implementation / validation:** Used for room capacity; not necessarily sum of group sizes.\n\n### `sessions[].duration`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Number of consecutive periods occupied.\n- **Implementation / validation:** One hour per period in teaching timetable.\n\n### `sessions[].room_types`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Allowed room types.\n- **Implementation / validation:** Session can use any room whose type is in this array.\n\n### `sessions[].needs_accessible`\n- **Type:** boolean\n- **Presence:** Required\n- **Meaning:** Whether assigned room must be accessible.\n- **Implementation / validation:** Hard constraint H10.\n\n### `sessions[].basket_slot`\n- **Type:** string|null\n- **Presence:** Nullable\n- **Meaning:** Elective basket identifier.\n- **Implementation / validation:** Sessions with same basket_slot must have identical day and start period; basket sessions in same slot are treated as one group-occupancy key.\n\n### `sessions[].fixed_slot`\n- **Type:** object|null\n- **Presence:** Nullable\n- **Meaning:** Fixed day and start_period.\n- **Implementation / validation:** When present, exact day and start period must be preserved (H14).\n\n### `booking_requests[].id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Booking request identifier.\n- **Implementation / validation:** Primary key.\n\n### `booking_requests[].submitted_at`\n- **Type:** ISO-8601 datetime with offset\n- **Presence:** Required\n- **Meaning:** Submission timestamp.\n- **Implementation / validation:** Tie-breaker for same effective priority; earlier timestamp wins.\n\n### `booking_requests[].requester`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Requester display/entity name.\n- **Implementation / validation:** Source data does not include an authenticated user ID; app must link imported requester to account where possible without inventing identity.\n\n### `booking_requests[].role`\n- **Type:** enum-like string\n- **Presence:** Required\n- **Meaning:** admin, department_coordinator, faculty, club.\n- **Implementation / validation:** Used with role_category_cap.\n\n### `booking_requests[].department`\n- **Type:** string|null\n- **Presence:** Nullable\n- **Meaning:** Department context for request.\n- **Implementation / validation:** No department FK is guaranteed by source; validate against configured department list if introduced.\n\n### `booking_requests[].requested_category`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Requested event category.\n- **Implementation / validation:** Effective category is adjusted by role cap.\n\n### `booking_requests[].title`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Booking/event title.\n- **Implementation / validation:** Display field.\n\n### `booking_requests[].attendance`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Expected attendance.\n- **Implementation / validation:** Room capacity requirement.\n\n### `booking_requests[].duration_periods`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Requested consecutive period count.\n- **Implementation / validation:** Allocated inclusive range must have exactly this length.\n\n### `booking_requests[].windows[].day/from_period/to_period`\n- **Type:** object\n- **Presence:** Required/repeatable\n- **Meaning:** Allowed requested windows; end period inclusive.\n- **Implementation / validation:** Approved bookings must fit entirely inside one window; alternative_offered may be outside.\n\n### `booking_requests[].room_types`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Acceptable room types.\n- **Implementation / validation:** Candidate room filter.\n\n### `booking_requests[].needs`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Required room features; accessible is synthesized from room.accessible.\n- **Implementation / validation:** All requested needs must be satisfied.\n\n### `booking_requests[].requested_room`\n- **Type:** string|null\n- **Presence:** Nullable\n- **Meaning:** Preferred room, may be null or unknown.\n- **Implementation / validation:** Preference only; validator does not require this exact room.\n\n### `booking_requests[].mandatory_for_groups`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Groups that must be free during booking.\n- **Implementation / validation:** Conflict check against Week 7 timetable.\n\n### `booking_requests[].series_id`\n- **Type:** string|null\n- **Presence:** Nullable\n- **Meaning:** Recurring booking series reference.\n- **Implementation / validation:** Starter schema only; recurring allocation semantics not specified by validator.\n\n### `booking_requests[].raw_text`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Original natural-language request.\n- **Implementation / validation:** Keep immutable for audit, parsing evaluation and AI provenance.\n\n### `cancellations[].request_id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Cancelled booking request.\n- **Implementation / validation:** FK to booking_requests.id; cancellation blocks approval/alternative.\n\n### `cancellations[].cancelled_at`\n- **Type:** ISO-8601 datetime with offset\n- **Presence:** Required\n- **Meaning:** Cancellation timestamp.\n- **Implementation / validation:** Audit field.\n\n### `cancellations[].by`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Cancelling entity label.\n- **Implementation / validation:** Source doesn't provide account ID.\n\n### `cancellations[].note`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Cancellation reason/note.\n- **Implementation / validation:** Preserve.\n\n### `exams[].id`\n- **Type:** string\n- **Presence:** Required\n- **Meaning:** Exam identifier.\n- **Implementation / validation:** Primary key.\n\n### `exams[].course_ids`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Courses covered by exam.\n- **Implementation / validation:** Many-to-many to courses.\n\n### `exams[].groups`\n- **Type:** array<string>\n- **Presence:** Required\n- **Meaning:** Groups sitting exam.\n- **Implementation / validation:** Many-to-many to student groups.\n\n### `exams[].size`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Total exam attendance.\n- **Implementation / validation:** Validator compares to sum of floor(room.capacity/2).\n\n### `exams[].duration_hours`\n- **Type:** integer\n- **Presence:** Required\n- **Meaning:** Exam duration.\n- **Implementation / validation:** Exam session windows currently two hours; validator does not explicitly compare duration_hours to selected AM/PM duration.\n\n
## 5. Calendar and time semantics

### 5.1 Teaching week
- Teaching days: Monday to Friday (`MON`–`FRI`).
- Periods 1–9 are teaching periods.
- P1 starts 08:00; P5 ends 13:00.
- Lunch is 13:00–14:00, after P5.
- P6 starts 14:00; P9 ends 18:00.
- Periods 10–13 are event-only, 18:00–22:00.
- A duration `d` starting at period `p` occupies `p` through `p+d-1`, inclusive.
- A teaching session cannot span lunch.
- Labs start only at P2 or P6.

### 5.2 Examination week
- Exam days: Monday to Saturday.
- AM session: 09:30–11:30.
- PM session: 14:00–16:00.
- Exam allocation key is `(day, exam_session_id)`.
- Exam room effective capacity is integer floor of half normal room capacity.
- An exam may occupy multiple rooms; the sum of effective capacities must meet exam size.

### 5.3 Do not collapse the time models
Teaching periods, event periods and exam sessions are different scheduling domains. Store them with explicit calendar references rather than treating all time as one generic period integer.

## 6. Official validator contract

### 6.1 Hard timetable rules

| Rule | Validator behaviour |
|---|---|
| H1 | Every source session must be scheduled exactly once; unknown sessions and unknown rooms are violations. Duplicate session IDs are reported by the main runner. |
| H2 | A faculty member cannot teach overlapping sessions. |
| H3 | A student group cannot attend overlapping sessions. Basket sessions sharing the same basket key are treated as one occupancy key. |
| H4 | A room cannot host overlapping sessions. |
| H5 | Room capacity must be at least session size. |
| H6 | Room type must be in the session's `room_types`. |
| H7 | Faculty unavailability must be respected. |
| H8 | Room unavailability must be respected. |
| H9 | Sessions must fit P1–P9, cannot cross lunch, and labs must start at configured lab start periods. |
| H10 | A session marked `needs_accessible` must use an accessible room. |
| H11 | All sessions sharing a `basket_slot` must have the same day and start period. |
| H12 | Faculty daily teaching duration cannot exceed `max_hours_per_day` (validator fallback is 4 if absent). |
| H14 | A session with `fixed_slot` must remain on that exact day and start period. |

### 6.2 Soft timetable penalties

| Rule | Penalty calculation |
|---|---|
| S1 | 2 points for each occupied period overlapping a faculty `avoid` preference. |
| S2 | 1 point for each gap period between a group's earliest and latest occupied period in a day. |
| S3 | 3 points per group teaching hour above 6 hours/day. |
| S4 | 3 points per additional same-course lecture for a group/day; basket course repetitions are scored separately. |
| S5 | 1 point for each scheduled session using less than 40% of the room's capacity. |
| S6 | 1 point for each session occupying P9. |

The application should store each penalty component and its explanation, not only the total. This makes optimisation understandable to admins and supports debugging.

### 6.3 Booking validation

The validator:
- detects duplicate decisions for a request (B1);
- detects an override that references an unknown session or a non-approved/non-institute booking (B2);
- rejects approval or alternative offers for cancelled requests (B3);
- requires a decision for every request (missing decisions are warnings);
- permits only `approved`, `rejected` or `alternative_offered`;
- requires a reason for rejection and alternative offers (warning if missing);
- validates room existence, event permission, type, capacity and required features;
- requires approved booking windows to contain the full booking interval;
- allows alternative offers outside the requested windows;
- checks room unavailability, timetable occupancy and mandatory-group occupancy;
- computes priority inversions and weighted booking score.

The validator's booking category weights are `institute_event: 5`, `guest_lecture: 4`, `department_event: 3`, `club_event: 2`. The effective category is the lower-priority (larger index) of the requested category and the role's category cap. Same-category ties are broken by earlier `submitted_at`.

**Important distinction:** the validator evaluates exported decisions. It does not implement authenticated reviewer assignment, no-self-approval, multi-stage approval, or the full operational workflow. Those are application requirements to implement in the backend.

### 6.4 Exam validation
- Every source exam must be scheduled exactly once.
- Day and exam session must be valid.
- Every selected room must exist and allow exams.
- Effective capacity is `room.capacity // 2`.
- Combined effective capacity must cover exam size.
- A room cannot host two exams in the same exam slot.
- A group cannot sit two exams in the same exam slot.
- The validator adds 5 soft penalty points for each additional exam for a group on the same day.

**Validator observation:** `duration_hours` exists in source exam records, but the validator does not explicitly compare it with the selected AM/PM window duration. Keep the field in the data model; do not invent an extra validator rule without recording it as an application-level policy.

## 7. Disruption contract

The sample disruption supports:
- `faculty_unavailable`: append faculty unavailability for each specified day and period set;
- `room_unavailable`: append room unavailability for each specified day and period set;
- `add_faculty`: add a faculty record in the same shape as a source faculty object;
- `add_session`: add a session record in the same shape as a source session object;
- `remove_session`: remove a session by ID.

The validator applies these changes to a deep copy of the dataset. Changes are permanent in the derived dataset for subsequent weeks. Therefore:
- retain the original dataset version;
- store the disruption file and each change as an immutable change set;
- create a derived dataset version when changes are approved/applied;
- preserve the pre-change timetable as a baseline;
- generate the repaired schedule against the derived dataset;
- compare repaired schedule against baseline;
- do not treat Week 7 booking overrides as permanent disruptions.

The public sample includes:
- F07 unavailable Monday P1–P9;
- CR-102 unavailable Monday–Friday P1–P9;
- new session CS202-T2, course CS202, CSE-2, F06, size 80, duration 1.

## 8. Export contract

### 8.1 `exports/schedule.json`
Required top-level fields:
- `team`
- `dataset_id`
- `sessions`
- `fest_week`
- `exams`

Each `sessions[]` item contains `session_id`, `day`, `start_period`, `room_id`.

`fest_week` contains:
- `bookings[]`: `request_id`, `status`, and, for approved/alternative allocations, day, start_period, end_period, room_id; reason is required for rejected and alternative decisions by warning and should always be supplied by our application.
- `session_overrides[]`: `session_id`, `day`, `start_period`, `room_id`, `displaced_by`.

`end_period` is inclusive. Only an approved institute event may displace a regular session. The displaced session must be moved, not dropped.

`exams[]` contains `exam_id`, `day`, `session`, `rooms[]`.

### 8.2 `exports/schedule_after.json`
This is the repaired timetable after applying the disruption, starting from `schedule.json`. The validator allows the `exams` field to be omitted in the disruption comparison; our application should preserve exams if they remain valid and include them where useful.

### 8.3 Export safety
Exports must be generated from persisted application state and the selected dataset/schedule version. Never manually patch generated JSON. Before export:
1. validate all required records;
2. serialize using exact field names and enum values;
3. run official validator;
4. store validator report and export checksum;
5. block “final/ready” status if hard violations remain.

## 9. Proposed normalized PostgreSQL mapping (not yet frozen)

This section proposes internal entities. It is a design recommendation, not a source requirement.

### 9.1 Dataset and configuration
- `dataset_versions`
- `institutes`
- `calendar_versions`
- `calendar_days`
- `calendar_periods`
- `calendar_exam_days`
- `calendar_exam_sessions`
- `booking_priority_categories`
- `role_category_caps`

### 9.2 Academic master data
- `departments`
- `rooms`
- `room_types` (optional lookup table; preserve unknown source values safely)
- `room_features`
- `room_feature_assignments`
- `room_allowed_uses`
- `faculty`
- `faculty_unavailability`
- `faculty_preferences`
- `student_groups`
- `courses`

### 9.3 Scheduling
- `teaching_sessions`
- `session_groups`
- `session_allowed_room_types`
- `session_versions` or dataset-scoped session records
- `timetable_versions`
- `timetable_assignments`
- `solver_runs`
- `solver_constraints` / `solver_run_metrics`
- `validation_runs`
- `validation_violations`

### 9.4 Venue booking
- `booking_requests`
- `booking_windows`
- `booking_allowed_room_types`
- `booking_required_features`
- `booking_mandatory_groups`
- `booking_cancellations`
- `booking_decisions`
- `booking_allocations`
- `booking_series` (only if recurrence semantics are defined)
- `approval_tasks`
- `approval_events`

### 9.5 Exams
- `exams`
- `exam_courses`
- `exam_groups`
- `exam_schedule_versions`
- `exam_assignments`
- `exam_room_allocations`

### 9.6 Disruptions and change control
- `disruption_sets`
- `disruption_changes`
- `change_proposals`
- `change_proposal_items`
- `change_validation_runs`
- `change_approvals`
- `applied_change_sets`

### 9.7 Cross-cutting
- `users`
- `role_assignments`
- `audit_logs`
- `notifications`
- `ai_conversations`
- `ai_messages`
- `ai_tool_executions`
- `import_jobs`
- `export_jobs`

### 9.8 Campus Navigator (separate module)
- `campuses`
- `buildings`
- `floors`
- `map_assets`
- `map_versions`
- `spaces`
- `doors`
- `entrances`
- `navigation_nodes`
- `navigation_edges`
- `map_processing_jobs`
- `map_review_items`
- `map_publications`

Navigator room references should reuse the canonical room record where the room is the same physical space. Do not create a second independent room identity for `CR-101`.

## 10. Proposed relationship principles

- One dataset version contains many source entities and configuration records.
- A course has many teaching sessions.
- A session belongs to one course and one assigned faculty member.
- A session belongs to many student groups through `session_groups`.
- A session may have one optional fixed slot and one optional basket slot.
- A timetable version has many assignments; an assignment references one session, one room, one day and one start period.
- A booking request has one or more windows, allowed room types, required features and mandatory groups.
- A booking request may have cancellation history and multiple decision events, but only one effective decision per export version.
- A booking allocation references a booking decision and one room/time interval.
- An exam references multiple courses and groups; one exam assignment can allocate multiple rooms.
- A disruption set contains ordered changes and creates a derived dataset version only after authorised approval.
- A change proposal references a baseline timetable and a target dataset version.
- Map versions are immutable; publication points to one approved version.

## 11. Database integrity and indexing recommendations

Recommended integrity:
- primary keys on internal UUIDs; unique external IDs scoped to dataset version;
- foreign keys for all imported references;
- CHECK constraints for non-negative capacities, positive durations, valid period ranges and enumerated states;
- unique `(dataset_version_id, external_id)` for source entities;
- unique `(timetable_version_id, session_id)` for assignments;
- unique `(request_id, decision_version_id)` for one effective decision in an export version;
- unique `(exam_assignment_id, room_id)` for exam room allocations;
- use database transactions for approval, allocation and publish operations.

Recommended indexes:
- sessions by dataset/course/faculty;
- session-group join by group and session;
- timetable assignments by version/day/start/room;
- timetable assignments by version/day/start/faculty;
- booking requests by status/submitted_at/category;
- booking allocations by room/day/time range;
- faculty and room unavailability by resource/day/period;
- exams by dataset and exam slot;
- audit logs by entity and timestamp;
- map spaces and navigation edges by map version.

For PostgreSQL, consider exclusion constraints for non-overlapping room reservations using range types once time representation is final. The teaching timetable is period-based, so explicit period occupancy validation remains necessary.

## 12. Backend architecture and build order

Recommended stack, subject to team skill confirmation:
- Frontend: React + TypeScript + Vite.
- UI: Tailwind CSS + shadcn/ui.
- Backend: Python + FastAPI.
- Database: PostgreSQL; PostGIS for campus spatial data.
- ORM/migrations: SQLAlchemy 2.x + Alembic.
- Solver: Google OR-Tools CP-SAT.
- AI: Gemini API with structured output and constrained backend tools.
- Tests: Pytest plus the official validator.
- Architecture: modular monolith, not microservices for the hackathon MVP.

Build in this sequence:
1. source audit and requirements freeze;
2. data dictionary and ERD;
3. database schema and migrations;
4. import pipeline and round-trip export tests;
5. backend auth, permissions and API contracts;
6. timetable solver and validator integration;
7. booking and approval workflows;
8. exams;
9. disruptions and schedule versioning;
10. frontend vertical slices against stable API contracts;
11. Campus Navigator;
12. Gemini assistant;
13. end-to-end tests, exports and deployment.

Do not wait for every backend feature before building any UI. Build each feature as a vertical slice: schema → API → UI → tests. The UI may use mock data for early design, but the integrated version must use real APIs.

## 13. AI safety and authority boundaries

Gemini may:
- parse natural-language booking requests into structured drafts;
- ask for missing information;
- explain schedule or booking options;
- propose changes and candidate rooms;
- invoke explicitly permitted read/validation tools.

Gemini must not:
- write directly to PostgreSQL;
- approve its own proposals;
- bypass role permissions;
- override hard constraints;
- publish a timetable or map without authorised approval;
- invent source IDs or silently alter user-provided requirements.

Every AI-generated action must be schema-validated, permission-checked, domain-validated and recorded. The backend remains the source of truth.

## 14. Important discrepancies, limitations and open decisions

1. The validator's `CAT_WEIGHT` mapping is hardcoded in validator.py, while `priority_order` and `role_category_cap` are read from the dataset. Preserve both behaviours exactly for competition scoring.
2. The README says seminar halls and open-air theatre never take regular classes; the timetable validator itself checks `room_types` but does not separately enforce this sentence. The solver should follow the dataset's allowed room types and the official validator; do not add a contradictory room restriction without checking source records.
3. `faculty.needs_accessible` and `student_groups.needs_accessible` are source fields, but H10 checks `session.needs_accessible`. The app may derive session accessibility requirements from institutional policy, but this derivation must be explicit.
4. The validator's H12 fallback is 4 if a faculty daily limit is missing. Our import should flag missing values; do not silently hide the missing source field.
5. `booking_requests.series_id` exists, but recurrence allocation rules are not defined in the validator. Treat recurring series as an application extension and do not claim the validator verifies recurrence.
6. Booking `requester` and cancellation `by` are display labels, not authenticated user IDs. Identity reconciliation is an application workflow.
7. `department` is nullable in booking requests; department membership and requester-to-department authority need explicit policy.
8. The booking validator uses one room per booking allocation. Multi-room booking support is not part of this export contract unless organisers clarify it.
9. Exam `duration_hours` is present but not explicitly checked against AM/PM slot duration by validator.
10. The validator does not enforce approval roles, no-self-approval or approval chains; backend must.
11. The public data is fictional. Do not treat names or records as live institutional identity data.
12. No actual successful generated schedule has yet been run through the validator as part of this audit. That is a future acceptance test.

## 15. Acceptance criteria for Milestone 1

- [x] Starter ZIP inventory inspected.
- [x] Canonical JSON root keys inspected.
- [x] Source entity counts verified.
- [x] Nested source fields documented.
- [x] README import/export contract reviewed.
- [x] Validator hard/soft timetable checks reviewed.
- [x] Booking, exam and disruption checks reviewed.
- [ ] Data dictionary approved.
- [ ] ER diagram reviewed.
- [ ] PostgreSQL schema reviewed.
- [ ] Import/export round-trip test implemented.
- [ ] Generated schedule passes official validator.

## 16. Next deliverable

**Milestone 2A — ER Diagram and Relational Schema Design.**

We will convert this dictionary into:
- a complete entity relationship diagram;
- exact table definitions and column types;
- primary and foreign keys;
- join tables for arrays and many-to-many relationships;
- versioning and audit design;
- unique/check/exclusion constraints;
- indexes;
- migration order;
- sample import mappings.

No migrations or application code should be generated until this design is reviewed and frozen.
