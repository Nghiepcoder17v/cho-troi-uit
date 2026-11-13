# DB-6C controlled moderator bootstrap

## Purpose

DB-6C creates the role catalog but does **not** assign MODERATOR or ADMIN to any user. Registration and profile APIs cannot grant authority. The first elevated reviewer must be selected and authorized outside the application.

## Initial reviewer

The first reviewer is bootstrapped as ADMIN. This resolves the escalation path: a MODERATOR can escalate a report, and only an ADMIN can claim an Escalated report. The first ADMIN must be an explicitly approved, trusted operator account. Verify the user_id against the intended user record and approval ticket.

## Operator procedure

1. Approve a named account and record the authorization/change ticket.
2. Take and verify the normal database backup required by the deployment process.
3. Confirm DB-6B and DB-6C additive migrations have been applied to the intended database.
4. Review database_scripts/operations/20261113_db6c_initial_admin_bootstrap.sql; set @TargetUserId and @ApprovalReference explicitly.
5. Have the authorized DBA/operator execute that one-time script in the intended database, then verify the returned active assignment.
6. Keep the execution result and ticket in the operational change record. Do not store credentials or secrets in the repository.

The bootstrap script does not run automatically and is not part of CI migrations. Its NULL placeholders are intentional fail-closed guards. It assigns only one ADMIN role; DB-6D will own the administrative UI for later role grants/revocations.

## Revoke authority

Role revocation is performed by closing the active row in USER_ROLE_ASSIGNMENTS with revoked_at, revoked_by_user_id, and a reason. The protected API checks active assignments from SQL on every request, so revocation applies to the next protected request. Until DB-6D delivers a reviewed admin interface, revocation is an operator-controlled database change under the deployment's approval and backup procedures.

## Audit and permissions

MODERATION_ACTIONS records moderation workflow events in the same transaction as the corresponding state change. The migration does not issue GRANT statements or claim append-only enforcement: the production application principal has not been identified in repository configuration. Before production rollout, identify the actual application principal and configure it to read/insert audit rows without update/delete, with separate operational-owner permissions. Do not assume the CI sa principal is the production principal.

## Safety boundaries

- Never grant a role from self-registration, profile update, or client-supplied fields.
- Never use seller-controlled PRODUCTS.status='Hidden' for a moderation hold.
- A report submission does not hide a listing.
- DB-6C does not suspend accounts, cancel transactions, delete products, issue email notifications, add appeals, or purge report/audit history.
- The moderation hold is public-visibility-only and remains until an authorized moderator explicitly releases it. Existing transaction state is untouched.
- Do not execute the destructive base-schema script against a database with data to preserve. Never use --drop-dwh.
