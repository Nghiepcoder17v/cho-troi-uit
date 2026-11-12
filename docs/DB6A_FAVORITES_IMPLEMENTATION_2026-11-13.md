# DB-6A — Favorites / Wishlist Implementation

**Date:** 2026-11-13  
**Status:** Backend/API implementation and additive SQL Server migration prepared in PR; migration not executed by this change.

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

- Migration is additive and has not been run against any database by this PR.
- No destructive base schema script, DWH command, production storage provider or unrelated table is changed.
- Foreign keys use SQL Server's default NO ACTION behavior; no cascade delete is introduced.
- The response intentionally excludes seller email/student ID and product description.

## Verification

- Backend unit/API tests cover authentication, idempotency, lifecycle states, Hidden tombstone redaction, ownership, privacy and stable pagination.
- An opt-in SQL Server integration test verifies exact columns/types, composite PK order, both FK targets/no-cascade behavior, descending index order, UTC default, duplicate rejection and FK enforcement.
- Run SQL Server integration tests only after applying the migration to a dedicated database whose name ends in `_test`.
- SQLite tests do not substitute for SQL Server migration/integration verification.
