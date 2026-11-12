# DB-6B — Product Report Intake and Moderation Design

**Date:** 2026-11-13  
**Status:** Proposal for Product Owner review. Design only; no schema, API, role, sanction or policy behavior is implemented by this document.

## 1. Goal and delivery boundary

Introduce a private, authenticated way for a UIT student to report a potentially abusive or misleading product listing.

This is the first slice of the DB-6 moderation roadmap:

| Stage | Scope | Explicitly out of scope |
|---|---|---|
| **DB-6B — Report intake** | Product-listing report submission, private reporter ownership, validation, duplicate/rate controls, optional own-submission status view | Moderator decisions, listing takedown, user sanctions, role provisioning, evidence uploads |
| **DB-6C — Minimal moderator workflow** | Backend-authorized moderator queue, review/dismiss/action/escalate decisions, separately audited moderation actions | Role granting, account suspension, transaction/review editing, permanent deletion |
| **DB-6D — Admin controls** | Controlled role provisioning, approved policy/reason-code maintenance, operational search and metrics | Appeals and reinstatement until their policies are defined |

The proposed MVP accepts **product/listing reports only**. Reporting a user account is deferred: it needs a separate taxonomy, privacy review and decision workflow. A reporter must never be able to choose or impersonate another reporter.

A report is a request for review, not a finding that the target violated policy. Submission must not automatically hide a listing, suspend an account, cancel a transaction or notify the reported seller with the reporter's identity.

## 2. Source-derived constraints

The current application model has no report workflow, moderator/admin role, role assignment, account suspension state or moderation audit model.

The product lifecycle state is seller-managed:

- `Available`, `Reserved`, `Sold`, `Hidden`.
- The owner can switch a listing between `Available` and `Hidden`.
- Public product APIs do not expose `Hidden` or `Reserved` listings.

**Do not reuse `PRODUCTS.status = 'Hidden'` for a moderator takedown.** A seller can currently restore a seller-hidden listing to `Available`. A moderator hold therefore needs a separate moderation state, enforced by all public listing queries and by owner-edit paths. An owner edit must never clear an active moderation hold.

DB-4 transaction events record buyer/seller transaction transitions. They are not the moderator audit trail. Moderation decisions require a separate audit record.

Authentication currently identifies the signed-in user but does not authorize a moderator role. Hiding moderator controls in React is not an authorization boundary; every future moderator endpoint must enforce role permissions in the backend.

## 3. Recommended DB-6B policy defaults — approval required

These are proposed defaults to make the MVP small and testable. They are **not approved policy** and must not be silently treated as requirements.

| Decision | Recommended MVP default | Reason / boundary |
|---|---|---|
| Report target | Product listing only | Keeps the first taxonomy and privacy surface narrow |
| Reason codes | `PROHIBITED_ITEM`, `MISLEADING_LISTING`, `SUSPECTED_SCAM`, `SPAM_OR_DUPLICATE`, `OTHER` | Fixed allowlist; clients cannot submit arbitrary reason strings |
| Description | Optional plain text, maximum 500 characters | Enough context without an attachment pipeline |
| Attachments | Not supported in DB-6B | Storage provider and upload lifecycle are not selected |
| Target eligibility | Listing must be visible to the reporter when submitted; reject missing, seller-hidden or reserved listings | Avoids creating reports against inaccessible/private listings; re-check on the server |
| Self-report | Reject reporting one's own listing | Avoids meaningless or abusive queue entries |
| Duplicate submissions | One open report per reporter/listing; allow a new report after the previous one is resolved | Limits repeated queue spam while preserving later reports |
| Rate control | Propose a small per-account daily limit (for example, 5 submissions per 24 hours) | Exact limit and enforcement window require approval |
| Report transparency | Reporter can see only their own submission and public-safe status, if this feature is approved | No internal notes, moderator identity, evidence or reporter data is shown to the target |
| Target notification | No notification in DB-6B | Notification content and timing require a separate privacy/product decision |
| Retention | Preserve report and decision history; do not cascade-delete on account/listing deletion | Exact retention period must be approved before production deployment |

If the product owner chooses to include user-account reports in the first release, pause the DB-6B implementation and revise the relational model, reason taxonomy and authorization/privacy review before creating a migration.

## 4. Proposed relational model

### `dbo.PRODUCT_REPORTS` (product-only MVP)

