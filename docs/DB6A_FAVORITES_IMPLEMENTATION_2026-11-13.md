# DB-6A — Favorites / Wishlist Implementation

**Date:** 2026-11-13  
**Status:** Backend/API implementation merged; additive migration and SQL Server integration suite verified on an ephemeral GitHub Actions SQL Server 2022 database. The migration has not been applied to the user's local, shared or production database by this work.

## Scope

- Add `dbo.USER_FAVORITES` with composite primary key `(user_id, product_id)`, foreign keys to USERS/PRODUCTS and UTC created_at default.
- Add the SQLAlchemy relation model, private response DTOs and authenticated endpoints:
  - `PUT /api/users/me/favorites/{product_id}`
  - `DELETE /api/users/me/favorites/{product_id}`
  - `GET /api/users/me/favorites`
- Derive ownership exclusively from `get_current_user`. The client cannot select another account's user ID.
- PUT is idempotent, including concurrent duplicate inserts; DELETE is idempotent and scoped by both current user and product.
- Allow visible Available/Reserved/Sold products. Reject Hidden or nonexistent products.
- Keep a saved relation when a product becomes Hidden, but return `product: null` and only the relation's product ID, current Hidden status and created_at.
- Paginate on the server with deterministic `created_at DESC, product_id DESC` ordering.
- Do not mutate PRODUCTS.status, create TRANSACTIONS, or affect the cart flow.

## Safety

- Migration is additive. It was applied twice successfully to a newly created, disposable `ChoTroUIT_DB6A_Test` database inside the GitHub Actions SQL Server service container. It was not applied to the user's application database, `UIT_Exchange`, `ChoTroUIT` or DWH.
- No destructive base schema script, DWH command, production storage provider or unrelated table is changed.
- Foreign keys use SQL Server's default NO ACTION behavior; no cascade delete is introduced.
- The response intentionally excludes seller email/student ID and product description.

## Verification

- Backend unit/API tests cover authentication, idempotency, lifecycle states, Hidden tombstone redaction, ownership, privacy and stable pagination.
- Opt-in SQL Server integration tests verify exact columns/types, composite PK order, both FK targets/no-cascade behavior, descending index order, UTC default, duplicate rejection and FK enforcement.
- A SQL Server HTTP integration test exercises FastAPI GET/PUT/DELETE endpoints through a dedicated SQL Server engine pool; it verifies the SQL Server query hint path, authentication, ownership, idempotency, redaction, Hidden tombstones and that no transaction is created. Test records are explicitly cleaned up in finally.
- Run SQL Server integration tests only after applying the migration to a dedicated database whose name ends in `_test`.
- SQLite tests do not substitute for SQL Server migration/integration verification.


## SQL Server CI verification — 2026-11-13

<badge>Verified on ephemeral SQL Server 2022</badge>

- SQL Server workflow: [run #3](https://github.com/Nghiepcoder17v/cho-troi-uit/actions/runs/43408035840) — Success.
- Standard CI: [run #73](https://github.com/Nghiepcoder17v/cho-troi-uit/actions/runs/43408035719) — Success; Frontend build, Backend tests/lint and Data Pipeline tests/lint all passed.
- Workflow #3 provisioned a SQL Server 2022 Developer container and a new database named `ChoTroUIT_DB6A_Test`. It applied the current base schema inside that disposable database, then ran `20261113_user_favorites.sql` twice.
- All 6 SQL Server integration tests passed, including the FastAPI Favorites HTTP round trip using the SQL Server dialect/pool. The test verified auth, duplicate PUT idempotency and stable `created_at`, per-user ownership, response redaction, Hidden tombstones and no transaction creation.
- The normal backend CI ran `89 passed, 6 skipped`; those six opt-in SQL Server tests were executed separately and passed in workflow #3.

**Important scope:** this verifies the migration and application behavior against the disposable GitHub Actions database only. It does not mean the migration has been applied to any database used by the application or by the user.
