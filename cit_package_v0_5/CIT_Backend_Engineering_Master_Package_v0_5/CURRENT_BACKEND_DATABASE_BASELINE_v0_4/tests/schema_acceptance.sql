-- Run after migration on a disposable PostgreSQL database.
-- Expected: each query returns zero rows unless explicitly noted.

-- A. Required namespaces
SELECT nspname
FROM pg_namespace
WHERE nspname IN ('core','academic','identity','scheduling','booking','exams',
                  'change_mgmt','approvals','analytics','assistant','notifications','integration')
ORDER BY nspname;

-- B. Verify critical tables exist (should return zero rows)
WITH required(schema_name, table_name) AS (
  VALUES
  ('core','dataset_versions'),('core','calendar_versions'),('core','calendar_periods'),
  ('academic','rooms'),('academic','faculty'),('academic','student_groups'),
  ('academic','courses'),('academic','teaching_sessions'),('academic','session_groups'),
  ('scheduling','timetable_versions'),('scheduling','timetable_assignments'),
  ('scheduling','timetable_occupancy'),('booking','booking_requests'),
  ('booking','booking_decisions'),('booking','session_overrides'),
  ('exams','exam_schedule_versions'),('exams','exam_room_allocations'),
  ('change_mgmt','change_proposals'),('approvals','approval_tasks'),
  ('integration','export_jobs'),('integration','validator_runs')
)
SELECT r.*
FROM required r
LEFT JOIN information_schema.tables t
  ON t.table_schema=r.schema_name AND t.table_name=r.table_name
WHERE t.table_name IS NULL;

-- C. Verify unique index for one active dataset per institute exists
SELECT indexname
FROM pg_indexes
WHERE schemaname='core' AND indexname='uq_dataset_one_active';

-- D. Verify partial unique effective booking decision index exists
SELECT indexname
FROM pg_indexes
WHERE schemaname='booking' AND indexname='uq_booking_effective_decision';

-- E. Ensure no duplicate external IDs can exist in imported rooms (constraint metadata)
SELECT conname
FROM pg_constraint
WHERE conrelid='academic.rooms'::regclass AND contype='u';

-- F. Smoke test transaction rollback manually in a disposable DB:
-- BEGIN; INSERT invalid row; expect CHECK violation; ROLLBACK;
