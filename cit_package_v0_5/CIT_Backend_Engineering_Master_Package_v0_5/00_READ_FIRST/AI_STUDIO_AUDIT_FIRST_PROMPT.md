# First prompt to send after uploading this package

Read the entire CIT backend/database engineering package, including the official starter dataset and validator. Do not code yet.

Return a detailed audit containing:
1. Full file inventory and which files were actually inspected.
2. Source authority map and document conflicts.
3. Existing v0.4 database/ORM/migration status.
4. Department and shared-resource model, including all CSE/ECE cases in the v0.5 rulebook.
5. Dataset-level FK integrity gaps and a proposed migration sequence.
6. API/service modules currently missing.
7. Security, authorization and transaction risks.
8. Open decisions that genuinely block implementation.
9. Test plan mapped to the acceptance matrix.
10. Ordered milestone plan with verifiable exit criteria.

Explicitly distinguish implemented, partial, missing and unverified. Do not claim a migration or test passed unless you executed it. Do not implement frontend or Campus Navigator. After presenting the audit, stop and wait for approval before broad code changes.
