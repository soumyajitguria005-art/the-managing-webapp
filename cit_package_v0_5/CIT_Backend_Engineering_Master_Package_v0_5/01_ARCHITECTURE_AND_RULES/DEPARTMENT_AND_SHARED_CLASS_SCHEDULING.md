# Department Isolation, Shared Resources & Joint Teaching — Mandatory Scheduling Design

This document captures the CSE/ECE example and turns it into explicit backend behaviour and acceptance rules.

## 1. The key distinction

**Department scope controls who may manage which academic records. Resource occupancy controls whether two activities may happen at the same time. These are different concepts.**

A naive implementation that creates a separate solver or separate occupancy map for every department is incorrect. It can double-book a teacher or room across departments. Conversely, a naive institute-wide "one class at a time" rule is also incorrect because unrelated CSE and ECE cohorts may attend different classes simultaneously.

The solver must operate on actual resource consumption, not on department labels.

## 2. Canonical examples

### Case A — Independent department classes (allowed)

| Session | Student group | Faculty | Room | Time |
|---|---|---|---|---|
| CSE-101 lecture | CSE-Year-1 | F-CSE-01 | Room A | Monday P2 |
| ECE-101 lecture | ECE-Year-1 | F-ECE-01 | Room B | Monday P2 |

Allowed because group, faculty and room resources are all distinct.

### Case B — Same teacher across departments (not allowed)

| Session | Student group | Faculty | Room | Time |
|---|---|---|---|---|
| CSE-201 | CSE-Year-2 | F-07 | Room A | Monday P3 |
| ECE-201 | ECE-Year-2 | F-07 | Room B | Monday P3 |

Not allowed because F-07 is the same institute-level faculty resource, even though the departments differ.

### Case C — Same room across departments (not allowed)

CSE-201 and ECE-201 cannot occupy Room A at the same time, regardless of department.

### Case D — Joint CSE+ECE lecture (one shared session)

| Field | Value |
|---|---|
| Session | COMMON-MATH-01 |
| Course | Common Mathematics |
| Participating groups | CSE-Year-1 and ECE-Year-1 |
| Faculty | F-07 |
| Room | Main Lecture Hall |
| Attendance | Sum of required group sizes, unless source gives a verified distinct combined attendance |
| Time | Monday P4 |

This is one teaching session with two group links, not two independent copies. It consumes both student-group resources, the faculty resource and the room resource. Any simultaneous session for CSE-Year-1 or ECE-Year-1 conflicts with it.

### Case E — A CSE-only timetable edit must preserve ECE

If an Admin requests generation for CSE only:
- CSE-owned/target sessions are candidates for generation.
- ECE-only assignments are locked and remain unchanged.
- A joint CSE+ECE session is detected because it intersects the target CSE scope.
- Any move of that joint session must still be checked against ECE group availability and shared faculty/rooms.
- If the joint session would need to change in a way that affects an out-of-scope department, require the appropriate elevated approval or return a scope conflict; never silently change ECE.
- The final candidate is validated against all sessions/resources in the timetable, not just CSE.

## 3. How to identify sessions in scope

A session's department scope must not be inferred solely from the course's owning department.

Recommended scope derivation:
1. Determine the set of participating student groups.
2. Resolve each group's department.
3. Include a session in a department-scoped generation if at least one participating group belongs to the target department, subject to the selected policy.
4. Mark sessions with groups in multiple departments as `cross_department`.
5. Include explicitly department-owned events/sessions where no student groups exist using an explicit owner department.
6. Preserve all sessions outside scope as locked assignments.
7. Do not allow a scoped user to edit cross-department sessions without required authority.

OPEN: Whether a department-only generation should be allowed to move a cross-department session when the requester has authority for only one participating department. Safe default: block that movement and request Admin approval; keep its baseline assignment locked.

## 4. Student group identity and overlap

The competition fixture supplies groups, not necessarily individual student membership. Treat each source group as a conflict unit unless the source explicitly provides a group-overlap relationship.

Do not invent that CSE-Year-1 and CSE-Year-1-Lab are disjoint. If the institution has nested groups, add a formal group-membership/overlap model (or resolve to atomic cohorts) before using both in the solver. Otherwise the solver may schedule overlapping students at once.

PROPOSED future model:
- `student_cohorts` as atomic conflict units;
- `student_group_cohort_memberships` maps a logical group to atomic cohorts;
- occupancy is generated for each atomic cohort, or a group conflict graph is constructed.
This is not present in the official starter contract and must not be fabricated for the hackathon fixture.

## 5. Faculty assignment cardinality

The current source fixture appears to provide one `faculty_id` per session. The database foundation currently has one nullable faculty_id on teaching_sessions.

Recommended extension:
- Keep the source's single faculty_id for faithful import compatibility.
- Add a normalized `teaching_session_faculty` association for zero/one/multiple instructors.
- Import the source faculty_id as the primary assigned instructor.
- Additional instructors may be added only through authorized application actions.
- Every linked instructor consumes their institute-wide availability and daily-hour limit.
- Do not count a joint class once per department; it is one session and its teaching duration counts once per assigned instructor.

OPEN: whether co-teaching and teaching assistants are in hackathon scope. Design can support it, but the source contract does not require it.

## 6. Department permissions

- Admin: institute-wide scope.
- Department Coordinator: only assigned department by default.
- Faculty: own profile, own availability/preferences and assigned teaching sessions; additional rights need explicit policy.
- Club: only its club-owned event/booking requests and permitted resources.

Department Coordinator must not:
- change another department's groups/courses/faculty without authorization;
- move a cross-department session unilaterally;
- override global room/faculty conflicts;
- publish a global timetable unless explicitly granted authority.

## 7. Scoped timetable generation transaction

A department-scoped generation request must capture:
- baseline timetable version ID;
- dataset version ID;
- target department IDs;
- target session IDs or deterministic scope rule/version;
- preserve-outside-scope = true;
- locked assignment IDs and version hash;
- solver config/version/seed;
- requester and authorization evidence.

Before apply/publish:
1. Compare current published timetable version with captured baseline.
2. Reject stale proposals if the baseline changed.
3. Recheck permissions.
4. Recheck every room, faculty and group occupancy across all departments.
5. Re-run independent hard-constraint validation.
6. Preserve out-of-scope assignments byte-for-byte/logically unchanged.
7. Commit new version and audit record atomically.

## 8. Required tests

The acceptance matrix contains explicit tests for all cases above. At minimum the solver must prove:
- independent CSE/ECE sessions may share a slot;
- same faculty across departments cannot;
- same room across departments cannot;
- joint class blocks both cohorts;
- scoped CSE generation cannot change ECE-only assignments;
- joint sessions are detected by a CSE scope;
- a department coordinator cannot modify an out-of-scope session;
- the final full-timetable validator catches conflicts introduced by any department-specific run.
