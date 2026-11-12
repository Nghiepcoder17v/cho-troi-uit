# DB-0 — Source-level Data and Database Baseline

**Date:** 2026-11-12  
**Repository:** `Nghiepcoder17v/cho-troi-uit`  
**Base:** `main` at `b04d4b90cddedf286a5a4f9d7f2a9534867681fa`  
**Scope:** Read-only review of ORM, API schemas/routes, SQL initialization, versioned migrations, ETL extraction and SQL Server integration-test documentation.

## 1. Executive result

The repository source confirms that the current application has users, products, transactions and reviews, but does not yet implement:
- User bio or avatar references.
- Product media metadata or media upload/read/delete/reorder endpoints.
- An append-only transaction event history.

The existing transaction row stores its current status and timestamps. It does not preserve each intermediate status transition.

**DB-0 status: source audit completed; live SQL Server schema baseline remains unverified in this session.** No database connection, schema query, backup, migration or data write was performed.

## 2. Source schema baseline

### USERS

Current SQL initialization defines:
- `user_id`, `student_id VARCHAR(8)`, `email`, `password_hash`, `full_name NVARCHAR(100)`, `major NVARCHAR(50)`, `created_at`, `updated_at`.
- Unique constraints for student ID and email.
- An eight-digit student ID check and UIT email check.

Missing from the current source schema: `bio` and avatar/media reference.

### PRODUCTS

Current SQL initialization defines:
- `product_id`, `seller_id`, `category_id`, `title`, `description`, `price`, `condition`, `status`, `created_at`, `updated_at`.
- Foreign keys to users/categories and checks for price, condition and status.

Missing from the current source schema: product media relation, storage key and image metadata.

### TRANSACTIONS

Current SQL initialization and ORM define:
- `transaction_id`, `product_id`, `buyer_id`, `amount`, `status`, `transaction_date`, `updated_at`, `buyer_confirmed_at`, `seller_confirmed_at`.
- Current status values: Pending, Accepted, Completed, Cancelled.
- A filtered unique index protects the active-product purchase workflow.

Missing from the current source schema: an append-only table recording every event, actor, transition and event timestamp.

### REVIEWS

The current source schema includes `REVIEWS`, with transaction/user foreign keys, rating constraints, comment limit and uniqueness per transaction/reviewer.

## 3. Current API surface relevant to upcoming work

- `GET /api/users/me` returns the authenticated user DTO.
- `PATCH /api/users/me` currently accepts full name and major only.
- `GET /api/users/{user_id}/public-profile` returns name, major, join date and reputation fields; it does not expose email, student ID or password hash.
- `GET /api/products` currently supports category, status, keyword and pagination. It does not support price range, condition filtering or sorting requested by DB-5.
- Product create/update/read responses do not contain media.
- Transaction routes update the current transaction row and commit; they do not insert status-history events.

The public product list enforces Available status. Existing owner editing rules keep Reserved and Sold products read-only; future media mutations must preserve these rules.

## 4. Existing migration inventory reviewed

- `20261110_purchase_requests.sql` — adds buyer/seller confirmation timestamps and aligns product/transaction status constraints.
- `20261110_reviews.sql` — adds the reviews table and indexes.
- `20261111_student_id_length.sql` — validates existing IDs, adjusts the column to VARCHAR(8), and restores uniqueness/check constraints.
- `20261111_dwh_product_scd2.sql` — DWH-only product dimension migration; it is not an OLTP migration.

The migration convention is versioned additive T-SQL. The ORM model documentation explicitly states that SQL scripts are the schema source of truth and backend ORM does not create or alter application tables.

## 5. ETL/DWH impact baseline

The current ETL extracts explicit columns:
- Users: user ID, student ID, full name, major and timestamps; it excludes email and password hash.
- Products: product ID, category, title, condition, price, status and timestamps.
- Transactions: transaction/product/buyer/seller identifiers, amount, status and transaction/listing timestamps.

The ETL does not currently select avatar, bio or image URL/key fields. Keep profile/media data out of the DWH in this scope; do not broaden ETL extraction as a side effect of OLTP media work.

## 6. SQL Server verification and migration safety

Repository documentation records previous local SQL Server integration checks against a dedicated `*_test` database and a separate local database named `UIT_Exchange`. Those historical records are useful evidence, but they do not prove the current schema of a live database at this moment.

This session did not have a SQL Server connection or credentials exposed through the repository connector. Therefore it did not:
- Query `sys.tables`, `sys.columns`, constraints, indexes or triggers on the current target database.
- Verify which migrations are applied to the current target database.
- Inspect row counts or existing data.
- Create or verify a backup.
- Execute any migration.

Safety rules retained:
1. Never run `database_scripts/01_init_schema.sql` on an existing database with data to preserve; it is a destructive fresh-install script.
2. Never run `--drop-dwh` in this work.
3. Use additive, versioned T-SQL migrations for existing databases.
4. Verify a dedicated SQL Server test database whose name ends in `_test`; SQLite is not sufficient for SQL Server-specific migration verification.
5. Before any migration against a database with data, verify a restorable backup and document rollback/recovery.

## 7. Files reviewed

- `backend/models.py`
- `backend/schemas.py`
- `backend/main.py`
- `backend/tests/test_account.py`
- `backend/tests/test_products.py`
- `database_scripts/01_init_schema.sql`
- `database_scripts/migrations/20261110_purchase_requests.sql`
- `database_scripts/migrations/20261110_reviews.sql`
- `database_scripts/migrations/20261111_student_id_length.sql`
- `database_scripts/migrations/20261111_dwh_product_scd2.sql`
- `docs/api_contract.md`
- `docs/SQLSERVER_INTEGRATION_TESTING.md`
- `data_pipeline/etl/extract.py`
- `data_pipeline/etl/transform.py`
- `docker-compose.yml`
- `docs/DOCKER_COMPOSE.md`

## 8. Next safe step

Proceed with DB-1 media architecture and API/schema design as a documentation-only step. Do not write migration or application code until:
- The target SQL Server test schema has been inspected.
- The production/deployment object-storage provider and URL access policy are decided.
- The database backup and migration plan are available for the actual target.
