# Milestone 4 Execution Report: Identity, Authentication, and Scoped Authorization

**Author:** Senior Backend & Database Architecture Team  
**Date:** October 31, 2026  
**Environment:** PostgreSQL 15.19 (Debian 12), Python 3.10.12, SQLAlchemy 2.0.55, PyJWT 2.15.1, bcrypt 5.0.0, FastAPI 0.162.0  
**Test Suite Result:** 48 / 48 tests passing in 23.13s against live PostgreSQL  

---

## 1. Executive Summary

Milestone 4 delivers the complete, production-grade **Identity, Authentication, and Scoped Authorization System** for the Chilika Institute of Technology (CIT) Campus Scheduling & Venue Management Platform.

The implementation strictly enforces the four official competition roles (`admin`, `department_coordinator`, `faculty`, `club`), rigorously separates role assignment from scope evaluation, guarantees cryptographic security via bcrypt salted password hashing and JWT access tokens, implements persistent refresh token rotation with token family tracking and automatic reuse breach containment, protects accounts against credential brute-forcing via persistent lockout policies, logs all security and administrative operations into `core.audit_events`, and mathematically enforces cross-department scheduling authority invariants (preventing unilateral coordinator modification of joint classes such as HS201, ID101, or open electives).

All 18 new identity and authorization integration tests execute against the live PostgreSQL 15.19 engine, bringing the total passing test suite to **48 / 48 tests**.

---

## 2. Four Official Competition Roles & Scope Decoupling

### 2.1 Canonical Role Definitions
The system strictly enforces the four official competition roles without creating fictitious or auxiliary roles:
1. `admin`: Global institute administrative authority. Holds root permissions across all departments, rooms, faculty, student groups, curricula, and timetable generation requests.
2. `department_coordinator`: Academic scheduling authority scoped to one or more academic departments (e.g., Computer Science & Engineering, Electronics & Communication Engineering).
3. `faculty`: Teaching staff authority scoped to individual faculty profiles, teaching workloads, availability intervals, and pedagogical preferences.
4. `club`: Student organization representative authority scoped to extracurricular venue booking requests, series events, and public availability lookups.

### 2.2 Decoupled Role Assignment and Scopes
Role assignments and scopes are explicitly modeled as separate concepts in `identity.user_role_assignments`:
- **Role Assignment:** A grant giving user $U$ role $R \in \{\text{admin}, \text{department\_coordinator}, \text{faculty}, \text{club}\}$.
- **Scope Type:** $S_{\text{type}} \in \{\text{institute}, \text{department}, \text{resource}, \text{club}\}$.
- **Scope ID:** Target entity UUID (or `NULL` for global institute scope).
- **Multi-Role & Multi-Scope Support:** A user may hold multiple roles (e.g. Dr. Rajesh Kumar is both a Faculty member and holds dual department scopes in CSE and ECE).

---

## 3. Cryptographic Security & Session Lifecycle

### 3.1 Password Security
- **Bcrypt Work Factor:** 12 work rounds (`gensalt(rounds=12)`), providing high resistance to offline GPU dictionary attacks.
- **Strict Prohibition:** Zero plaintext passwords or reversible ciphers.

