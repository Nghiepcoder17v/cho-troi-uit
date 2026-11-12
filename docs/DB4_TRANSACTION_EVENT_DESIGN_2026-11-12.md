# DB-4 — Transaction Event History Design

**Date:** 2026-11-12  
**Status:** Source-based design only; no migration or application code in this step.

## 1. Current source behavior

The current `TRANSACTIONS` row stores the latest status (`Pending`, `Accepted`, `Completed`, `Cancelled`), `transaction_date`, `updated_at`, `buyer_confirmed_at` and `seller_confirmed_at`.

Current backend transitions:

| Action | Transaction transition | Product behavior |
|---|---|---|
| Buyer creates request | New row → Pending | Available → Reserved |
| Seller accepts | Pending → Accepted | Remains Reserved |
| Seller rejects | Pending → Cancelled | Reserved → Available |
| Buyer or seller cancels | Pending/Accepted → Cancelled | Both confirmation timestamps are cleared; Reserved → Available |
| First party confirms | Accepted → Accepted | First confirmation timestamp is set |
| Second party confirms | Accepted → Completed | Reserved → Sold |

The purchase/sales history endpoints are authenticated and scope records to the current buyer or seller, but currently return only the latest state and timestamps. They do not return intermediate transitions.

**Important:** cancellation clears confirmation timestamps from the current transaction row. A separate event table is required to preserve a prior confirmation that happened before cancellation.

## 2. Proposed SQL Server table

Add `dbo.TRANSACTION_EVENTS` through a versioned additive migration only after DB-0 runtime schema verification and backup/recovery checks.

| Column | Proposed type | Nullable | Purpose |
|---|---|---:|---|
| `event_id` | `BIGINT IDENTITY(1,1)` | No | Primary key and stable ordering tie-breaker |
| `transaction_id` | `INT` | No | FK to `dbo.TRANSACTIONS(transaction_id)` |
| `actor_user_id` | `INT` | Yes | FK to `dbo.USERS(user_id)`; NULL only for system completion marker |
| `event_type` | `VARCHAR(32)` | No | Fixed event code |
| `from_status` | `VARCHAR(20)` | Yes | Status before the action; NULL for creation |
| `to_status` | `VARCHAR(20)` | No | Status after the action |
| `occurred_at` | `DATETIME2(0)` | No | UTC; default `SYSUTCDATETIME()` |

Do not add arbitrary note or JSON metadata in the first version. It is unnecessary for the requested timeline and risks storing unreviewed personal or security-sensitive content.

Constraints and indexes:
- PK on `event_id`.
- FKs to transactions and users, with no cascading delete.
- CHECK constraints for event codes and allowed transaction statuses.
- Index `(transaction_id, occurred_at, event_id)` for chronological reads.
- No speculative secondary indexes until actual query workload and SQL Server metadata are reviewed.

Do not change existing transaction constraints or the filtered unique index.

## 3. Event vocabulary

| Event code | Actor | from_status | to_status | Meaning |
|---|---|---|---|---|
| `REQUEST_CREATED` | Buyer | NULL | Pending | Purchase request successfully created |
| `SELLER_ACCEPTED` | Seller | Pending | Accepted | Seller accepts request |
| `SELLER_REJECTED` | Seller | Pending | Cancelled | Seller rejects request |
| `BUYER_CANCELLED` | Buyer | Pending or Accepted | Cancelled | Buyer cancels request |
| `SELLER_CANCELLED` | Seller | Pending or Accepted | Cancelled | Seller cancels request |
| `BUYER_CONFIRMED` | Buyer | Accepted | Accepted or Completed | Buyer's first successful confirmation |
| `SELLER_CONFIRMED` | Seller | Accepted | Accepted or Completed | Seller's first successful confirmation |
| `TRANSACTION_COMPLETED` | System; actor is NULL | Completed | Completed | One completion milestone after both confirmations |

Store stable event codes; user-facing labels belong in the frontend/API presentation layer.

### Two-party confirmation semantics

- First confirmation: event status remains Accepted → Accepted.
- Second confirmation: the actor's confirmation event records Accepted → Completed.
- In that same SQL transaction, insert exactly one system completion marker with Completed → Completed. This is a milestone, not a duplicate status transition.
- The final transaction update, product Reserved → Sold update, actor confirmation event and completion marker must commit or roll back together.
- Conditional confirmation updates ensure one participant cannot confirm twice. The second successful actor update is the only code path that inserts the completion marker.

### Cancellation after one confirmation

If one side confirms and the other side subsequently cancels:
1. Keep the earlier confirmation event unchanged.
2. Insert the actor-specific cancellation event with the actual transition Accepted → Cancelled (or Pending → Cancelled).
3. Preserve existing behavior that clears current confirmation timestamp columns.
4. Do not insert a completion marker.

This retains the audit sequence even though the current row no longer carries the old confirmation timestamp.

## 4. Atomic write rules

The event insert belongs in the same SQLAlchemy transaction as the business update. No separate commit is allowed.

| Action | Event insert point | Atomic operations |
|---|---|---|
| Create request | After transaction row flush returns its ID | Product claim, transaction insert, REQUEST_CREATED insert |
| Accept | After conditional update affects one row | Pending → Accepted and SELLER_ACCEPTED |
| Reject | After transaction update and product release both succeed | Pending → Cancelled, Reserved → Available, SELLER_REJECTED |
| Cancel | After conditional cancellation and product release both succeed | Status transition, clear confirmation columns, Reserved → Available, actor-specific cancellation |
| Confirm | After actor-specific conditional confirmation succeeds | Confirmation timestamp/status, actor confirmation; if completed, product → Sold and one completion marker |

