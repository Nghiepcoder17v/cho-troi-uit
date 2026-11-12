# DB-6 — Marketplace and Admin/Moderator Source Audit

**Date:** 2026-11-12  
**Base:** `main` after DB-5 filter/sort merge  
**Status:** Read-only source audit and implementation proposal. No role, moderation, report or favorite code is changed here.

## 1. Executive result

The repository has a working student marketplace foundation, but the following DB-6 capabilities are not implemented in the audited application source:

- Favorites/Wishlist persistence and endpoints.
- Product/user reporting workflow.
- Moderator/admin role model and backend authorization.
- Moderation queue, moderation decisions and moderation audit log.
- Account suspension/revocation workflow.

The README also explicitly records that admin/moderator roles and listing moderation/reporting are not implemented.

**Recommendation:** build this as a staged workflow, not as a full admin dashboard in one step. Start with Favorites and user-submitted reports; add a minimum moderator queue and append-only moderation action log; expand admin management only after role and sanction policies are fixed.

## 2. Current source baseline

### Users and authentication

The current `User` ORM/SQL schema has identity/profile/authentication fields (user ID, student ID, email, password hash, full name, major and timestamps). There is no role, role assignment, account status or moderator capability in the model.

The current `get_current_user` dependency:
- Reads the `access_token` cookie.
- Validates and decodes JWT.
- Loads the user row by `sub`.
- Rejects a missing user.

It does not inspect an authorization role or an account suspension flag. Registration does not assign an authorization role. Therefore hiding an admin button in React would not create a security boundary, and a moderation action cannot safely be implemented only in the frontend.

The current cookie JWT is stateless and has an expiry. A future suspend/ban feature must define how an already-issued token becomes unusable; an account-status column alone is insufficient unless the backend checks it on every authenticated request.

### Products

Product status is currently `Available`, `Reserved`, `Sold`, or `Hidden`.

The existing seller update endpoint allows the owner to switch between `Available` and `Hidden`; Reserved and Sold are read-only. Public APIs exclude Hidden and Reserved listings.

**Critical design constraint:** do not reuse `Hidden` to represent a moderator takedown. It is already a seller-controlled listing state. If a moderator action simply changes `status = 'Hidden'`, the existing owner update flow could let the seller switch it back to Available. Moderation visibility must be represented separately (or by a separately enforced state machine), and the public visibility query must enforce both seller state and moderation state.

### Reviews and transaction audit

- Reviews exist and are tied to Completed transactions, with one review per reviewer per transaction.
- There is no review/report flagging workflow in the audited API contract.
- DB-4 transaction event history is a separate feature. It must not be treated as the general audit log for moderator/admin actions.

### Feature search in audited source

The following were checked: `backend/models.py`, `backend/schemas.py`, `backend/main.py`, `backend/security.py`, `backend/tests/test_account.py`, `docs/api_contract.md` and `README.md`.

No Favorites/Wishlist, user/product Reports, admin/moderator role, moderation queue or moderation audit endpoint/model was found in those application files.

## 3. Proposed staged delivery

### DB-6A — Favorites/Wishlist (lowest policy risk)

Proposed logical table `USER_FAVORITES`:
- `user_id` FK to USERS.
- `product_id` FK to PRODUCTS.
- `created_at` UTC.
- Unique constraint `(user_id, product_id)`; duplicate add should be idempotent or return a documented conflict.

Proposed API:
- `PUT /api/users/me/favorites/{product_id}` — add favorite (authenticated).
- `DELETE /api/users/me/favorites/{product_id}` — remove favorite (authenticated).
- `GET /api/users/me/favorites` — paginated current user's favorites, including current product state and seller summary.

