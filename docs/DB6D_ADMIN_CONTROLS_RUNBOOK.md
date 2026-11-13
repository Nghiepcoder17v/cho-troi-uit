# DB-6D role management — operations boundary

DB-6D adds admin-only application controls for granting and revoking the two fixed DB-6C roles: MODERATOR and ADMIN.

## Authority model

- Only a currently active ADMIN assignment authorizes role-management endpoints.
- Authority is checked from SQL on every request. No role claim is copied into the JWT.
- An administrator cannot grant, revoke, or otherwise change their own role assignment.
- The final active ADMIN assignment cannot be revoked. A second ADMIN must be granted first.
- A role grant/revoke requires a reason (8–250 characters).
- Role assignment rows preserve granted/revoked attribution. USER_ROLE_ASSIGNMENT_EVENTS records each GRANTED/REVOKED event in the same database transaction.

## Initial bootstrap

The first ADMIN remains an operator/DBA-controlled action described in DB6C_MODERATOR_BOOTSTRAP_RUNBOOK.md. DB-6D does not make the first administrator self-service and does not select or grant a role to a real user.

## Scope

The application UI does not suspend accounts, edit user profiles, change reason codes, delete users, or grant unknown role codes. There is no bulk role operation. Do not run the destructive base schema on a database with data to preserve. Do not run migrations against the application database without backup/restore verification and explicit operational approval.

## Audit storage

The migration creates a distinct event table. The application only inserts and reads events. It does not grant SQL permissions or claim database-level append-only enforcement, because the production SQL Server principal has not been identified. Before production deployment, configure the actual application principal to read/insert events without update/delete and use a separate operational owner for schema changes.
