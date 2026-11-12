# DB-6A — Favorites / Wishlist Design

**Date:** 2026-11-12  
**Status:** Design only; implementation waits for DB-0 SQL Server runtime baseline.

## 1. Goal and non-goals

Allow an authenticated student to save products for later and manage a private favorites list.

In scope: add/remove favorite, list the current user's favorites with pagination, show current product status, prevent duplicates, and prevent one user from reading or changing another user's favorites.

Not in scope: reserving a product, creating a purchase request, changing product status, public wishlists, notifications, price alerts, recommendations, report workflows or media uploads.

A favorite is an expression of interest only. It must never imply a purchase request or reserve a product.

## 2. Proposed data model

### dbo.USER_FAVORITES

| Column | Type | Nullable | Purpose |
|---|---|---:|---|
| user_id | INT | No | FK to dbo.USERS(user_id) |
| product_id | INT | No | FK to dbo.PRODUCTS(product_id) |
| created_at | DATETIME2(0) | No | UTC time when saved |

Constraints:
- Composite primary key (user_id, product_id); this prevents duplicates.
- Foreign keys to USERS and PRODUCTS, with no cascade delete in the first version.
- Default created_at = SYSUTCDATETIME().
- Index (user_id, created_at DESC, product_id DESC) for the user's paginated list.
- No surrogate identity column: the relation has no separate entity behavior in the MVP.

No ORM or SQL migration is written in this design step. SQL Server schema is authoritative; SQLite model tests do not validate SQL Server migration behavior.

## 3. API contract

All endpoints require the existing authenticated user cookie. The user ID is derived from get_current_user; clients never submit a user_id to select whose favorites are changed.

### Add — PUT /api/users/me/favorites/{product_id}

- Product must exist.
- Hidden product returns 404.
- Recommended rule: allow saving Available, Reserved or Sold products when the product detail endpoint still exposes them. Status may change after saving.
- Duplicate PUT is idempotent: return success without changing the original created_at.
- Do not mutate product status, transaction rows or inventory.

### Remove — DELETE /api/users/me/favorites/{product_id}

- Delete only the relation belonging to the authenticated user.
- Repeating DELETE is idempotent (recommended HTTP 204 whether or not a row existed).
- Do not reveal whether another user's favorite relation exists.
- Do not delete the product.

### List — GET /api/users/me/favorites

- Pagination: page >= 1, page_size 1..100; default 20.
- Stable order: created_at DESC, product_id DESC.
- Query is scoped to current user ID.
- Include favorite created_at and current product status.
- Never return email, student ID, password hash or private user data.
- Hidden product content must not leak through this endpoint. Retain the favorite relation but return a safe unavailable/tombstone representation rather than hidden description, price or seller-private data.
- Reserved and Sold may be shown with their current status; the frontend must not present a purchase action that bypasses existing transaction rules.

### Response shape proposal

The list returns a success envelope containing items with product_id, created_at and a product field, plus the existing pagination shape. The product field is nullable or a dedicated safe DTO for a Hidden listing; do not serialize the full Product ORM object for Hidden products.

## 4. Product lifecycle behavior

| Product state when favorited | Add? | List behavior later |
|---|---|---|
| Available | Yes | Show product as Available |
| Reserved | Yes, if detail remains visible | Show Reserved; no purchase/reserve action |
| Sold | Yes, if detail remains visible | Show Sold; no purchase action |
| Hidden | No; return 404 | Retain relation; redact product details |

If a product becomes Reserved or Sold after being favorited, retain the relation and show its current state. If it becomes Hidden, retain the relation but redact product details. If it becomes Available again legitimately, the saved item can appear normally again.

The first version does not define hard deletion of users/products. Since the proposed FKs do not cascade, a future deletion policy must explicitly define retention or cleanup behavior.

## 5. Authorization and privacy

- Add/remove/list derive user ID exclusively from the authenticated principal.
- No endpoint accepts target user ID for favorite management.
- A guessed product ID cannot be used to write another user's favorites.
- No public profile endpoint exposes favorites.
- Favorite ownership does not grant access to Hidden listing details.
- Favorites never mutate PRODUCTS.status, create TRANSACTIONS or bypass seller/buyer checks.
- No moderator/admin bypass is introduced.

## 6. ORM and transaction design

Proposed SQLAlchemy mapping: UserFavorite mapped to user_favorites with composite primary key user_id/product_id. Optional relationships to User/Product may be used for query convenience, but list serialization must not lazy-load once per item.

Add behavior:
1. Load product and verify it exists and is not Hidden.
2. Attempt insert under the composite primary key.
3. Handle concurrent duplicate inserts as idempotent success; roll back a failed unique insert before reading the existing row.
4. Do not change product or transaction rows.

Remove behavior: execute a scoped delete by both current user_id and product_id. No cross-user lookup.

List behavior: apply user_id=current_user.user_id in SQL before pagination; use deterministic ordering and a safe product DTO; avoid N+1 queries.

## 7. Frontend behavior after API implementation

- Add a favorite toggle on ProductCard and Product Detail.
- Unauthenticated users follow the existing auth pattern; never pretend a guest favorite was persisted.
- Use explicit selected/unsaved states with accessible labels, not icon color alone.
- Prevent double submission while add/remove is in flight.
- Add a private “Sản phẩm đã lưu” section in Account Center.
- Display Reserved/Sold status badges and disable purchase actions according to current state.
- For Hidden/unavailable products, show a neutral tombstone message and no private product fields.
- Provide loading, empty, error and retry states.
- Do not use localStorage-only favorites as a replacement for server persistence. Existing cart storage remains separate.

## 8. Test plan

Backend/API tests:
1. Add requires authentication.
2. User can add a visible product; relation stores current user ID and UTC timestamp.
3. Duplicate add is idempotent and does not reset created_at.
4. Hidden/nonexistent product cannot be newly favorited.
5. Reserved and Sold follow the documented add policy.
6. Delete removes only the current user's relation.
7. Repeated delete returns the documented idempotent response.
8. User A never receives User B favorites.
9. Pagination/order is stable with equal timestamps.
10. Hidden product payload is redacted; relation is retained.
11. Product status changes after add are reflected on next list read.
12. Favorites do not mutate product status or create transactions.
13. Concurrent duplicate adds result in one row and a stable success response.

SQL Server integration tests on the dedicated test database:
- Table/PK/FK/default/index metadata.
- Composite primary key prevents duplicates.
- FK prevents dangling references.
- Concurrent duplicate inserts behave as expected on SQL Server.
- Query ordering/pagination against SQL Server.
- No surprising cascade behavior.

Frontend build and interaction tests:
- Toggle add/remove and pending state.
- Account favorites loading/empty/error states.
- Status-aware UI for Reserved/Sold/Hidden.
- Keyboard labels/focus and accessible selected state.
- Current cart and purchase-request flows remain unaffected.

## 9. Implementation gates

- Run DB-0 schema diagnostic on the dedicated SQL Server test DB.
- Compare actual table/index/constraint metadata and naming conventions.
- Verify backup/recovery before migration against any database with existing data.
- Implement migration, ORM model, schemas/routes and tests on an isolated feature branch.
- Run backend tests and SQL Server-specific tests; SQLite alone is insufficient.
- Update API contract and frontend only after backend semantics are stable.

**DB-6A design result:** the favorite relationship, privacy boundary, status behavior, API semantics, concurrency handling and test plan are specified. No migration, endpoint, ORM model or frontend behavior was changed.
