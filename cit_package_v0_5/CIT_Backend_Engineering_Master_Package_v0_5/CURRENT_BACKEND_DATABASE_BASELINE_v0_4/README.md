# CIT Backend Database Package v0.4

Incremental Milestone 2F engineering package. Read `docs/MILESTONE_2F_REPORT.md` first.

## Included
- `docker-compose.yml` — local PostgreSQL 16 service.
- `sql/0001_initial_schema.sql` and `migrations/` — baseline DDL/Alembic migration from v0.3, with statement-by-statement migration execution.
- `app/modules/integration/source_schemas.py` — strict Pydantic contract for canonical `cit_public.json`.
- `app/modules/integration/validate_source.py` — source loader, checksum, observed counts and ID extraction.
- `app/modules/datasets/models.py`, `app/modules/academic/models.py` — initial typed SQLAlchemy 2.x mapping foundation (15 tables, partial coverage).
- `tests/` — source-contract and PostgreSQL-dialect compilation tests.
- `.env.example`, `requirements.txt`, `alembic.ini` — local setup.

## Local setup

```bash
cp .env.example .env
# Edit .env and set a private local password.
docker compose up -d postgres
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Set `DATABASE_URL` in the shell/session before running Alembic:

```bash
alembic upgrade head
alembic current
```

Run tests:

```bash
pytest -q
```

Then run the SQL acceptance script against the disposable database (for example using `psql -v ON_ERROR_STOP=1 -d "$DATABASE_URL" -f tests/schema_acceptance.sql`; use a `psql` connection URL compatible with your local client).

## Current limitations

- This environment did not have Docker or PostgreSQL binaries/server, so no live migration or SQL acceptance run is claimed.
- ORM mappings cover 15 of the 78 application tables only.
- Transactional import, activation, full domain services and functional API endpoints are not implemented in this package.
- The schema needs dataset-scoped FK hardening and open policy decisions before a production deployment.
- Campus Navigator and frontend remain deferred.

Do not deploy this package as production-ready. It is a reproducible engineering checkpoint for the next validation gate.
