# FE-1 — Frontend foundation implementation

**Date:** 2026-11-11  
**Branch:** `feat/frontend-foundation`  
**Scope:** Approved FE-1 boundary from `docs/UI_AUDIT_2026-11-11.md`.

## Changes

- Added a reusable primitive set for buttons, labeled fields, empty states, loading skeletons and semantic status badges in `frontend/src/components/primitives.tsx`.
- Extended the existing graphite/lime/cyan theme tokens with a spacing scale, typography roles and motion durations. Existing dark/light color tokens and visual identity remain in place.
- Removed the duplicate theme control from the global top bar. Dark/light switching remains in Account Center → Settings.
- Changed password settings so the form appears after the user chooses **Đổi mật khẩu**. The cancel action clears all password values and transient messages; the existing change-password endpoint and validation remain in use.
- Added labeled modal semantics, focus placement/restoration, Escape-to-close, Tab focus containment, background inertness and body scroll locking for authentication, product detail and cart overlays.
- Added accessible status announcements and close labels to global notices, semantic listing status in product detail, shared empty states in the marketplace/cart, and a skeleton for review loading.
- Kept the pre-existing untracked `frontend/src/components/ui/` directory untouched.

## Behavior and data impact

- Purchase, authentication, profile, listing and review API contracts are unchanged.
- No database schema, migration or stored user data was changed.
- The password form continues to use `POST /api/users/me/change-password`.
- Product photos, profile avatar/bio, Explore filters and transaction history remain deferred to their backend dependencies in the roadmap.

## Verification

- `npm.cmd run build` — passed (`tsc -b` and Vite production build).
- `git diff --check` — passed.
- Browser, screen-reader, contrast and keyboard interaction checks were not run. Focus behavior is implemented in source but still needs manual browser/assistive-technology review before release.
- Backend and database tests were not run because this frontend-only step changes no backend behavior or schema.

## Review notes

The audit and implementation changes are pushed on `feat/frontend-foundation` in [PR #26](https://github.com/Nghiepcoder17v/cho-troi-uit/pull/26), targeting `main`. The pre-existing user-owned `frontend/src/components/ui/` directory remains untracked and was excluded from the commit. The repository's current GitHub default branch was five commits ahead of the original local baseline, with README as the only file changed in that range. Check PR #26 for the latest CI and review state.