| Column | Proposed SQL Server type | Nullable | Purpose |
|---|---|---:|---|
| `report_id` | `BIGINT IDENTITY(1,1)` | No | Report identifier |
| `reporter_user_id` | `INT` | No | FK to `dbo.USERS(user_id)` |
| `target_product_id` | `INT` | No | FK to `dbo.PRODUCTS(product_id)` |
| `reason_code` | `VARCHAR(32)` | No | Fixed approved code |
| `description` | `NVARCHAR(500)` | Yes | Optional user-supplied context |
| `status` | `VARCHAR(16)` | No | Initially `Submitted`; workflow states are proposed below |
| `submitted_at` | `DATETIME2(0)` | No | UTC submission time |
| `updated_at` | `DATETIME2(0)` | No | UTC last state change, if/when workflow states are implemented |

Proposed constraints and indexes:

- Primary key on `report_id`.
- Foreign keys to USERS and PRODUCTS with default `NO ACTION`; no cascade deletion.
- CHECK constraint for the approved reason-code allowlist.
- CHECK constraint limiting description length to 500 characters (also validate at API boundary).
- CHECK constraint for known report statuses.
- Index `(reporter_user_id, submitted_at DESC, report_id DESC)` for the reporter's own paginated submissions.
- Index `(status, submitted_at ASC, report_id ASC)` for the future moderation queue.
- If SQL Server filtered-index semantics are used for duplicate prevention, create a filtered unique index on `(reporter_user_id, target_product_id)` for open statuses only. The exact open-status set must be kept in sync with the workflow state machine.
- No role table, account suspension column, listing moderation column or moderation audit table is introduced by DB-6B unless its own reviewed design is approved.

For a product-only MVP, `target_product_id` is deliberately NOT NULL. If user reports are approved later, use an additive, reviewed extension with explicit target FKs and a CHECK requiring exactly one target; do not replace the FK with a polymorphic string or arbitrary target ID.

### Initial report states

- DB-6B creates a report as `Submitted`.
- The proposed DB-6C workflow may add `InReview`, `Dismissed`, `Actioned` and `Escalated`.
- A report is open while `Submitted` or `InReview`. A resolved state is one of `Dismissed` or `Actioned`; `Escalated` remains open until an authorized decision is made.
- State transitions, assignment and queue priorities must be approved before DB-6C implementation.

A report row records the allegation and its target reference, not a copy of the listing's private or mutable contents. If the listing later becomes Hidden, Reserved, Sold or otherwise unavailable, retain the report. Authorized moderators can use a separate, permission-checked review view in DB-6C; ordinary users must not receive hidden listing details through report APIs.

## 5. Proposed API contract

All endpoints require the existing authenticated cookie. The server derives `reporter_user_id` only from `get_current_user`. Never accept `reporter_user_id`, moderator ID, status, assignment, sanction or decision fields from the submitting client.

### Submit a report — `POST /api/reports`

Proposed request:

```json
{
  "target_product_id": 123,
  "reason_code": "MISLEADING_LISTING",
  "description": "Hình ảnh và mô tả không khớp với sản phẩm được giao."
}
```

Proposed behavior:

- Validate the reason code against the approved allowlist.
- Validate the optional description length and reject HTML/script payloads as content rather than rendering it as markup.
- Load the target server-side; reject a missing, seller-hidden or Reserved target according to the approved eligibility rule.
- Reject a user reporting their own listing.
- Apply approved duplicate and rate-limit rules.
- Insert a `Submitted` report only. No automatic moderation decision or listing state change.
- Return the new report ID, submitted timestamp and safe status. Do not return internal notes or reporter information.

### View own reports — `GET /api/users/me/reports` (optional; approval required)

If reporter status transparency is approved, return only the authenticated reporter's reports, paginated with stable ordering `submitted_at DESC, report_id DESC`.

The response may contain report ID, target product ID, approved public-safe reason label, submitted timestamp and a public-safe status. It must not contain reporter identity fields, internal notes, assigned moderator details, internal queue priority or the target's non-public listing data.

Do not add a public endpoint to list reports for a product or user. Do not allow the reported seller to query who reported them.

No moderator queue or decision endpoint is part of DB-6B.

## 6. DB-6C authorization and moderation audit requirements

Before DB-6C code:

