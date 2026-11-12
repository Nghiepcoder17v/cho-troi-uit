# DB-4 — Transaction Event History Implementation

**Date:** 2026-11-12  
**Status:** Backend/API implementation prepared in PR; SQL Server migration is additive and has not been executed by this change.

## Scope in this PR

- Add `dbo.TRANSACTION_EVENTS` through `20261112_transaction_events.sql`.
- Add the SQLAlchemy `TransactionEvent` model and Pydantic event DTO.
- Record request, accept, reject, buyer/seller cancel, buyer/seller confirm and completion milestone events in the same database transaction as the business operation.
- Extend the existing authenticated purchase/sales history responses with an ordered `events` array.
- Load events in one bulk query for the history page, using a LEFT OUTER JOIN for nullable system actors.
- Keep existing events insert/read-only at the application API layer; no update/delete endpoint is introduced.
- Keep legacy transactions without event rows as an empty array. No event backfill is performed.

## Atomicity and concurrency details

- Request creation flushes the transaction ID, stages its initial event and commits once with the product reservation.
- Seller accept/reject and participant cancellation stage an event only after their conditional state update succeeds. Reject/cancel also wait until the product release succeeds before commit.
- Cancellation now compares against the status read for the operation. A concurrent status transition no longer produces a cancellation event with an inaccurate `from_status`.
- Confirmation stages the actor event only after the conditional confirmation succeeds. If the second confirmation completes the transaction, product Reserved → Sold, actor confirmation and exactly one NULL-actor `TRANSACTION_COMPLETED` milestone commit together.
- Failed state updates and failed product transitions roll back their event rows with the business mutation.

## Database safety and permissions

- The migration creates only one new table and one supporting index. It does not alter existing transaction constraints or the filtered unique index.
- The migration is not executed against any database by this PR.
- No synthetic history is inserted for pre-existing transactions.
- The current SQL Server application principal's grants were not changed by this PR. Database-level denial of UPDATE/DELETE must be applied only after the exact principal and ownership model are verified. Therefore this implementation does not claim database-enforced immutability; the API exposes no mutation route and application code only inserts/selects events.
- Do not run `database_scripts/01_init_schema.sql` on a database with data to preserve. Do not run `--drop-dwh`.

## Verification still required

- CI backend tests and lint.
- Apply the migration to a dedicated SQL Server database ending in `_test`, then run the SQL Server event-table metadata and transaction atomicity checks.
- Confirm application-principal permissions and concurrent confirmation/cancellation behavior on SQL Server; SQLite tests do not prove SQL Server locking semantics.
- No live or production database was modified by this PR.
