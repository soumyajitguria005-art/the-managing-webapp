# CIT Backend & Database Engineering Master Package v0.5

This is the consolidated **backend-and-database-only** package for the CIT Campus Scheduling & Venue Management Platform.

- Includes prior product/competition context, architecture, API, ERD, SQL, migrations, Python foundations, tests, original dataset and official validator.
- Adds a detailed backend domain rulebook and implementation plan.
- Adds explicit department isolation, shared faculty/room conflict rules, joint CSE+ECE teaching semantics, scoped timetable generation and locked baseline requirements.
- Adds a proposed database hardening migration and a comprehensive acceptance test matrix.
- Excludes frontend implementation and Campus Navigator implementation.

Start at `00_READ_FIRST/README.md` and follow the reading order there.

**Truthful status:** this is an engineering package and implementation blueprint. The current v0.4 baseline is partial and not live-validated. The new migration is proposed and must be run on a disposable PostgreSQL instance before acceptance. The backend workflows are not represented as already complete.