### 3.2 Access Token Management (JWT)
- **Algorithm:** HMAC-SHA256 (`HS256`) with a 32+ byte cryptographic secret configured via environment variables.
- **Lifetime:** Configurable 30-minute standard expiration (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Claims:** User ID (`sub`), email, list of active roles (`roles`), list of active scopes (`scopes`), issued-at (`iat`), expiration (`exp`), and token type (`type="access"`).
- **Type Validation:** Rejects any token where `type != "access"`.

### 3.3 Refresh Token Rotation & Token Family Reuse Containment
- **Storage:** Refresh tokens are 48-byte URL-safe cryptographic strings (`secrets.token_urlsafe(48)`). Only the SHA-256 hash is persisted in `identity.auth_sessions.refresh_token_hash`.
- **Token Rotation:** Every refresh request invalidates the consumed refresh token (`revoked_at = now()`) and issues a new access token alongside a fresh rotated refresh token.
- **Token Family Tracking:** Each authenticated session chain is tracked via `correlation_id` in `core.audit_events`.
- **Compromise / Reuse Detection:** If an already-rotated or revoked refresh token is presented again (indicating token leakage or an active replay attack), the system triggers an immediate security lockdown:
  1. All sessions belonging to that token family are permanently revoked.
  2. All active sessions for the compromised user account are terminated.
  3. A high-severity security audit event (`AUTH_REFRESH_TOKEN_REUSE_DETECTED`) is permanently committed.
  4. The request is rejected with `HTTP 401 Unauthorized`.

### 3.4 Brute-Force Protection & Account Lockout
- **Lockout Policy:** 5 consecutive failed login attempts within a 15-minute window (`LOCKOUT_DURATION_MINUTES`).
- **Persistence:** Failed attempts and lockouts are tracked via `core.audit_events` (`action="AUTH_LOGIN_FAILED"`), guaranteeing that brute-force tracking survives worker restarts and operates across multi-node deployments without requiring an external cache.
- **Response:** Locked accounts receive `HTTP 429 Too Many Requests` with a `Retry-After` header indicating remaining lockout seconds.

---

## 4. Cross-Department & Joint Scheduling Authority Invariants

### 4.1 The Joint Session Conflict Problem
In large multidisciplinary institutions, core courses (e.g., Mathematics `MA101`, Environmental Studies `ID101`, Humanities `HS201`, Open Electives `OE301`) combine student cohorts across multiple academic departments (e.g., CSE and ECE). 
Allowing a Department Coordinator for CSE to unilaterally reschedule or modify a joint session would silently corrupt or disrupt the timetable of ECE students and faculty.

### 4.2 Invariant Enforcement (`evaluate_session_modification_authority`)
When evaluating authority to modify, reschedule, or cancel a teaching session:
1. **Institute Admin:** Global authority; permitted for all sessions.
2. **Single-Department Session:**
   $$\text{InvolvedDepartments}(S) = \{\text{CourseDept}\} \cup \{\text{GroupDept} \mid g \in S.\text{groups}\}$$
   If $|\text{InvolvedDepartments}(S)| = 1$ and the coordinator holds an active grant for that single department, the operation is **authorized**.
3. **Joint / Cross-Department Session:**
   If $|\text{InvolvedDepartments}(S)| > 1$:
   $$\text{UnauthorizedDepartments} = \text{InvolvedDepartments}(S) \setminus \text{CoordinatorGrants}$$
   - If $\text{UnauthorizedDepartments} \neq \emptyset$, the unilateral action is **strictly rejected** with `HTTP 403 Forbidden` ("Unilateral modification rejected: joint cross-department session").
   - If the user holds explicit coordinator grants covering **all** participating departments, or possesses Institute Admin privileges, the action is **authorized**.

---

## 5. API Surface & Endpoints

All endpoints are registered under `/api/v1` and fully integrated:

| Method | Endpoint | Access Control | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Public | Authenticates credentials, tracks failed attempts/lockout, issues access + refresh tokens. |
| `POST` | `/api/v1/auth/refresh` | Public | Rotates refresh token with family tracking and reuse breach containment. |
| `POST` | `/api/v1/auth/logout` | Authenticated | Revokes all active sessions for current user. |
| `GET` | `/api/v1/auth/me` | Authenticated | Returns current profile, active roles, and active scopes. |
| `POST` | `/api/v1/auth/password-change` | Authenticated | Verifies current password, updates hash, and revokes all active sessions. |
| `GET` | `/api/v1/auth/sessions` | Authenticated | Lists recent sessions and active status. |
| `DELETE` | `/api/v1/auth/sessions/{id}` | Owner / Admin | Revokes a specific authenticated session. |
| `GET` | `/api/v1/users` | Admin Only | Lists all registered users, roles, and status. |
| `POST` | `/api/v1/users` | Admin Only | Provisions a new user account with initial role and scope assignment. |
| `GET` | `/api/v1/users/{id}` | Self / Admin | Returns detailed profile and role assignments. |
| `POST` | `/api/v1/users/{id}/activate` | Admin Only | Activates an invited, suspended, or disabled user. |
| `POST` | `/api/v1/users/{id}/deactivate` | Admin Only | Disables a user account and terminates all active sessions. |
| `POST` | `/api/v1/users/{id}/roles` | Admin Only | Assigns an official role and scope to a user. |
| `DELETE` | `/api/v1/users/{id}/roles/{id}` | Admin Only | Revokes an active role assignment. |
| `GET` | `/api/v1/auth/verify-session-authority/{session_id}` | Authenticated | Verifies scheduling authority on a session (single vs joint). |
| `GET` | `/api/v1/auth/verify-faculty-authority/{faculty_id}` | Authenticated | Verifies access to a faculty profile/preferences. |
| `GET` | `/api/v1/auth/verify-booking-authority/{booking_id}` | Authenticated | Verifies authority on a booking request. |
| `GET` | `/api/v1/auth/audit-logs` | Admin Only | Queries security audit logs from `core.audit_events`. |

---

## 6. Comprehensive Test Verification

All 48 backend integration tests executed and passed against live PostgreSQL 15.19:

```bash
PYTHONPATH=backend python3 -m pytest backend/tests -v
```

### Test Summary (48 / 48 Passed):
- **Database & Catalog Parity (10 tests):** Alembic revision `0002_dept_scope_shared_teaching`, 84/84 table catalog match, department isolation, unavailability constraints, composite foreign key cross-dataset rejection, advisory locks.
- **Dataset Import Pipeline (17 tests):** Canonical ingestion of `cit_public.json`, exact ID preservation, entity count reconciliation, joint session preservation, multi-department faculty, invalid JSON rejection, transaction rollback, retry after failure, idempotency, dataset activation, and concurrent import locking.
- **Identity & Authorization (18 tests):**
  - `test_seed_dev_identities_structure`: Proves 4 official roles and scope separation.
  - `test_login_success_and_token_structure`: Proves JWT generation, claims, and refresh token hashing.
  - `test_login_invalid_password_returns_401`: Proves rejection of incorrect credentials.
  - `test_account_lockout_after_consecutive_failed_logins`: Proves lockout after 5 failures and HTTP 429 response.
  - `test_auth_me_endpoint_with_bearer_token`: Proves profile lookup with Bearer token.
  - `test_expired_access_token_rejection`: Proves HTTP 401 on expired access token.
  - `test_refresh_token_rotation_flow`: Proves refresh token rotation.
  - `test_refresh_token_reuse_detection_and_family_revocation`: Proves immediate token family revocation on reuse attempt.
  - `test_logout_revokes_active_session`: Proves logout invalidates refresh token.
  - `test_password_change_invalidates_all_active_sessions`: Proves password change revokes all existing sessions.
  - `test_user_deactivation_prevents_login_and_refresh`: Proves disabled users cannot authenticate or refresh.
  - `test_department_coordinator_authority_on_single_department_session`: Proves coordinator access to single-department sessions.
  - `test_joint_session_unilateral_modification_rejected`: Proves rejection of unilateral modification on joint classes.
  - `test_multi_department_coordinator_can_modify_joint_session`: Proves multi-department grants allow joint class scheduling.
  - `test_faculty_self_isolation`: Proves faculty cannot access other faculty profiles.
  - `test_club_rep_booking_authority_and_isolation`: Proves club reps cannot touch academic sessions.
  - `test_admin_user_management_and_role_crud`: Proves admin user and role assignment CRUD.
  - `test_audit_trail_recorded_for_security_events`: Proves persistence of security events in `core.audit_events`.
- **Model Metadata & Source Contracts (3 tests):** Full ORM DDL compilation, Pydantic schema validation, and unique ID preservation.