1. Approve role provisioning and a backend permission model. Buyer/seller are transaction relationships, not global roles. Registration must never assign Moderator or Admin.
2. Every queue/read/decision endpoint must have server-side role checks, independently tested for unauthenticated students, ordinary users, moderators and admins.
3. Limit moderator permissions to the approved actions. The proposed minimum is review, dismiss, action or escalate a report, plus only explicitly approved listing-level measures.
4. Require an approved reason code and a bounded internal note for every decision. Keep internal notes separate from reporter-visible status.
5. Commit the moderation decision and its audit record atomically.

A separate `MODERATION_ACTIONS` audit model should capture actor user ID and role at action time, target type/ID, action code, previous/resulting moderation state, required reason, bounded internal note and UTC timestamp. It is distinct from `TRANSACTION_EVENTS`.

Do not call the audit immutable merely because application code avoids updates. Before claiming append-only enforcement, determine the actual SQL Server application principal and restrict UPDATE/DELETE permissions or implement an equivalent database-enforced policy. The current application principal/permission setup must be verified first.

## 7. Listing moderation state — later additive design

Keep seller-controlled `PRODUCTS.status` separate from moderation state. A future public listing must satisfy both:

1. Seller lifecycle permits public visibility (for example, Available or Sold under the corresponding endpoint rules).
2. Moderation state permits public visibility.

A moderation hold must be enforced on public product list, detail, public profile, search and any other public projection. Owner update must not clear or bypass it. Restoration must be an explicit authorized action and must not bypass Reserved/Sold transaction rules.

DB-6B report submission alone does not create or activate a moderation hold. Exact sanctions (warning, correction request, temporary listing hold, removal) must be approved before implementation.

## 8. Account suspension and appeals — deferred

Do not add account suspension in DB-6B or DB-6C by implication. Before implementation, define temporary versus permanent suspension, expiry, allowed self-service actions, appeal path and who can approve each sanction.

Because authentication uses an expiring JWT cookie, adding an account status column alone will not invalidate already-issued tokens immediately. The backend must check account state on each authenticated request or use a verified session/token revocation strategy. Preserve transaction, review and report history; do not hard-delete users as a moderation shortcut.

Appeals and reinstatement are deferred until an appeal policy and independent reviewer process are approved.

## 9. Test and migration gates

When implementation is approved:

- Use an additive SQL Server migration only; no base-schema reinitialization.
- First apply the migration to a dedicated database whose name ends in `_test`.
- Keep the SQL Server integration test opt-in and verify the actual SQL Server constraints/indexes; SQLite unit tests are not a substitute.
- Test authentication, reporter ownership/privacy, invalid reason codes, description bounds, self-report rejection, inaccessible targets, duplicate behavior, rate limits, target lifecycle changes and pagination.
- Verify ordinary users cannot read another reporter's submissions or invoke moderator endpoints.
- Do not run `database_scripts/01_init_schema.sql` against an existing database with data to preserve. Do not run `--drop-dwh`. Do not modify production or user data as part of this design step.

## 10. Product Owner decisions required before DB-6B implementation

| # | Decision | Proposed default | State |
|---:|---|---|---|
| 1 | Report targets | Product listings only; defer user-account reports | Needs approval |
| 2 | Reason taxonomy | Five codes listed in section 3 | Needs approval |
| 3 | Description | Optional plain text, 500 characters | Needs approval |
| 4 | Evidence | No image/file attachments in MVP | Needs approval |
| 5 | Target eligibility | Publicly visible listing only; reject own listing | Needs approval |
| 6 | Duplicate behavior | One open report per reporter/listing; re-report after resolution | Needs approval |
| 7 | Rate limit | Suggested 5 submissions per 24 hours | Needs approval |
| 8 | Reporter status view | Own reports only, public-safe state; optional | Needs approval |
| 9 | Target notification | No notification in DB-6B | Needs approval |
| 10 | Retention | Preserve reports and decisions; retention period TBD | Needs approval |
| 11 | Moderator listing actions | Not in DB-6B; define exact sanctions before DB-6C | Needs approval |
| 12 | Role provisioning | No self-assignment; controlled initial admin setup before DB-6C | Needs approval |
| 13 | Appeals | Deferred; define before account/listing sanctions | Needs approval |

**Exit criterion:** DB-6B implementation may begin only after the product owner approves the defaults or records replacements. Until then this branch is a reviewable design proposal; it does not authorize a live migration, new permissions, takedowns, suspensions or moderator access.
