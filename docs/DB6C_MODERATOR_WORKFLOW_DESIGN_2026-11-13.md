# DB-6C — Minimal Moderator Workflow and Audit Design

**Date:** 2026-11-13  
**Status:** Design proposal for Product Owner review. Documentation only; no role, moderation endpoint, listing hold, audit table or policy behavior is implemented by this document.  
**Baseline:** \`main\` after DB-6B PR #42 was merged.

## 1. Goal and delivery boundary

DB-6C is the next planned slice after DB-6A Favorites and DB-6B private product-report intake. Its goal is to let an explicitly authorized moderator review a submitted product report, record a controlled decision and preserve a separate moderation audit trail.

This design intentionally does **not** make a report itself a finding of wrongdoing. It also does not grant moderator privileges, suspend accounts, delete products or decide sanctions by implication.

| Stage | Scope | Boundary |
|---|---|---|
| DB-6A | Private favorites | Complete and merged |
| DB-6B | Authenticated product-report intake | Complete and merged; reports remain \`Submitted\` |
| **DB-6C** | Minimum moderator queue, assignment/review, decisions and audit | Requires this proposal's policy/authorization decisions before implementation |
| DB-6D | Admin controls and controlled role provisioning | Separate later stage; not included here |

## 2. Source-verified current baseline

The repository at the baseline commit has the following relevant behavior:

- \`USERS\` has identity/profile/authentication fields but no role, role assignment or account-status field.
- Registration creates a student account only. It does not assign an authorization role.
- \`get_current_user\` validates the cookie JWT and loads the user row. It does not check moderator/admin permissions.
- JWT claims currently contain user ID and token timestamps, not roles. A future authorization check should read active role assignments from the database on every protected request rather than trusting a long-lived role claim.
- \`PRODUCTS.status\` is seller-controlled and is constrained to \`Available\`, \`Reserved\`, \`Sold\` or \`Hidden\`. The seller update endpoint can change between \`Available\` and \`Hidden\`; Reserved and Sold listings are not editable.
- Public product list, detail, seller-product and transaction-creation routes enforce different product lifecycle rules. Any moderation hold must be enforced consistently across all of them.
- DB-4 \`TRANSACTION_EVENTS\` records buyer/seller transaction lifecycle events. It is not the moderation audit log.
- DB-6B added \`dbo.PRODUCT_REPORTS\`. Its current CHECK constraint allows only \`Submitted\`. There is no report queue, assignment, decision endpoint, moderator role or reporter-status endpoint.
- DB-6B currently keeps reporter identity and description out of the submission receipt. That privacy boundary must remain.

**Critical constraint:** do not reuse \`PRODUCTS.status = 'Hidden'\` for moderator action. A seller can restore their own Hidden listing to Available. Moderation visibility needs its own independent state and server-side enforcement if a listing-level hold is approved.

## 3. Security and privacy invariants

1. Every moderator queue, report-detail, assignment and decision route must enforce authorization in the backend. A hidden React button is not authorization.
2. Ordinary students, sellers and reporters must receive 403 for moderator-only routes, even when they know a report ID.
3. Role changes must take effect on the next protected request. Do not rely on roles embedded in the existing JWT.
4. Registration, profile update and ordinary user APIs must never create or modify role assignments.
5. The reported seller must never receive reporter identity, reporter email/student ID, report description or internal moderator notes.
6. The reporter must not receive internal notes, moderator identity, assignment data or another reporter's details.
7. Moderation decisions and their audit rows must commit atomically.
8. Report history and moderation audit rows must not be cascade-deleted with a user or product.
9. No account suspension, transaction mutation, review editing or permanent deletion is part of DB-6C.
10. No report submission or automated threshold may independently place a moderation hold.

## 4. Proposed role and permission boundary

### Proposed role model

Use normalized role assignments rather than a single role column, so a student can retain normal marketplace capabilities while separately holding a moderation permission.

Suggested logical entities:

- \`ROLES\`: fixed role codes such as \`MODERATOR\` and \`ADMIN\`.
- \`USER_ROLE_ASSIGNMENTS\`: user, role, granted-at, granted-by, revoked-at, revoked-by and a bounded grant/revocation reason.
- Role-assignment history is preserved; revoking a role closes an assignment rather than deleting history.

Suggested route permissions:

| Capability | Student | Moderator | Admin |
|---|---:|---:|---:|
| Submit a product report | Yes | Yes | Yes |
| View own submission receipt | Yes | Yes | Yes |
| Read moderation queue/details | No | Yes | Yes |
| Claim/release a report | No | Yes | Yes |
| Dismiss/action/escalate a report | No | Within approved scope | Yes |
| Apply/release an approved listing hold | No | If explicitly granted | Yes |
| Grant/revoke roles | No | No | DB-6D only |
| Change reason codes or global policy | No | No | DB-6D only |

### Provisioning dependency

DB-6C must not expose a self-service role-grant endpoint. DB-6D owns the admin-facing grant/revoke workflow. Before production use of DB-6C, the Product Owner must approve a controlled initial moderator bootstrap procedure and identify who is allowed to execute it. A test fixture may seed a moderator role only inside the disposable test database.

If no approved bootstrap process exists, moderator endpoints must remain unavailable in production even after the code is merged.

## 5. Proposed report workflow

### Proposed states

| State | Meaning | Queue behavior |
|---|---|---|
| \`Submitted\` | New report awaiting review | Unassigned; visible to authorized moderators |
| \`InReview\` | A moderator has claimed the report | Assigned to one moderator |
| \`Escalated\` | Current reviewer requests a second-level review | Open; requires the approved escalation path |
| \`Dismissed\` | Review found insufficient grounds for a listing action | Resolved |
| \`Actioned\` | Review approved an explicit, policy-listed action | Resolved after the action and audit commit |

A report is open while Submitted, InReview or Escalated. Dismissed and Actioned are terminal for this first workflow. Reopening a resolved report, bulk actions, duplicate-report merging, queue priority/SLA and account reports are excluded unless separately approved.

### Proposed transition table

| Current state | Command | Next state | Guard |
|---|---|---|---|
| Submitted | Claim | InReview | Moderator; report is still unassigned |
| Escalated | Claim | InReview | Authorized reviewer under the approved escalation rule |
| InReview | Release | Submitted | Current assignee or an explicitly authorized admin |
| InReview | Dismiss | Dismissed | Current assignee; mandatory resolution code and internal note |
| InReview | Action | Actioned | Current assignee; mandatory approved action code, reason and internal note |
| InReview | Escalate | Escalated | Current assignee; mandatory escalation reason/note; assignment cleared |

The recommended concurrency rule is a conditional SQL update/row lock so two moderators cannot claim the same report concurrently. Only the current assignee may decide a claimed report; all overrides must be explicit, permission-checked and audited.

An Escalated report must not silently resolve itself. The Product Owner must decide whether it goes to an Admin role, a senior moderator role or a different moderator for independent review. Until that target role/process is approved, escalation cannot be implemented as an actionable workflow.

### Duplicate-open-report rule

The DB-6B filtered unique index currently protects only \`Submitted\`. Once additional open states exist, the migration must replace it so the same reporter/product pair remains unique while the report is Submitted, InReview or Escalated, and may be reported again only after Dismissed or Actioned.

The exact SQL Server filtered-index predicate must be verified on the real SQL Server integration workflow before merge; SQLite behavior is not sufficient evidence.

## 6. Proposed data and API design

### Report workflow fields

A reviewed additive migration would extend \`dbo.PRODUCT_REPORTS\` with the minimum fields required for current workflow state, such as:

- \`assigned_moderator_user_id\` nullable FK to USERS;
- \`review_started_at\` nullable UTC timestamp;
- \`resolved_at\` nullable UTC timestamp;
- optionally a constrained \`resolution_code\` for the final public-safe outcome.

The current status CHECK constraint must be replaced with the approved state set. The migration must be versioned and additive; never edit \`01_init_schema.sql\` as a way to update an existing database.

### Separate audit table

Proposed \`dbo.MODERATION_ACTIONS\` (name subject to review):

| Field | Purpose |
|---|---|
| \`moderation_action_id\` | Audit row primary key |
| \`report_id\` | FK to the report |
| \`actor_user_id\` | User who performed the operation |
| \`actor_role_code\` | Role snapshot at action time |
| \`action_code\` | CLAIMED, RELEASED, DISMISSED, ACTIONED, ESCALATED, HOLD_PLACED or HOLD_RELEASED as approved |
| \`from_status\`, \`to_status\` | Report state transition |
| \`reason_code\` | Controlled decision/escalation reason |
| \`internal_note\` | Bounded moderator-only explanation |
| \`occurred_at\` | UTC timestamp |

The report state update, any approved listing-hold update and audit insert must occur in one database transaction. A failed audit insert must roll back the decision.

Do not call this table immutable merely because application code only inserts. Before claiming append-only enforcement, identify the actual SQL Server application principal and verify its permissions. The intended production permission model is SELECT/INSERT for the application role and no UPDATE/DELETE; operational owner permissions must be separate and tightly controlled.

### Proposed endpoint boundary

- \`GET /api/moderation/reports\`: moderator-only paginated queue, filterable by approved state and stable ordering.
- \`GET /api/moderation/reports/{report_id}\`: moderator-only review detail; return only fields needed for the decision.
- \`POST /api/moderation/reports/{report_id}/claim\`: claim an unassigned open report.
- \`POST /api/moderation/reports/{report_id}/release\`: return an assigned report to the queue, with required reason.
- \`POST /api/moderation/reports/{report_id}/decision\`: dismiss, action or escalate using an allowlisted decision payload.

Do not create a public report-list endpoint or a seller-facing report-detail endpoint. DB-6C does not add the optional reporter history endpoint that was excluded from DB-6B.

### Moderator response privacy

Recommended moderator DTO:
- report ID, target product ID, reason code, submitted time, bounded description, current state and assignment summary;
- target listing fields necessary for review;
- reporter internal user ID only if the Product Owner approves that moderators need it.

Do not return reporter email, student ID, password hash, full private profile or unrelated transaction/review data by default. Internal notes are readable only through a dedicated moderator permission and never appear in student/seller DTOs.

## 7. Listing-level moderation hold — separate policy decision

A moderator finding may require a listing action, but the exact sanction is not yet approved.

Recommended technical separation, if a hold is approved:

- Add a separate current moderation state (for example, a one-row-per-product \`PRODUCT_MODERATION\` relation with \`Clear\` / \`Held\` state), not a mutation of seller-managed \`PRODUCTS.status\`.
- Keep hold/release history in \`MODERATION_ACTIONS\`.
- Seller update requests must not clear or overwrite the moderation state.
- Public product list, product detail, public seller-product list and purchase-request creation must all enforce the hold server-side.
- Favorites must return a safe unavailable/tombstone representation for held products without exposing held listing content.
- The seller's private product view may show a safe “under moderation” state, but must not reveal reporter identity or internal notes.

Before implementing this, decide:
- Whether the approved action is temporary hold only, correction request, permanent removal from public marketplace or another explicitly named action.
- Whether a hold has an expiry or remains until an authorized release.
- Whether moderators may hold Available, Reserved and Sold listings, and how any existing Reserved transaction proceeds.
- What safe notice the seller receives, and through which channel.
- Whether the seller can edit listing content while a hold is active.

No product state or visibility change is implemented by this design PR. A report alone must never create a hold.

## 8. Account actions and appeals remain out of scope

DB-6C does not add account warnings, suspension, permanent bans, transaction cancellation, review removal, hard deletion or appeals.

Before any account restriction is considered, a separate policy must define temporary versus permanent restrictions, expiry, allowed account actions, appeal path and approval authority. Because the current JWT is stateless and \`get_current_user\` does not check account status, an account status column alone would not revoke an already-issued token. That feature needs per-request enforcement or a verified revocation strategy.

## 9. Test plan and delivery gates

Implementation, after policy approval, must include:

1. Unauthenticated access receives 401; ordinary student access receives 403; authorized moderator access succeeds.
2. Newly revoked role is denied on the next request (no stale role claim in JWT).
3. Claim race: two moderators cannot both claim one report.
4. Invalid state transitions and client-supplied actor/role/state fields are rejected.
5. Only an assigned moderator may decide, unless a specifically approved override applies.
6. Decision, listing hold (if approved) and audit event commit atomically; injected audit failure rolls the whole operation back.
7. Reporter identity and internal notes never leak to seller, public listing, reporter receipt or ordinary user APIs.
8. A report does not change listing visibility before an explicit approved decision.
9. If a hold is implemented, every public read and purchase-request route enforces it, and seller edits cannot clear it.
10. SQL Server integration tests verify actual constraints, filtered unique index, FKs, concurrency behavior and application-principal permissions.
11. Use only a disposable SQL Server database whose name ends in \`_test\`; do not point the test suite at the user's app database.
12. Do not run \`database_scripts/01_init_schema.sql\` against an existing database with data to preserve. Do not run \`--drop-dwh\`.

## 10. Product Owner decisions required before DB-6C implementation

The recommended defaults below are proposals, not approved policy:

| # | Decision | Recommended starting point | Approval needed |
|---:|---|---|---|
| 1 | Moderator role | \`MODERATOR\` and \`ADMIN\` assignment model; check role from DB on each protected request | Confirm role names and permission split |
| 2 | First moderator provisioning | Controlled one-time operator/DBA bootstrap; no self-registration or public role API; DB-6D later adds admin UI | Identify the authorized bootstrap owner/process |
| 3 | Queue access | Moderators see all Submitted/InReview/Escalated product reports | Confirm whether moderator scope is global or scoped |
| 4 | Assignment | Explicit claim; one assignee; only assignee decides; release returns to queue | Confirm claim/release and override rules |
| 5 | Escalation | Escalated goes to Admin or an independent second moderator; no auto-resolution | Choose escalation destination and who can close it |
| 6 | Final outcomes | Dismissed or Actioned, both with controlled reason and internal note | Approve state machine and reason taxonomy |
| 7 | Listing sanction | Temporary public listing hold only; no account sanction or hard delete | Approve whether hold is allowed and exact semantics |
| 8 | Hold duration | Hold stays until explicit moderator release; no automatic expiry in first slice | Approve or specify a fixed expiry |
| 9 | Product lifecycle | A hold never cancels or rewrites an existing transaction; decide separately how Reserved/Sold listing views behave | Approve edge-case behavior |
| 10 | Seller notice | Show a safe state in own listing view; no reporter identity, internal note or automatic email | Confirm message/channel |
| 11 | Moderator visibility | Minimum review context; omit reporter email/student ID; include reporter user ID only if justified | Confirm reporter identity visibility to moderators |
| 12 | Internal note | Required for every decision/escalation; max 1,000 characters; moderator-only | Approve length and visibility |
| 13 | Audit enforcement | Separate audit table; app principal cannot UPDATE/DELETE; identify actual DB principal first | Approve audit access and operational owner model |
| 14 | Retention | Preserve reports/actions; no automated purge in DB-6C | Exact retention period remains a separate approval gate |
| 15 | Reporter transparency | No new own-report history endpoint in DB-6C | Confirm deferral or request a separate feature |

## 11. Exit criteria

DB-6C implementation may begin only after the Product Owner resolves the decisions above, especially role bootstrap, escalation ownership, actioned outcome/listing-hold semantics and audit enforcement.

This PR is a documentation-only proposal. It creates no migration, endpoint, permission, moderator assignment, listing hold, notification or user restriction. It does not modify any database or application data.
