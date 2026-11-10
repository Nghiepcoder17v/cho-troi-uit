# Chợ Trời UIT — Design Profile

> Version: 1.0  
> Status: Approved design direction  
> Last updated: 2026-11-10  
> Scope: Frontend visual language and interaction guidance for the Chợ Trời UIT pilot

## 1. Design direction

### 1.1 Product identity

**Gaming Gear Marketplace × Modern SaaS**

Chợ Trời UIT should feel like a modern technology marketplace built for the UIT community: confident, practical, energetic and trustworthy. The visual language takes inspiration from gaming peripherals and enthusiast hardware through dark graphite surfaces, crisp borders, controlled lime accents and electric-cyan details.

The result must remain a usable marketplace, not a gaming launcher or RGB showcase. Product information, price, condition, seller identity, order state and primary actions always take priority over decoration.

### 1.2 Core principles

1. **Product first.** Product title, image, condition, price and seller information must be quickly scannable.
2. **Clear hierarchy.** Use spacing, typography, surface contrast and borders to separate sections. Do not rely on color alone.
3. **Purposeful accents.** Lime identifies primary actions and selected states. Cyan is a secondary technology accent. Neither should become a large, distracting glow.
4. **Trust through clarity.** Show the real meaning of transaction and reputation states. Never imply payment, delivery or a verified review when the system has not recorded it.
5. **Consistent patterns.** Buttons, inputs, cards, dialogs, notifications and status badges should behave consistently across screens.
6. **Accessible by default.** Target WCAG 2.2 Level AA for applicable criteria, including keyboard use, focus visibility, contrast and understandable errors.
7. **Responsive by design.** Mobile must have an explicit navigation pattern and must not simply hide desktop navigation.
8. **Preserve the product.** Visual work must not silently change API contracts, authentication, authorization or existing business rules.

### 1.3 What this direction is not

- Not a full-screen neon or RGB aesthetic.
- Not a low-contrast dark interface with gray text that is difficult to read.
- Not a generic pastel editorial storefront.
- Not a collection of unrelated card styles, radii, shadows and button treatments.
- Not decorative motion that delays shopping tasks or causes accessibility issues.

## 2. Brand and color system

### 2.1 Brand accents

| Token | Value | Intended role |
|---|---|---|
| Brand primary | `#C7F36B` | Main CTA fill, selected indicators, key highlights |
| Brand secondary | `#62D7F2` | Secondary accent, informational details, subtle data visualization |
| Brand dark | `#0B0F14` | Dark-theme page background |
| Brand ink | `#17212B` | Primary text on light surfaces and text on bright accent fills |

**Usage rules**

- Use primary lime for the most important action in a view, not every button.
- Use cyan sparingly for secondary actions, informational emphasis and small decorative details.
- Use dark foreground text on lime or cyan filled controls in both themes.
- Do not use lime or cyan as body text on white or pale surfaces. Use the normal text tokens instead.
- Never communicate success, warning, error or order state using color alone; pair color with readable text and, where helpful, an icon.
- Keep glow effects limited to a focused active/selected detail. Avoid permanent glow around every card or control.

### 2.2 Dark theme tokens

Dark is the default presentation for a first visit unless a later product decision changes this behavior.

| Token | Value | Purpose |
|---|---|---|
| `--color-bg` | `#0B0F14` | Application background |
| `--color-surface` | `#121923` | Cards, main panels |
| `--color-surface-elevated` | `#192332` | Dialogs, popovers, elevated panels |
| `--color-border` | `#2B3949` | Decorative and structural borders |
| `--color-text` | `#F4F7FB` | Primary text |
| `--color-text-muted` | `#A2AFBC` | Secondary text |
| `--color-primary` | `#C7F36B` | Primary accent |
| `--color-secondary` | `#62D7F2` | Secondary accent |
| `--color-on-accent` | `#0B0F14` | Text and icons on bright accent fills |

### 2.3 Light theme tokens

