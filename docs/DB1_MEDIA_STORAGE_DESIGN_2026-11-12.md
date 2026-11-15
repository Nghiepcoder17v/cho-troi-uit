# DB-1 — Media Storage and Profile Media Architecture

**Updated:** 2026-11-15  
**Status:** Storage architecture and URL policy decided; no provider credentials, application adapter or database migration has been deployed.  
**Scope:** Product images, user avatar and bio foundations for FE-3/FE-5.

## 1. Decisions already approved

The following are established project requirements:
- Store image bytes in object storage, not SQL Server.
- SQL Server stores the storage key and required metadata only.
- Product images: maximum 5 images per product, 5 MB per image.
- Avatar: maximum 2 MB.
- Accepted image formats: JPEG, PNG and WebP.
- Bio: plain text, maximum 300 characters.
- Bio and avatar may appear on public profiles; email, student ID and password hash remain private.
- Avatar, bio and product media must not be added to the DWH extraction in this scope.

These are the approved initial limits. The first hosted provider default is recorded in section 2; provisioning remains an implementation gate.

## 2. Deployment survey and provider decision

The repository currently documents:
- Local development with SQL Server and Windows Authentication or SQL login.
- Docker Compose with FastAPI, Nginx frontend and SQL Server.
- A named Docker volume for SQL Server data.
- No confirmed production cloud host, object-storage account, media CDN, domain or production secret configuration.

### 2.1 Decisions for the first implementation

**Production default: Cloudflare R2 Standard, using a private bucket and its S3-compatible API.** This is the chosen default for the first hosted implementation, not a claim that an account or bucket has already been provisioned. The storage adapter must remain S3-compatible so the project can move to another provider without changing SQL Server schema or marketplace business logic.

**Local development: a filesystem storage adapter.** Store objects beneath a configurable data directory outside the frontend static assets. Serve local objects only through an API route that applies the same media visibility checks as the hosted path. Use a temporary directory in unit tests. A persistent Docker volume can be added when the adapter is integrated into Compose; do not expose the directory as a public static mount.

**Do not add MinIO Community Server as a new dependency.** Its upstream repository was archived on 2026-04-25 and is marked no longer maintained. This project should not introduce a new local storage dependency without an active maintenance path.

### 2.2 Why R2 is the default

- R2 exposes an S3-compatible API and supports server-generated presigned GET URLs, so a standard S3 SDK can implement the adapter.
- The Standard storage pricing published on 2026-11-15 lists $0.015 per GB-month and no egress bandwidth charge. This is a useful cost profile for a small image-heavy student marketplace, although actual cost still depends on stored volume and request counts.
- R2 buckets are private by default. Keep the bucket private; do not enable public bucket access or the development r2.dev URL.
- R2 presigned URLs work on the R2 S3 API domain, not a custom domain. The selected private-read policy therefore prioritizes access control over a branded public media hostname and custom-domain CDN caching.