Implementation constraints:
- For create, call `db.flush()` to get the transaction ID, add the event, then commit once.
- For reject/cancel, if product release fails, roll back the transaction status and event too.
- For confirm, if the product cannot transition Reserved → Sold, roll back the confirmation and event.
- Never create an event for authorization failure, missing row, invalid state, duplicate confirmation, failed conditional update or failed commit.
- For cancellation, the event's `from_status` must be the state actually updated. Use an update predicate matching the status read (or a SQL Server-safe locking/OUTPUT implementation after DB-0 review); a concurrent state change must produce a conflict, not an inaccurate event.
- Use UTC. For equal DATETIME2(0) timestamps, event_id is the deterministic tie-breaker.

## 5. History API

Extend existing authenticated purchase/sales history responses instead of adding a public event endpoint or issuing one query per transaction.

Each `TransactionHistoryOut` item gains an `events` array:

```json
{
  "events": [
    {
      "event_id": 21,
      "event_type": "REQUEST_CREATED",
      "from_status": null,
      "to_status": "Pending",
      "occurred_at": "2026-11-12T10:30:00",
      "actor": { "user_id": 12, "full_name": "Nguyễn Văn A" }
    }
  ]
}
```

- Add `TransactionEventOut` and an events list to `TransactionHistoryOut`.
- In `_transaction_history`, query events in bulk for returned transaction IDs, join actor users, group by transaction_id and order by occurred_at ASC, event_id ASC. Avoid N+1 queries.
- Existing endpoint scoping remains the access-control boundary: buyer sees only their purchases, seller sees only their sales. No unauthenticated or unscoped event endpoint.
- Return an empty array for legacy transactions without event rows.
- Do not expose arbitrary metadata.

## 6. Legacy transaction policy

Do not fabricate history for transactions created before event logging.

- `transaction_date` proves request creation time only; it does not reveal all intermediate actions.
- `updated_at` records a latest modification timestamp, not a complete transition sequence.
- Confirmation timestamps may have been cleared when a transaction was cancelled.
- A Completed row does not prove who confirmed first or the precise sequence.

The initial migration creates an empty event table. No synthetic events are backfilled. The frontend should explain that detailed event history was not recorded for legacy transactions when the API returns an empty array.

## 7. Append-only and security

- No user-facing UPDATE or DELETE endpoint for events.
- Application behavior is insert/select only.
- Do not cascade-delete events with transaction/user deletion.
- During DB-0 verification, inspect the actual SQL Server application principal. Where it is not the database owner, grant SELECT/INSERT and deny UPDATE/DELETE on this table for that principal. If the current connection principal has broader ownership rights, settle the least-privilege boundary before claiming database-enforced immutability.
- No admin/moderator access is added; that belongs to DB-6 role and audit policy.
- Never store passwords, tokens, email, student ID or unrelated personal content in the event log.

## 8. Frontend integration

Extend `TransactionHistory` with the event list and render an expandable chronological timeline inside each existing `OrderCard`.

- Keep current status, accept/reject/cancel/confirm actions and review editor unchanged.
- Show localized event label, actor (“Bạn”, the other participant, or “Hệ thống”) and localized time.
- Use API order; do not infer events client-side.
- For empty legacy arrays, show a clear “Giao dịch này được tạo trước khi hệ thống lưu lịch sử chi tiết” note.
- Expansion must be keyboard accessible and must not interfere with existing controls.
- Do not render mock events before the API is implemented.

## 9. Implementation test plan

Backend/API tests:
1. Create request inserts exactly one REQUEST_CREATED.
2. Accept and reject insert the correct actor and status values.
3. Buyer cancellation and seller cancellation use distinct event codes.
4. First confirmation records Accepted → Accepted.
5. Second confirmation records Accepted → Completed plus exactly one system completion marker; product becomes Sold.
6. Cancellation after one confirmation retains the confirmation event, adds cancellation and creates no completion marker.
7. Unauthorized actions, duplicate confirmation, invalid status and failed product update insert no event.
8. Forced failure before commit rolls back the state and event together.
9. Buyer/seller can retrieve only their own transaction timelines; outsider cannot.
10. Legacy transaction with no events returns an empty array and is not backfilled.
11. Equal timestamps are ordered by event_id.

SQL Server tests on the dedicated test database:
- Table/FK/CHECK/index/default metadata.
- Application principal insert/select and update/delete restrictions.
- Atomic rollback of event + transaction + product mutations.
- Concurrent confirmation/cancel behavior. SQLite unit tests alone do not prove SQL Server locking behavior.

## 10. Gates before implementation

- [ ] Complete DB-0 diagnostics on a dedicated SQL Server database with the required test suffix.
- [ ] Verify actual target schema and applied migrations.
- [ ] Verify a restorable backup and migration recovery plan before changing a database with data.
- [ ] Verify application SQL Server principal and event-table permissions.
- [ ] Implement migration/model/DTO/event writes/history read and frontend timeline in separately reviewable changes as appropriate.
- [ ] Never run destructive `database_scripts/01_init_schema.sql` against an existing database.
- [ ] Do not run `--drop-dwh`; do not add event data to ETL/DWH in this scope.

**DB-4 result:** event vocabulary, state semantics, atomicity, legacy handling, participant access, frontend treatment and the test plan are defined. This is a design-only deliverable; no application behavior, migration or live database was changed.