| Token | Value | Purpose |
|---|---|---|
| `--color-bg` | `#F3F6F9` | Application background |
| `--color-surface` | `#FFFFFF` | Cards, main panels |
| `--color-surface-elevated` | `#EAF0F5` | Dialogs, popovers, elevated panels |
| `--color-border` | `#D5DEE7` | Decorative and structural borders |
| `--color-text` | `#17212B` | Primary text |
| `--color-text-muted` | `#526273` | Secondary text |
| `--color-primary` | `#C7F36B` | Primary accent |
| `--color-secondary` | `#62D7F2` | Secondary accent |
| `--color-on-accent` | `#0B0F14` | Text and icons on bright accent fills |

### 2.4 Semantic colors

Create semantic tokens separately from brand accents:

| Semantic role | Use |
|---|---|
| Success | Completed actions and confirmed outcomes |
| Warning | Attention required, pending action or expiring state |
| Danger | Failed actions, destructive actions and validation errors |
| Info | Neutral information and guidance |

Semantic colors must have theme-appropriate foreground, surface and border variants. Their final values must be selected and contrast-tested during UI Foundation implementation. A lime brand accent must not automatically mean “success”; for example, a pending order is not a completed order.

### 2.5 Contrast and color validation

- Normal text must meet at least 4.5:1 contrast against its actual rendered background.
- Large text must meet at least 3:1.
- Essential UI component boundaries, states and focus indicators must meet the applicable WCAG 2.2 AA non-text contrast requirements.
- Validate actual foreground/background combinations in both themes; testing isolated palette swatches is not sufficient.
- The palette in this document is the approved visual direction, not a claim that every possible token pairing has already passed an automated accessibility audit.

## 3. Typography

### 3.1 Font families

| Usage | Family |
|---|---|
| Display headings and section titles | Space Grotesk |
| Body, forms, navigation and metadata | DM Sans |
| Numeric values and prices | DM Sans; Space Grotesk may be used for prominent totals |

Keep the existing font families in the project. Do not add another font family without a clear need. Provide system fallbacks and use a non-blocking font loading strategy.

### 3.2 Type scale

Use this scale as the starting point; responsive layouts may reduce display sizes when necessary.

| Role | Suggested size | Typical weight |
|---|---:|---:|
| Display | 40–56 px | 600–700 |
| Page title | 32–40 px | 600–700 |
| Section title | 24–30 px | 600–700 |
| Card title | 16–18 px | 600 |
| Body | 14–16 px | 400–500 |
| Supporting text | 12–14 px | 400–500 |
| Eyebrow / compact label | 11–12 px | 600–700 |

Use comfortable line-height for body text (approximately 1.5). Avoid overly tight tracking on long headings and never reduce essential content to tiny metadata text.

## 4. Layout, spacing and shape

### 4.1 Spacing

Use a 4 px base spacing unit. Preferred steps:

`4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80 px`

Use spacing consistently within component families. Do not introduce arbitrary values when a token from this scale works.

### 4.2 Content layout

- Use a centered content container with a comfortable maximum width (approximately 1200–1280 px) and responsive side padding.
- Keep the marketplace product grid dense enough to compare products without making cards cramped.
- Desktop product listing: typically 3–4 columns depending on available width.
- Tablet: typically 2 columns.
- Narrow mobile: 1–2 columns only when product image and title remain legible; prefer 1 column when the content becomes crowded.
- Align page headings, filters, result counts and content edges consistently.
- Use a stable aspect ratio for product media so cards do not jump while images load.

### 4.3 Radius

| Element | Radius |
|---|---:|
| Small controls and tags | 6–8 px |
| Inputs and buttons | 8–12 px |
| Product cards and panels | 12–16 px |
| Drawers and dialogs | 16–20 px |
| Pills / circular avatars | Fully rounded |

Avoid oversized rounded corners on every surface; use shape to communicate component hierarchy.

### 4.4 Borders and elevation

- Standard card and panel border: 1 px.
- Stronger active, focused or selected boundary: approximately 2 px where helpful.
- Use borders to make layout structure visible, especially in dark theme.
- Do not rely only on subtle border color for essential form-control boundaries; validate non-text contrast against adjacent surfaces.
- Keep shadows soft and restrained. Use elevation mainly to distinguish overlays from page content.
- Reserve accent outlines or glow for selected/focused items, not all resting components.

## 5. Component styling and behavior

### 5.1 Buttons

Define consistent variants:

