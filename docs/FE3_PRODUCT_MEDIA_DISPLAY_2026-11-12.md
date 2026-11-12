# FE-3 — Product Media Display Foundation

**Date:** 2026-11-12  
**Branch:** `feat/product-media-display`  
**Base:** `main` at `92e573f05faf41aed43c0f95bc63475f7447733c`  
**Status:** Presentation layer implemented; waiting for DB-3 media API for real product images.

## 1. Scope delivered

This step prepares a reusable UI component for real image metadata returned by the future product media API. It does not simulate an upload or invent image URLs.

- Added optional `Product.media` to the TypeScript DTO contract, with the fields proposed in DB-1: `media_id`, `url`, `content_type`, `size_bytes`, `width`, `height`, `sort_order`, `is_cover`, `alt_text`.
- Added reusable `ProductMediaGallery`.
- Connected the gallery to `ProductCard` and `ProductDetailModal`.
- Kept the existing deterministic glyph fallback whenever the API does not provide media or every image fails to load.

## 2. Gallery behavior

- Sorts media by `sort_order`; the flagged cover is selected by default.
- Product cards show the cover and a small image-count indicator when there are multiple images.
- Product detail supports thumbnail buttons with selected state and keyboard interaction.
- Uses server-provided `url` unchanged; the frontend does not construct storage/CDN URLs or know provider credentials.
- Uses lazy loading and async decoding in cards; detail image is eager to avoid delaying the open modal.
- A failed source is excluded from selection; if the cover fails, the next available image is selected, then the legacy glyph if all fail.
- Failure state resets when the product changes or the media URL list changes, which permits refreshed/signed URLs to be retried.
- Alt text uses the API value when present and otherwise uses a product-title-based description.

## 3. Backward compatibility and non-goals

Current backend Product DTOs do not yet return media. Therefore existing products continue to display the old glyph fallback until DB-3 returns a populated `media` array. This is intentional and is not represented as complete image upload integration.

Not implemented in this step:
- Upload/delete/reorder/cover APIs or any upload UI.
- Storage provider, bucket, CDN or signed URL selection.
- SQL migration, ORM models or database writes.
- Avatar/bio or user profile media.
- Browser QA, device-specific layout verification or screen-reader testing.

## 4. Files changed

- `frontend/src/types.ts`
- `frontend/src/components/ProductMediaGallery.tsx` (new)
- `frontend/src/components/ProductCard.tsx`
- `frontend/src/components/ProductDetailModal.tsx`
- `frontend/src/components/account/AccountExtras.tsx`
- `frontend/src/components/account/AccountManagement.tsx`
- `frontend/src/styles.css`

## 5. Verification

The project frontend package currently exposes a TypeScript/Vite `build` script but no dedicated component-test script. GitHub Actions is expected to run the existing frontend build. This branch has not been browser-tested in this session.

The deferred browser QA remains necessary for actual image aspect ratios, thumbnail interaction, keyboard focus, loading failures, Dark/Light themes and mobile layouts. SQL Server verification is unrelated to this presentation-only change and remains deferred as agreed.

## 6. Next dependency

Once DB-0 and the media-storage provider/URL policy gates are settled, DB-3 can supply the Product DTO's `media` array. This gallery is ready to consume that response without changing its rendering contract. The upload flow and image management controls remain separate work.
