# PostgreSQL Local Runbook

## Prerequisites
- Docker Desktop or Docker Engine with Compose plugin.
- Python 3.11+ (package verified with Python 3.13.5 in the authoring environment).
- `psql` client for the SQL acceptance script.

## Start database

```bash
cp .env.example .env
# Change POSTGRES_PASSWORD in .env before use.
docker compose up -d postgres
docker compose ps
```

Wait for the `healthy` state. Confirm connection with `psql` or a PostgreSQL GUI.

## Install backend database dependencies

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Export the connection URL for the current terminal:

```bash
# PowerShell
$env:DATABASE_URL="postgresql+psycopg://cit_app:YOUR_PASSWORD@localhost:5432/cit_platform"
# macOS/Linux
export DATABASE_URL='postgresql+psycopg://cit_app:YOUR_PASSWORD@localhost:5432/cit_platform'
```

## Apply and inspect migration

```bash
alembic upgrade head
alembic current
alembic history
```

If `pgcrypto` extension creation fails due to permissions, do not remove UUID defaults blindly. Check whether the extension is already installed or ask the database administrator to enable it.

## Run acceptance SQL

Use a `psql` URL (not SQLAlchemy's `postgresql+psycopg://` dialect URL):

```bash
psql 'postgresql://cit_app:YOUR_PASSWORD@localhost:5432/cit_platform' -v ON_ERROR_STOP=1 -f tests/schema_acceptance.sql
```

## Reset disposable local database only

```bash
docker compose down -v
```

This destroys the named local database volume. Never run this command against a shared or production database.

## What to send back after running
- Output of `alembic upgrade head`.
- Output of `alembic current`.
- Output of `tests/schema_acceptance.sql`.
- PostgreSQL server version.
- Any full error text, with passwords/tokens removed.

This local run is the first actual PostgreSQL validation gate. Do not import the starter data until it passes.