Initial behavior to decide before implementation:
- Whether only Available listings can be newly favorited.
- Whether an already-favorited item remains visible after it becomes Sold or Hidden (recommended: retain it in the user's list with current status; do not expose Hidden product details to public users).
- Whether removing a product permanently deletes the favorite relation or returns an unavailable-item marker.
- Whether favorites are private by default (recommended).

Favorites must never reserve a product or imply a purchase request.

### DB-6B — User-submitted Reports

Start with product/listing reports. User-account reports may be included after the same abuse-control and privacy rules are defined.

Proposed report attributes:
- Reporter user ID.
- Exactly one target: product ID or user ID.
- Fixed reason code, optional bounded description, submitted timestamp.
- Workflow status and assigned moderator, if/when the moderation queue is implemented.
- No arbitrary file upload in the first release.

A relational design should use explicit nullable target FKs plus a CHECK that exactly one target is present; avoid an unvalidated polymorphic string target that cannot be protected by a foreign key.

Proposed API boundary:
- `POST /api/reports` — authenticated submission.
- A user may view only their own submitted reports, if report-status transparency is approved.
- Report details and reporter identity are private to the reporter and authorized moderators; never expose reporter identity to the reported seller/user.

Before implementation define:
- Reason codes per target type.
- Description length and whether evidence attachments are allowed.
- Duplicate report/rate-limit rules.
- What happens when the target disappears or changes state.
- Whether the reported party can see report details or only the moderation result.

### DB-6C — Minimal Moderator Workflow

Proposed minimum moderator capabilities:
- View a queue of new/in-review reports.
- Open the reported target and relevant public context.
- Mark a report dismissed, actioned or escalated.
- Apply only explicitly approved listing-level sanctions.
- Record a mandatory reason and actor for every decision.
- Avoid exposing unrelated private user fields or transaction data.

Do not allow moderators to grant roles, change security settings, alter transactions, edit reviews, or permanently delete users/products unless a separate policy and authorization matrix explicitly permits it.

### DB-6D — Admin Console

Only after DB-6B/6C is running:
- Grant/revoke moderator roles through a controlled admin-only workflow.
- Manage categories and approved moderation reason codes.
- Search/filter users, listings and report queues.
- View moderation metrics with defined metric semantics.
- Add appeals/reinstatement workflows only after the appeal policy exists.

No public registration or client-side action may assign admin/moderator roles.

## 4. Authorization and audit architecture

### Role separation

Buyer and seller are transaction relationships, not global user roles. Student eligibility is currently established through the UIT email/student identity requirements; it should not be confused with authorization role.

Before implementation, choose either a simple role column (only if exactly one role per account is guaranteed) or a normalized role/assignment model. The recommended direction for extensibility is a role catalog plus user-role assignments, with explicit permission checks in backend dependencies. This remains a proposal, not a schema decision.

Suggested initial permissions matrix:

| Capability | Student | Moderator | Admin |
|---|---:|---:|---:|
| Manage own favorites | Yes | Yes | Yes |
| Submit report | Yes | Yes | Yes |
| View own reports | Yes, if approved | Yes | Yes |
| View moderation queue | No | Yes | Yes |
| Dismiss/action/escalate report | No | Within approved scope | Yes |
| Grant/revoke roles | No | No | Yes |
| Change moderation policy/categories | No | No | Yes |

### Separate moderation audit log

DB-4 transaction events record buyer/seller transaction actions. They are not suitable for moderator audit.

Proposed moderation audit record should capture:
- Actor user ID and role at action time.
- Target type/ID.
- Action code.
- Previous and resulting moderation state.
- Required reason code and bounded internal note.
- UTC timestamp.

No moderation decision should be implemented without an audit record committed atomically with the decision. App-level insert-only behavior and SQL Server principal permissions must be defined; do not claim immutable audit if the application principal can freely UPDATE/DELETE it.

### Listing moderation state

Keep seller-managed listing status separate from moderation status. A public listing must pass both conditions:
1. Seller/product workflow allows public visibility.
2. Moderation policy allows public visibility.

An owner edit must never clear an active moderation hold. Restoration must be an explicit authorized moderator/admin action and must not bypass Reserved/Sold transaction rules.

### Account suspension

Before account suspension/ban:
- Define temporary vs permanent suspension and expiry.
- Decide which actions remain possible (view own data, appeal, logout).
- Add backend enforcement to authenticated requests.
- Decide how existing JWTs are invalidated or made ineffective immediately.
- Preserve transaction, review and report audit records; do not hard-delete accounts as a substitute for moderation.

## 5. Policy decisions required before DB-6 implementation

The current handover explicitly leaves moderation policy to the Product Owner. The broad roadmap approval does not define which sanctions or report categories are allowed. Record these decisions when the implementation phase starts:

1. **Target types:** listing only for MVP, or both listing and user from first release?
2. **Report reasons:** fixed categories for prohibited item, misleading listing, scam/impersonation, harassment/spam, or a different approved taxonomy?
3. **Evidence:** text-only MVP or image/file evidence? If attachments are added, they must use the approved media pipeline, not an ad-hoc upload path.
4. **Listing sanctions:** hide from public search, request correction, temporary hold, restore, or remove? Which actions can a moderator perform?
5. **User sanctions:** warning, temporary suspension, permanent suspension? Who can approve each action?
6. **Appeal:** can a seller/user appeal a takedown or suspension; who reviews it?
7. **Queue service levels:** priority levels, assignment, duplicate merging and target response time.
8. **Privacy:** may the reported person see the reporter's identity? Recommendation: no.
9. **Role provisioning:** who assigns the first admin and how role changes are audited?
10. **Retention:** how long are reports, evidence and internal moderation notes retained?

No product data, role assignments, user restrictions or policy behavior is changed by this source audit.

## 6. Dependencies and safety gates

- DB-0 SQL Server runtime baseline remains a prerequisite for any OLTP migration. Use the dedicated test database and backup/recovery rules already documented.
- DB-4 event implementation has its own design PR and also waits on DB-0 verification. A transaction timeline does not replace moderation audit.
- DB-1/DB-2/DB-3 media work is gated separately by the actual deployment target, storage provider and URL access policy. Do not invent a provider or bypass the media lifecycle with report evidence uploads.
- DB-6A favorites can be implemented independently after DB-0 verification.
- DB-6B/6C require report taxonomy, moderation state machine, backend role checks and audit policy before code.
- DB-6D must remain a later phase, not a prerequisite for basic Favorites or report submission.
- Do not run `database_scripts/01_init_schema.sql` against any existing database with data to preserve. Do not run `--drop-dwh`. Do not expand DWH/ETL scope for these operational features without a separate approved analytics requirement.

## 7. Recommended sequence

1. Finish DB-0 runtime verification on the dedicated SQL Server test database.
2. Complete DB-4 transaction event implementation using the design in `DB4_TRANSACTION_EVENT_DESIGN_2026-11-12.md`.
3. Implement DB-6A Favorites as the first DB-6 code slice.
4. Finalize report taxonomy and listing/user sanctions; then implement DB-6B.
5. Add minimal DB-6C moderator queue plus append-only moderation audit.
6. Add DB-6D admin console and role provisioning only after permission and appeals policies are approved.
7. Integrate frontend controls only when each API and permission contract is real.

**DB-6 audit result:** the feature gap and core security constraints are mapped from current source. This document is a planning/audit artifact only; it does not claim that Favorites, Reports, RBAC or moderation have been implemented.