- **Primary:** lime fill, dark text; the main action in a section.
- **Secondary:** surface fill with a clear border.
- **Tertiary / ghost:** transparent background for low-emphasis actions.
- **Danger:** semantic danger treatment for destructive actions.
- **Disabled:** visually distinct and non-interactive, with sufficient readable contrast.

Every button must have visible hover, pressed, focus-visible and disabled states. Do not rely on hover alone to reveal an action.

### 5.2 Inputs and forms

- Use persistent labels; placeholders are examples, not labels.
- Provide clear focus-visible boundaries.
- Show validation messages next to the relevant field and summarize form-level errors when useful.
- Preserve typed values after validation errors.
- Indicate required fields and constraints before submission.
- Make loading and submission states explicit and prevent accidental duplicate submissions.

### 5.3 Product cards

A product card should prioritize:

1. Product image or clearly designed media placeholder.
2. Product condition and availability.
3. Product title.
4. Listed price.
5. Seller identity and, when available, genuine review summary.
6. A clear action to open product details.

Keep cards visually consistent and make the whole card behavior predictable. Do not present a placeholder glyph as if it were a real product photograph.

**Current implementation constraint:** the inspected product API/model does not currently expose product image URLs or an upload endpoint. The design should reserve a media area and provide a truthful fallback. Adding image storage, upload or new product fields is a separate API/database scope and must be approved before implementation.

### 5.4 Status badges

Use text labels with semantic styling. The design must distinguish at least:

- Product: Available, Reserved, Sold, Hidden (where visible to its owner).
- Purchase request: Pending, Accepted, Cancelled, Completed.

The agreed purchase workflow is:
- Buyer submits a request → Pending.
- Seller accepts → Accepted.
- Seller rejects → Cancelled and the product becomes available again.
- The transaction becomes Completed only after both buyer and seller confirm completion.

Do not label Accepted as Completed, and do not display “payment successful” when the platform has not processed a payment.

### 5.5 Dialogs, drawers and notifications

- Dialogs must have an accessible name, dialog semantics and a deliberate initial focus.
- Keyboard focus must remain usable within an open modal; Escape should close dismissible dialogs.
- Return focus to the element that opened the dialog.
- Drawers must remain usable on narrow screens and must not trap content off-screen.
- Toast notifications must remain readable, use semantic status appropriately and not be the only place where important errors are communicated.
- Destructive or irreversible actions require a clear confirmation step.

### 5.6 Loading, empty and error states

Every data-driven section should have a defined loading, empty, error and success state. Avoid indefinite “Loading…” text after a failed request. Empty states should explain what is empty and provide one useful next action where appropriate.

## 6. Screen-level guidance

### 6.1 Marketplace

- Strong page heading and search entry point.
- Category filters that are easy to scan and have a visible selected state.
- Result count, sort/filter context and pagination controls when the API returns paginated results.
- Product cards with consistent image ratios and clear prices.
- Useful empty and loading states.

### 6.2 Product details

- Product media and key facts should be prominent.
- Show condition, description, listed price and seller profile entry.
- Separate genuine review score/count from completed transaction count.
- Show “Chưa có đánh giá” when there are no eligible reviews; never fabricate a default star score.
- Make the action label reflect the actual action, such as adding to cart or sending a purchase request.

### 6.3 Cart and purchase flow

- Show item title, current listed price, seller and availability.
- Recheck availability and price with the backend before creating a purchase request; localStorage data is not authoritative.
- Clearly summarize the total and explain that the platform does not process payment unless a real payment integration is introduced.
- Show per-item outcomes if a multi-item checkout is not atomic.
- Explain the next step and the current order status after submission.

### 6.4 Account Center

Use a clear account navigation pattern that separates:

- Overview.
- Personal profile.
- Settings.
- Cart.
- Purchase orders.
- Sales requests / sales orders.
- Product listings.

On mobile, convert the account navigation to a usable compact menu or another explicit pattern; do not simply hide it.

### 6.5 Review and reputation

- Only eligible participants in a Completed transaction may review the other participant.
- Each participant may submit at most one review per transaction.
- Show average rating and review count together.
- Show transaction count separately from review score.
- Do not show a numeric rating when there are no reviews.
- Avoid exposing private contact or student data in public profile surfaces.

