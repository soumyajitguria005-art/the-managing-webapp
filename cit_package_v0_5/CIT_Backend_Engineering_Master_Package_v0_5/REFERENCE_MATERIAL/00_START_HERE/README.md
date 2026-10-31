# CIT Google AI Studio Upload Bundle v1.0

This bundle consolidates the project documents, official hackathon source material, SQL/migrations, current backend foundation and milestone reports for review in Google AI Studio.

## Start here

1. Read `00_START_HERE/PROJECT_CONTEXT_AND_UPLOAD_GUIDE.md`.
2. Upload the bundle contents (or the ZIP itself if the platform accepts ZIPs). If Google AI Studio cannot inspect ZIP contents reliably, extract it locally and upload the key files/folders individually.
3. Upload the original official starter pack files, especially `data/cit_public.json` and `validator.py`; they are included both as an original ZIP and as extracted files.
4. Give the model the master audit instruction in `00_START_HERE/AI_STUDIO_MASTER_INSTRUCTION.md`.
5. Require an audit report before authorizing implementation.

## Authority and version rules

- `05_CURRENT_IMPLEMENTATION/CIT_Backend_Database_Package_v0_4/` is the latest working database foundation.
- The v0.4 milestone report is the latest status report.
- v0.3 is retained only as historical baseline reference and is explicitly superseded by v0.4. Do not combine its code with v0.4 or treat it as the latest package.
- The original starter pack and official validator are authoritative for competition input/output and constraints.
- PDFs explain decisions; Markdown, SQL, Python and JSON files provide inspectable implementation/source detail.

## Current status (do not overstate)

The current package is a partial backend/database foundation, not a completed backend. The initial schema baseline has 78 tables across 12 schemas; the v0.4 package includes a partial SQLAlchemy mapping and source contract validation. Offline Alembic rendering and available Python tests were run. Live PostgreSQL migration/acceptance testing and transactional dataset import remain pending. Scheduling, exams, bookings, disruptions, approvals, analytics, AI workflows and production authentication still require implementation and verification.

## Project boundaries

- Backend first; frontend deferred.
- Campus Navigator/map implementation deferred to teammate; retain only a future integration boundary.
- No dummy endpoints or fake workflows.
- AI may interpret/propose; deterministic backend code validates and applies authorized operations.
