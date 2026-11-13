# DB-6 rollout readiness checklist

**Scope:** controlled rollout of the DB-6A Favorites, DB-6B Product Reports, DB-6C Moderation, and DB-6D Admin Controls migrations to an existing OLTP database.

**Status:** preparation only. This checklist is not evidence that a production database is configured, backed up, migrated, or approved.

## 1. Preconditions — stop unless all are true

- [ ] Identify the exact SQL Server instance and OLTP database from the approved deployment record.
- [ ] Confirm the deployed backend artifact contains the DB-6A through DB-6D code and migrations from an approved main commit.
- [ ] Confirm the existing database has the expected base schema and prerequisite tables `dbo.USERS` and `dbo.PRODUCTS`.
- [ ] Confirm the current migration state. Do not assume a migration is absent just because a table is not visible in an application screen.
- [ ] Assign an operator/DBA, application owner, change ticket, maintenance window, and recovery owner.
- [ ] Take a full backup of the target OLTP database and verify that it can be restored to an isolated SQL Server instance. Record the backup identifier and restore-test result.
- [ ] Decide how application writes will be paused or coordinated during the schema change and how writes after the backup will be protected during recovery.

**Hard stop:** no verified restore, unknown target database, uncertain migration state, or no approved change ticket means no migration.

## 2. Identify the actual backend SQL principal

The repository reads `DATABASE_URL` from the backend runtime environment. Do not infer the identity from a CI `sa` account, local Docker Compose, a developer workstation, or `.env.example`.

A read-only diagnostic is provided at `backend/diagnose_sql_principal.py`. Run it inside the exact backend image/container with the same `DATABASE_URL` environment as the deployed API. Set the approved database name explicitly:

~~~powershell
docker exec -e EXPECTED_OLTP_DATABASE="<approved_database_name>" <backend_container_name> python diagnose_sql_principal.py
~~~

For a local backend process, run it from the `backend` directory with the same environment configuration:

~~~powershell
$env:EXPECTED_OLTP_DATABASE = "<approved_database_name>"
python diagnose_sql_principal.py
Remove-Item Env:EXPECTED_OLTP_DATABASE
~~~

The diagnostic prints the server, original/effective login, database user, database name, and membership in `sysadmin` / `db_owner`. It does not print the connection string or password. It exits with code 2 when the expected database is missing/mismatched or the runtime principal is `sysadmin` / `db_owner`.

- [ ] Match the output to the approved server/database record.
- [ ] Confirm the returned server login maps to the expected database user.
- [ ] Confirm the runtime principal is neither `sysadmin` nor `db_owner`.
- [ ] Record the identity and diagnostic result in the change ticket, but never record credentials.
- [ ] Have the DBA separate schema-migration authority from the backend runtime principal.

If the diagnostic reports `sa`, `sysadmin`, or `db_owner`, stop. Do not attempt to make an elevated principal safe by granting/denying permissions on only one table.

## 3. Prepare the audit-table permission boundary

After the actual runtime principal is positively identified and approved:

- [ ] Grant the runtime database user only `SELECT` and `INSERT` on `dbo.USER_ROLE_ASSIGNMENT_EVENTS`.
- [ ] Deny `UPDATE` and `DELETE` on that table to the runtime database user.
- [ ] Verify the runtime user cannot bypass those restrictions through `sysadmin`, `db_owner`, object ownership, or another privileged role.
- [ ] Keep `CREATE` / `ALTER` / `DROP` permissions with a separate migration/operator principal.
- [ ] Test the positive and negative permissions using the same runtime identity on a non-production clone before production change.

Do not generate or apply a `GRANT` / `DENY` statement until the real server login and database user have been confirmed. Do not use a guessed principal name.

## 4. Apply additive migrations in dependency order

The DB-6 workflow uses this order:

1. `database_scripts/migrations/20261113_user_favorites.sql` — DB-6A.
2. `database_scripts/migrations/20261113_product_reports.sql` — DB-6B.
3. `database_scripts/migrations/20261113_db6c_moderation.sql` — DB-6C.
4. `database_scripts/migrations/20261113_db6d_role_assignment_events.sql` — DB-6D.