Official references reviewed on 2026-11-15:
- [R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/) — supported methods, expiry and hostname limitations.
- [R2 public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/) — private-by-default behavior and public-access options.
- [R2 pricing](https://developers.cloudflare.com/r2/pricing/) — current storage, operation and egress pricing.
- [MinIO upstream repository](https://github.com/minio/minio) — archive and maintenance status.

### 2.3 Adapter and configuration boundary

Define a narrow storage interface for:
- Uploading already-validated, normalized bytes to a server-generated key.
- Deleting an object by key, idempotently where the provider supports it.
- Generating a short-lived read URL for a key.

Provider selection belongs in environment configuration, not domain logic. The hosted adapter will receive the S3 endpoint, bucket, region, access key and secret key from runtime secrets. Local mode will receive only a filesystem root. Never commit storage credentials, print them in diagnostics or expose them to the browser.

Uploads remain multipart to FastAPI for the first implementation: the server validates and normalizes the image before storage. Do not introduce direct browser-to-R2 PUT uploads in the first iteration; that would add CORS, upload-token and untrusted-object-finalization complexity without a current requirement.

## 3. Proposed logical data model

Keep the OLTP database as metadata and relationship storage. Do not store image bytes or a provider-generated URL in SQL Server.

### 3.1 `MEDIA_ASSETS`

One row per uploaded object:
- `media_asset_id` — BIGINT IDENTITY primary key.
- `storage_key` — NVARCHAR(512), unique, generated by the server; never derived from the original filename.
- `content_type` — VARCHAR(50), allow-listed JPEG/PNG/WebP MIME value.
- `size_bytes` — BIGINT, actual stored byte size.
- `sha256` — CHAR(64), checksum of the normalized stored bytes.
- `width`, `height` — INT, decoded image dimensions.
- `lifecycle_status` — VARCHAR(20): Pending, Active or DeletePending.
- `uploaded_by_user_id` — FK to USERS.
- `created_at` — DATETIME2(0), UTC.

Constraints/indexes:
- Unique storage key.
- Positive byte size and positive dimensions.
- Check lifecycle status against the allow-list.
- Index lifecycle status and created_at for cleanup workers.
- Do not cascade-delete assets implicitly when a user or product relationship changes.

The lifecycle state allows cleanup to recover from process crashes between a SQL commit and an object-storage operation.

### 3.2 `PRODUCT_MEDIA`

One row per product image:
- `product_media_id` — BIGINT IDENTITY primary key.
- `product_id` — FK to PRODUCTS.
- `media_asset_id` — FK to MEDIA_ASSETS, unique.
- `sort_order` — TINYINT, zero-based order.
- `is_cover` — BIT.
- `alt_text` — NVARCHAR(200), nullable.
- `created_at` — DATETIME2(0), UTC.

Constraints/indexes:
- Unique `(product_id, sort_order)`.
- Filtered unique index on `product_id` where `is_cover = 1`, allowing at most one cover.
- Check `sort_order` is between 0 and 4.
- Enforce the maximum of five images in the backend inside a transaction that locks the product row; a simple count-then-insert without locking is vulnerable to concurrent uploads.

A product may temporarily have no cover, for example before the first image upload. When images exist, the API should ensure a deterministic cover selection.

### 3.3 `USER_AVATARS`

One active avatar relationship per user:
- `user_id` — PK and FK to USERS.
- `media_asset_id` — FK to MEDIA_ASSETS, unique.
- `updated_at` — DATETIME2(0), UTC.

Replacing an avatar switches the relationship to the new active asset and schedules the previous asset for deletion. If no avatar exists, frontend fallback remains the user's initial.

### 3.4 USERS.bio

Add `bio NVARCHAR(300) NULL` through an additive OLTP migration. Validate trimmed plain text at the API boundary and enforce the 300-character maximum in both Pydantic and SQL Server.

## 4. Object lifecycle and orphan cleanup

Use a recoverable lifecycle rather than relying only on best-effort cleanup:

1. Read and validate the uploaded bytes before accepting them.
2. Create a `MEDIA_ASSETS` row in Pending state with a server-generated key.
3. Upload the normalized object to storage.
4. In a SQL transaction, create the PRODUCT_MEDIA/USER_AVATARS relationship and mark the asset Active.
5. If upload or association fails, mark the asset DeletePending; do not expose it in API responses.
6. A cleanup worker retries DeletePending objects and removes the metadata row only after storage deletion succeeds.
7. A stale-Pending sweep handles process crashes during upload. It must use a safe age threshold and never delete Active assets.

For deletion/replacement, remove the relationship and mark the old asset DeletePending in the same SQL transaction. The worker performs object deletion and retries transient provider failures. This prevents a failed object delete from silently leaving an untracked object.

The final worker cadence, retry policy and retention threshold must be set with the selected provider and runtime deployment.

## 5. Upload validation and security

- Accept only JPEG, PNG and WebP.
- Enforce 5 MB/product image and 2 MB/avatar using actual streamed bytes; do not trust client Content-Length or filename extension.
- Inspect file signatures and fully decode the image; reject malformed, polyglot, SVG, HTML and unsupported formats.
- Use an image decoder such as Pillow with decompression-bomb protections and a documented pixel/dimension limit before implementation.
- Normalize/re-encode accepted images and strip EXIF/GPS metadata before storage.
- Generate opaque object keys server-side; never use user-supplied paths or filenames as storage keys.
- Limit upload count to five images per product and apply rate/size limits at the API boundary.
- Require authenticated requests and enforce ownership on every upload, delete, reorder and cover action.
- Never expose storage credentials or internal storage endpoints to the browser.
- Avoid logging image bytes, signed URLs, authorization headers or storage credentials.

## 6. Ownership and product-state rules

- A user may upload, replace or delete only their own avatar.
- A seller may mutate media only for products they own.
- Preserve current listing lifecycle: Available and Hidden listings may be edited by their owner; Reserved and Sold listings remain read-only for media mutations.
- Public product responses expose media only where the product itself is visible under the existing public visibility rules.
- Hidden product media may be returned only to the authenticated owner.
- Public profile may expose avatar and bio, but never email, student ID or password hash.
- No admin/moderator bypass is introduced by this media scope.

## 7. Proposed API contract

### Profile

- Extend `PATCH /api/users/me` with optional `bio` (trimmed plain text, max 300).
- `POST /api/users/me/avatar` — multipart upload; authenticated user only.
- `DELETE /api/users/me/avatar` — remove current avatar and restore initials fallback.
- Extend `GET /api/users/me` and public profile DTO with bio and an avatar media representation.

### Product media

- `POST /api/products/{product_id}/media` — upload one image.
- Product detail/list DTO includes an ordered media array and cover indicator.
- `DELETE /api/products/{product_id}/media/{media_id}` — remove an owned image.
- `PATCH /api/products/{product_id}/media/order` — replace order with the exact set of current media IDs; reject duplicates, missing IDs and foreign product IDs.
- `PATCH /api/products/{product_id}/media/{media_id}/cover` — set the cover atomically.

Suggested media response fields:
`media_id`, `url`, `content_type`, `size_bytes`, `width`, `height`, `sort_order`, `is_cover`, `alt_text`.

The API generates the read URL from the storage adapter. SQL Server stores only the storage key and metadata, never the resolved URL.

## 8. URL access policy — decided

Use **private object storage plus short-lived presigned GET URLs** for hosted media. Set the initial `MEDIA_READ_URL_TTL_SECONDS` default to **900 seconds (15 minutes)**. The API generates a URL only after it has checked the relevant resource access rule:
- Public product media: the listing is currently visible through the public marketplace rules and is not under a moderation hold.
- Hidden product media: only the authenticated owner may receive a read URL.
- Avatar: public profile visibility follows the existing public-profile rules; the owner may always access their own avatar.

A presigned URL is a bearer capability: anyone who obtains it can read that object until it expires. Do not log it, persist it in SQL Server, put it in audit records, or return it from an API response that otherwise hides the associated resource. A listing becoming hidden cannot revoke an already-issued URL instantly; the 15-minute expiry bounds that exposure window. Keep the bucket private and never solve this by making the entire bucket public.

The API response may include a `url` field as expected by the existing FE-3 DTO. Add a read-URL refresh operation (for example, `GET /api/media/{media_id}/read-url`) that re-runs the same authorization checks. The frontend must request a fresh URL and retry an expired/failed image at most once; it must not mark an expired signature as a permanently missing asset or enter an infinite retry loop.

R2 presigned URLs use the R2 S3 API hostname and cannot be generated against a custom domain. Accept this trade-off for the first implementation. Do not enable public bucket access, `r2.dev`, or a public CDN path as a shortcut. A future CDN/Worker gateway requires a separate design that preserves the same hidden-listing and moderation authorization rules.

## 9. DWH boundary

Do not add `bio`, avatar keys, image keys, image URLs, MIME values, checksums or other media metadata to:
- `extract_users`
- `extract_products`
- `dim_user`
- `dim_product`
- transaction facts or analytics.

The existing explicit ETL column lists should remain unchanged. Media/profile customization is operational marketplace data, not part of the current approved analytical model.

## 10. Migration and implementation sequence

The storage decision is now settled, but DB-0 runtime verification remains a hard gate for SQL changes. Work can proceed in this order without connecting to or modifying the user's database:

1. Implement and unit-test the filesystem and S3-compatible storage adapters independently of SQL Server.
2. Verify DB-0 against a dedicated SQL Server `*_test` database and record the actual schema/migration state.
3. Add a versioned additive T-SQL migration for MEDIA_ASSETS, PRODUCT_MEDIA, USER_AVATARS and USERS.bio only after the schema baseline and recovery plan are approved.
4. Add ORM models and Pydantic DTOs; keep SQL Server as the schema source of truth.
5. Add upload validation, ownership checks, lifecycle/cleanup worker and tests.
6. Update `docs/api_contract.md`, Docker/local configuration and migration documentation.
7. Add SQL Server integration tests for constraints, concurrency, uniqueness and cleanup behavior.
8. Integrate FE-3/FE-5 only after the real API is available.

Do not edit existing data or run a migration on the user's database without a verified backup. Do not change `01_init_schema.sql` in a way that drops or recreates existing tables; keep fresh-install schema synchronized only when implementation is approved and tested.

## 11. Open implementation gates

- [ ] Verify the actual target SQL Server schema and applied migration state (DB-0; user is performing the local check).
- [ ] Provision the R2 account/bucket and runtime credentials, or record an approved S3-compatible replacement if the eventual deployment host already supplies object storage.
- [ ] Set image pixel/dimension limits and cleanup retry/retention policy before upload endpoints are exposed.
- [ ] Verify backup and rollback/recovery plan for the target database before applying the additive migration.
- [ ] Decide and document the persistent local media volume when integrating the filesystem adapter into Docker Compose.

**DB-1 design output:** logical schema, API proposal, validation/security rules, object lifecycle, provider default, local development strategy, read-URL authorization and DWH boundary are documented. Storage adapter implementation can proceed independently; SQL migration remains blocked on DB-0 verification and the target database recovery plan.
