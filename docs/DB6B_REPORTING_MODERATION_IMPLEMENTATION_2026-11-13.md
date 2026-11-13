# DB-6B — Product Report Intake Implementation

**Date:** 2026-11-13  
**Policy state:** Product Owner approved the DB-6B defaults for product-only reporting.  
**Implementation boundary:** report submission only; no moderator workflow or sanctions.

## Approved intake behavior

- Reports target product listings only; user-account reports are excluded.
- Allowed reasons: PROHIBITED_ITEM, MISLEADING_LISTING, SUSPECTED_SCAM, SPAM_OR_DUPLICATE, OTHER.
- Optional plain-text description, maximum 500 characters. No attachments.
- Only publicly visible Available and Sold listings may be reported. Missing, seller-hidden (Hidden) and reserved listings are rejected.
- A seller cannot report their own listing.
- One open (Submitted) report per reporter/product. The filtered unique index is the database-level race-condition guard. A later report may be submitted after a future authorized workflow resolves the earlier report.
- Maximum five successful submissions per account in any rolling 24-hour period. SQL Server locks the reporter row while checking/inserting to serialize concurrent requests from the same account.
- The server derives the reporter ID from the authenticated cookie. Client-supplied reporter IDs, state and authority fields are rejected.
- No seller notification; no reporter identity is disclosed in the receipt.
- A report is an allegation/request for review, not a finding of a violation.

## API

POST /api/reports requires the authenticated UIT student cookie.

Request fields:
- target_product_id: positive product ID.
- reason_code: one of the five approved reason codes.
- description: optional plain-text context, maximum 500 characters.

The 201 response returns report_id, target_product_id, reason_code, status=Submitted and submitted_at. It intentionally excludes reporter identity and description. There is no report-list endpoint in this slice.

## Data model and safety

Migration: database_scripts/migrations/20261113_product_reports.sql.

- dbo.PRODUCT_REPORTS stores reporter/product FKs, reason code, optional description, status and UTC timestamps.
- Both FKs use NO ACTION; report history is not cascade-deleted when a user or product is removed.
- A filtered unique index on (reporter_user_id, target_product_id) where status is Submitted prevents duplicate open submissions.
- No base-schema reset, data backfill, production connection or live database migration is included.
- Submission does not update PRODUCTS.status, create transactions, send notifications or apply sanctions.

## Explicitly not implemented

DB-6B does not add:
- Moderator/admin roles or role provisioning.
- Moderator queue, assignment, review, dismissal, escalation or action endpoints.
- Product takedown/moderation hold, seller warnings, account suspension or other sanctions.
- Report attachments, public report lists, own-report history/status page or seller notifications.
- Account reports, appeals or reinstatement.
- A retention duration or automated purge policy.

The status CHECK constraint currently allows only Submitted. DB-6C must be separately designed and approved before adding workflow states, moderator access or resolution actions. The exact retention period remains unresolved; this migration deliberately preserves rows and does not implement deletion.

## Verification gates

- SQLite unit tests cover request validation, authentication, self-report rejection, target eligibility, duplicate prevention, ownership privacy, no listing mutation and rolling rate limit.
- Opt-in SQL Server integration tests require RUN_SQLSERVER_INTEGRATION=1 and a SQLSERVER_TEST_DATABASE_URL whose database name ends in _test.
- The dedicated GitHub Actions workflow provisions a disposable SQL Server 2022 container and database, applies the base schema only inside that new database, applies the Favorites and Product Reports migrations, and runs the DB-6B SQL Server tests.
- Never run database_scripts/01_init_schema.sql against an existing database whose data must be preserved. This PR does not apply migrations to the user's app database.
