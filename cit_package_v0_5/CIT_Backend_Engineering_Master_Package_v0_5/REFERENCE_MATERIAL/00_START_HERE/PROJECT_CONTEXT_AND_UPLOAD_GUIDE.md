# Project Context & Upload Guide

## Project
CIT Campus Scheduling and Venue Management Platform for the hackathon. The system must generate and validate weekly timetables, schedule exams, process venue/event bookings, manage disruptions with minimal-change rescheduling, support approvals, expose schedule/utilisation views, explain decisions, and import/export the official competition data format.

## Confirmed scope boundaries
- Build and verify backend functionality before frontend integration.
- Do not build dummy endpoints or pretend static responses are functional.
- Campus Navigator is on hold because a teammate is building it. Do not implement map UI, map processing, indoor/outdoor routing or geometry now. Keep a future integration boundary only.
- Continue in sequential milestones; test each milestone and report exact test status.

## Technology direction
Python + FastAPI + Pydantic; PostgreSQL + SQLAlchemy 2.x + Alembic; OR-Tools CP-SAT for scheduling; Pytest and official validator; Gemini structured output/function calling as an interpretation layer only. Do not change this stack without documenting a concrete reason and requesting review.

## Roles
Official roles: `admin`, `department_coordinator`, `faculty`, `club`. Club Representative is a UI label for `club`, not a fifth role. Scope permissions by institute/department/club/resource. Student read access remains a product-policy decision, not an extra competition role.

## Competition source
The canonical input is `CrunchWeek_StarterPack/data/cit_public.json`; `validator.py` is the authoritative validator. CSVs are supporting data and may omit some canonical JSON configuration. Do not hardcode observed IDs or fixture counts. Generate required exports from application data; never hand-edit expected output files.

## Core constraints
- Every teaching session exactly once.
- No overlap for faculty, mandatory student groups or rooms.
- Respect capacity, room type/allowed use, accessibility, unavailability and fixed slots.
- No teaching across lunch; labs have the source-defined duration/start restrictions.
- Elective basket constraints must be modelled as specified by the source.
- Faculty daily limits and all soft-penalty formulas must be read from the actual official validator, not guessed from summaries.
- Exams follow the official exam-day/session rules and room-capacity policy.
- Booking priority, role-category caps, cancellation and tie-break rules follow the official source/validator.
- Hard constraints are never overridden to improve a soft score.

## Important open decisions
Do not invent reviewer routing, alternative-offer export semantics, recurrence semantics, multi-room booking export behaviour, publication gate, or department coordinator edit authority. Check the decision register and mark these as OPEN until confirmed. No-self-approval, auditability, hard-constraint enforcement, revalidation after material edits, stale-version checks and atomic transactions are core application safeguards.

## Upload recommendation
Upload all contents in this bundle if the AI Studio workspace supports them. If file count/size limits apply, prioritize:
1. This guide and `AI_STUDIO_MASTER_INSTRUCTION.md`.
2. Official starter pack `README.md`, `data/cit_public.json`, `validator.py`, examples and CSVs.
3. Latest v0.4 implementation folder (all source, SQL, migration, tests and README).
4. Master PRD, source audit/data dictionary, API contracts, architecture decision register, revised DB blueprint, ERD and milestone reports.
5. Problem statement.

Ask the model to cite exact filenames when making claims. Require it to identify missing source support rather than filling gaps from general assumptions.
