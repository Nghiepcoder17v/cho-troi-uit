# DB-6D Admin Controls — Design and Implementation

**Date:** 2026-11-13  
**Base:** DB-6C merge commit `63242a013ff0f4d243ed5fa8754d7b33a6dd3723`  
**Scope:** Controlled management of the existing `MODERATOR` and `ADMIN` roles.

## 1. Objective

DB-6D completes the role-provisioning boundary deferred by DB-6C. It provides an ADMIN-only interface to locate an existing student account, grant or revoke a fixed role, and inspect the associated assignment and audit history.

The first ADMIN remains an operator/DBA bootstrap operation described in `DB6C_MODERATOR_BOOTSTRAP_RUNBOOK.md`. DB-6D does not let a normal student promote themselves or bootstrap the first administrator.

## 2. Approved defaults

| Decision | DB-6D behavior |
|---|---|
| Who can manage roles | Only an active `ADMIN` role assignment verified from SQL on every request |
| Grantable roles | Fixed values: `MODERATOR`, `ADMIN`; no arbitrary role codes |
| Target selection | Search existing users by name, student ID or UIT email; return only the minimal identity fields needed for operator confirmation |
| Self-change | An administrator cannot grant or revoke any role on their own account |
| Last administrator | The final active `ADMIN` assignment cannot be revoked |
| Reason requirement | Every grant/revoke requires a trimmed reason of 8–250 characters |
| Assignment history | Keep each assignment row; revocation closes the row rather than deleting it |
| Audit | Insert `GRANTED` / `REVOKED` event in the same transaction as assignment creation/update |
| Revocation latency | Authorization reads active assignments from SQL on the next protected request; no role claim is cached in JWT |
| Bulk actions | Out of scope |
| Account restrictions | No account suspension, deletion, profile editing or transaction mutation |

## 3. Security and consistency

- Backend authorization is mandatory on all `/api/admin/*` endpoints. Frontend navigation visibility is not an authorization control.
- Mutating role operations acquire a SQL Server update/serializable lock on the `ADMIN` role row first, then re-check and lock the actor's active ADMIN assignment. This serializes admin mutations and prevents an actor whose role was revoked while a request was waiting from continuing the operation.
- Target role and assignment locks are acquired in a consistent order. This protects against duplicate active assignments and concurrent role revocation.
- The last-active-ADMIN check runs while holding the `ADMIN` role-row lock. Concurrent administrators cannot both revoke each other and leave the system without an active administrator.
- Role assignment mutation and `USER_ROLE_ASSIGNMENT_EVENTS` insertion share one transaction. An audit insert failure must roll back the role change.
- No user-facing endpoint accepts actor IDs or actor role codes from the client.
- The event table is append-only by application behavior. Database-level UPDATE/DELETE denial is still a deployment task because the production SQL Server principal has not been identified; the app principal must not be guessed from CI's `sa` account.

## 4. API boundary

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/users/me/permissions` | Return the current user's active role codes for UI navigation |
| GET | `/api/admin/users?q=...` | Search existing student accounts with bounded pagination |
| GET | `/api/admin/role-assignments` | View active assignments or assignment history |
| GET | `/api/admin/role-events` | View role grant/revocation audit events |
| POST | `/api/admin/users/{user_id}/roles` | Grant MODERATOR or ADMIN with a reason |
| POST | `/api/admin/role-assignments/{assignment_id}/revoke` | Revoke an active assignment with a reason |

Unauthenticated callers receive 401; authenticated non-admin users receive 403. Duplicate grants, stale/repeated revocations and invalid state changes return conflict/bad-request responses rather than silently succeeding.

## 5. Data model

Migration `20261113_db6d_role_assignment_events.sql` adds `dbo.USER_ROLE_ASSIGNMENT_EVENTS` with:
- assignment ID, target user, role code;
- actor user and role snapshot;
- event code, required reason and UTC timestamp;
- foreign keys and bounded event/reason checks;
- indexes by target/time and assignment/time.

No existing assignment rows are rewritten, no roles are auto-assigned, and no user rows are changed by the migration.

## 6. Frontend

The top-level Admin navigation appears only for a session whose permissions endpoint reports `ADMIN`. The page provides:
- existing-account search;
- explicit selection of a target account;
- fixed-role grant with a required reason;
- active and revoked assignment history;
- revoke action with a required reason;
- recent role audit events.

The API remains the authority. A stale or manually altered frontend state cannot grant access. The page does not expose a first-admin bootstrap action.

## 7. Tests and delivery gate

- Unit tests cover unauthorized/non-admin access, successful grant/revoke, duplicate grant rejection, self-change rejection, immediate role revocation and atomic audit rollback.
- SQL Server integration verifies the actual event table/check constraints, transactional rollback when the audit insert fails, and concurrent admin revocations leaving exactly one active ADMIN.
- The SQL Server workflow applies DB-6A, DB-6B, DB-6C and DB-6D migrations twice in an isolated database ending in `_test`.
- The destructive base-schema script is used only in the newly created disposable CI database.
- No migration is executed against the user's application database; no initial ADMIN identity is selected or granted.