## 7. Responsive behavior

Use content-driven breakpoints rather than designing for a single device width. Starting breakpoints for implementation:

| Range | Guidance |
|---|---|
| 320–599 px | Mobile; compact navigation, single-column forms, usable product cards and drawers |
| 600–767 px | Large mobile / small tablet; adapt navigation and grid to available width |
| 768–1023 px | Tablet; usually two-column content and compact account navigation |
| 1024 px and above | Desktop; expanded navigation and multi-column marketplace grid |

These are starting points, not rigid requirements. Components must remain usable between breakpoints, at 200% zoom and with long Vietnamese text.

## 8. Accessibility and interaction requirements

- Target WCAG 2.2 Level AA for all applicable criteria.
- Use semantic landmarks, meaningful heading order and native controls where practical.
- All functionality must be available using a keyboard.
- Provide a clearly visible focus indicator; do not remove browser outlines without replacing them.
- Dialogs must support accessible naming, focus management and keyboard dismissal when dismissible.
- Associate every input with a visible label and its validation message.
- Announce important asynchronous outcomes and errors to assistive technology.
- Do not use color, position or icon alone to convey a state.
- Provide sufficient contrast in both themes and in hover, focus, disabled and selected states.
- Aim for comfortable touch targets around 44 × 44 CSS px; never fall below applicable WCAG 2.2 target-size requirements without a valid exception.
- Respect `prefers-reduced-motion`.
- Avoid flashing, parallax or motion that interferes with reading or interaction.

## 9. Motion and micro-interactions

- Typical transitions: approximately 150–220 ms.
- Use subtle opacity, color and small positional changes for hover/pressed feedback.
- Avoid large scaling, constant pulsing, excessive blur and animated glow loops.
- Loading indicators must not block understanding of the current state.
- Disable or simplify non-essential motion when reduced motion is requested.

## 10. Implementation guidance

1. Treat this document as the source of truth for the visual direction of the pilot.
2. Implement theme tokens as CSS custom properties; component styles should consume tokens rather than hard-coded theme colors.
3. Keep theme-specific values in explicit theme scopes (for example, a root theme attribute).
4. Persist the user's theme choice. A first-visit default of Dark is the current direction; a later system-preference policy can be decided during implementation without breaking saved user choice.
5. Reuse existing React, TypeScript, Vite and existing font dependencies. Do not add a UI framework or component library solely for styling.
6. Clean up the current stylesheet as part of the UI Foundation phase; avoid layering duplicate rules over the existing CSS.
7. Keep components small and reusable where that improves consistency. Do not split files mechanically without a maintainability benefit.
8. Keep presentation changes separate from business/API changes. Any new API, database field, migration, dependency or workflow behavior must be explicitly scoped and reviewed.
9. Validate both themes, responsive states, keyboard interactions, focus indicators and real contrast combinations before declaring the design implementation complete.

## 11. Out of scope for this Design Profile

This document does not authorize implementation of:
- Payment processing, shipping or delivery tracking.
- Real-time chat or push notifications.
- Product image storage/upload or a new media API.
- A full moderation/admin system.
- Unapproved changes to authentication, authorization, database behavior or the ETL/DWH pipeline.

These may be proposed separately with their own impact and approval.

## 12. Design acceptance checklist

- [ ] Dark and Light themes use the defined semantic tokens.
- [ ] Brand lime and cyan are used purposefully and never as low-contrast body text on light surfaces.
- [ ] Typography, spacing, radii, borders and elevations are consistent.
- [ ] Marketplace, product detail, cart, account and order surfaces follow the same component language.
- [ ] Product media has a stable layout and an honest fallback until image support exists.
- [ ] Product/order states use accurate labels and are not communicated by color alone.
- [ ] Mobile navigation and account navigation remain available and usable.
- [ ] Loading, empty, error, disabled, focus and success states are designed.
- [ ] Applicable WCAG 2.2 AA contrast, keyboard and interaction requirements are checked in both themes.
- [ ] Reduced-motion preferences are respected.
- [ ] No business logic, API contract, database or authentication change is introduced by visual styling alone.
