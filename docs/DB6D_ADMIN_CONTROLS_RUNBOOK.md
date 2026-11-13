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

The first ADMIN remains an operator/DBA-controlled action described in DB6C_MODERATOR_BOOTSTRAP_RUNBOOK.md. DB-6D does not make the first administrator self-service and does not select or grant a role to a real user. That first bootstrap assignment is recorded by the assignment row and the operator's approved change record; the application event table records subsequent ADMIN-managed grant/revoke actions.

## Scope

The application UI does not suspend accounts, edit user profiles, change reason codes, delete users, or grant unknown role codes. There is no bulk role operation. Do not run the destructive base schema on a database with data to preserve. Do not run migrations against the application database without backup/restore verification and explicit operational approval.

## Audit storage

The migration creates a distinct event table. The application only inserts and reads events. It does not grant SQL permissions or claim database-level append-only enforcement, because the production SQL Server principal has not been identified. Before production deployment, configure the actual application principal to read/insert events without update/delete and use a separate operational owner for schema changes.


## Production SQL principal — mandatory preflight

The repository does not contain a production connection string or identify the production SQL Server login/database user. `backend/database.py` reads `DATABASE_URL` from the runtime environment. The committed `.env.example` contains placeholders, while local Docker Compose currently connects the backend as SQL Server `sa`; neither is evidence of the production principal.

Before changing permissions, run this read-only query through a connection created by the actual deployed backend process, against the intended OLTP database:

```sql
SELECT
    ORIGINAL_LOGIN() AS original_login,
    SUSER_SNAME() AS effective_server_login,
    USER_NAME() AS database_user,
    DB_NAME() AS database_name,
    IS_SRVROLEMEMBER('sysadmin') AS is_sysadmin,
    IS_MEMBER('db_owner') AS is_db_owner;
```

Record the returned identity and database in the approved change ticket, without recording or sharing the connection string or password. Have the DBA verify the login-to-database-user mapping and confirm that the runtime principal is not `sysadmin` or `db_owner`. Do not infer the principal from CI, local Compose, a developer shell, or a sample environment file.

After the identity is confirmed, the runtime principal should receive only the permissions needed on `dbo.USER_ROLE_ASSIGNMENT_EVENTS`: `SELECT` and `INSERT`, with `UPDATE` and `DELETE` denied. Schema migration rights must remain with a separate operator/DBA principal. A deny on the event table does not provide meaningful protection if the application runs as `sa`, `sysadmin`, `db_owner`, or the object owner.

This preflight is documentation only. It does not change SQL permissions, run migrations, perform the initial ADMIN bootstrap, or authorize production deployment. Those actions remain blocked until the principal is confirmed, backup-and-restore has been verified, and the deployment has explicit operational approval.