Before **each** file, have the DBA verify the connection target:

~~~sql
SELECT @@SERVERNAME AS server_name, DB_NAME() AS database_name;
~~~

Then execute only the approved migration file against the approved OLTP database, using the separate migration/operator identity. With Windows Authentication, the command shape is:

~~~powershell
sqlcmd -S "<approved_server>" -d "<approved_database>" -E -b -i "database_scripts/migrations/<approved_migration_file>.sql"
~~~

Replace the file placeholder with exactly one path from the ordered list above. Check the exit code and full output before proceeding to the next file. Use the approved secret-management method if SQL Authentication is required; do not place passwords in source control or this runbook.

- [ ] DB-6A completed and verified before DB-6B.
- [ ] DB-6B completed and verified before DB-6C.
- [ ] DB-6C completed and verified before DB-6D.
- [ ] Record each exact file, deployed commit, target database, execution time, operator, and result.

The SQL Server CI workflow applies these four migrations twice to a disposable `*_test` database to verify idempotency. That test does not replace a production backup, a restore test, or a controlled one-time rollout.

**Never run** `database_scripts/01_init_schema.sql` or `02_seed_reference_data.sql` as a substitute for these migrations on an existing database. The base schema contains destructive reset behavior. Docker `db-init` is a local initialization check and does not run these migrations automatically.

## 5. Verify the schema and application

After the migration sequence, verify at minimum that the following objects exist:

- DB-6A: `dbo.USER_FAVORITES`.
- DB-6B: `dbo.PRODUCT_REPORTS`.
- DB-6C: `dbo.ROLES`, `dbo.USER_ROLE_ASSIGNMENTS`, `dbo.MODERATION_ACTIONS`, `dbo.PRODUCT_MODERATION`.
- DB-6D: `dbo.USER_ROLE_ASSIGNMENT_EVENTS`.

Also inspect the named foreign keys, check constraints, filtered unique indexes, and DB-6C report status constraint in SQL Server metadata. A table-exists check alone is insufficient.

- [ ] Backend health endpoint responds successfully.
- [ ] Normal authenticated account can read its own permissions and receives no elevated roles unless assignments exist.
- [ ] Authenticated non-admin account receives 403 from Admin Controls endpoints.
- [ ] Public product listing/detail surfaces continue respecting active moderation holds.
- [ ] Existing transactions and seller-owned listing statuses remain unchanged by report intake.
- [ ] Review server and application logs for SQL errors, lock timeouts, and failed requests.

The first ADMIN bootstrap is a separate, explicitly approved operator action described in [DB-6C Moderator Bootstrap](DB6C_MODERATOR_BOOTSTRAP_RUNBOOK.md). Verify the target account and approval ticket before running the one-time bootstrap script. The DB-6D application audit table records subsequent admin-managed grants/revocations; preserve the bootstrap execution result in the operator change record.

## 6. Recovery and rollback boundaries

These migrations are additive/idempotent but do not provide a general down-migration sequence. Do not improvise by dropping tables, constraints, or indexes after a partial failure.

- Stop the rollout on the first SQL error; do not continue to later migrations.
- Keep application deployment and database migration decisions coordinated. Do not run newer application code against a partially migrated database.
- Have the DBA assess whether a forward corrective migration is safer than restoring.
- If restore is required, use the verified recovery procedure and explicitly account for application writes that occurred after the backup. Never perform a blind restore that silently discards newer business data.
- Preserve SQL output, application logs, backup metadata, and the change record.

Do not use `--drop-dwh`; these OLTP migrations do not require a DWH rebuild.

## 7. Final approval record

Production rollout is complete only when the deployment owner records: target server/database, deployed commit, backup and restore verification, confirmed backend principal, permission test, four migration outcomes, schema checks, application smoke-test results, initial ADMIN approval (if enabled), and recovery decision.

A green GitHub workflow proves tests against an isolated disposable database. It does not prove production identity, production schema state, backup recoverability, or deployment approval.
