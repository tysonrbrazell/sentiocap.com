# SentioCap — Frontend Page Specifications

> Framework: Next.js 14 App Router | Auth: Supabase | Styling: Tailwind + shadcn/ui

---

## Route Map

| Route | File | Auth Required |
|-------|------|--------------|
| `/` | `app/page.tsx` | No |
| `/login` | `app/(auth)/login/page.tsx` | No |
| `/dashboard` | `app/(app)/dashboard/page.tsx` | Yes |
| `/plans` | `app/(app)/plans/page.tsx` | Yes |
| `/plans/new` | `app/(app)/plans/new/page.tsx` | Yes |
| `/plans/[id]` | `app/(app)/plans/[id]/page.tsx` | Yes |
| `/plans/[id]/upload` | `app/(app)/plans/[id]/upload/page.tsx` | Yes |
| `/plans/[id]/variance` | `app/(app)/plans/[id]/variance/page.tsx` | Yes |
| `/investments` | `app/(app)/investments/page.tsx` | Yes |
| `/investments/new` | `app/(app)/investments/new/page.tsx` | Yes |
| `/investments/[id]` | `app/(app)/investments/[id]/page.tsx` | Yes |
| `/benchmarks` | `app/(app)/benchmarks/page.tsx` | Yes |
| `/settings` | `app/(app)/settings/page.tsx` | Yes |

---

## Layout Architecture

### Root Layout (`app/layout.tsx`)
- Applies global fonts, Tailwind base styles, metadata
- Wraps all pages in `<SupabaseProvider>` (session context)
- No nav — each route group has its own layout

### Auth Layout (`app/(auth)/layout.tsx`)
- Centered card, no sidebar
- Redirects to `/dashboard` if session already active

### App Layout (`app/(app)/layout.tsx`)
- `<Sidebar>` — fixed left, 240px wide, collapsible to icon rail
- `<Header>` — top bar: breadcrumb, org switcher, user avatar menu
- `<main>` — scrollable content area
- Redirect to `/login` if no session

---

## Pages

---

### 1. `/` — Landing Page

**Status:** Exists as `index.html` — convert to Next.js App Router page.

**Layout:** Full-width, no sidebar. Standalone marketing page.

**Key Components:**
- `<HeroSection>` — headline, sub-headline, CTA button ("Get Started")
- `<FeatureGrid>` — 3-column cards: AI Classification, RTB/CTB Clarity, Benchmarking
- `<DemoScreenshot>` — static screenshot or animated mockup of dashboard
- `<CTABanner>` — bottom CTA with "Request Demo" button
- `<NavBar>` — logo left, "Login" right

**Data Sources:** None (static content)

**User Interactions:**
- "Get Started" → `/login`
- "Login" → `/login`
- "Request Demo" → mailto or Calendly link (configurable via env var)

---

### 2. `/login` — Authentication

**Layout:** Auth layout (centered card, 480px max-width)

**Key Components:**
- `<LoginForm>` — email input, password input, submit button
- `<ErrorAlert>` — inline error for bad credentials
- `<LoadingSpinner>` — button loading state during auth

**Data Sources:**
- Supabase `auth.signInWithPassword()` — client-side

**User Interactions:**
- Submit form → Supabase auth → redirect to `/dashboard` on success
- Failed auth → show error message inline
- "Forgot password?" link → Supabase password reset email flow

**Notes:**
- No sign-up on this page — invite-only model (users created via `/settings`)
- Session stored in Supabase cookie; middleware guards all `/app/*` routes

---

### 3. `/dashboard` — Main Dashboard

**Layout:** App layout (sidebar + header)

**Key Components:**

#### KPI Tiles Row
- `<KPITile label="Total OpEx" />` — total spend across active plan
- `<KPITile label="RTB Amount" color="blue" />` — Run The Business total
- `<KPITile label="CTB Amount" color="emerald" />` — Change The Business total
- `<KPITile label="CTB %" />` — CTB as % of total OpEx
- `<KPITile label="Revenue / OpEx" />` — efficiency ratio

#### Charts Row
- `<DonutChart>` — RTB vs CTB split; hover shows exact amounts
- `<L2BarChart>` — horizontal bar chart: 8 L2 categories, each bar colored by L1, signal dots on right edge

#### Treemap
- `<Treemap>` — drill-down: L1 → L2 → L3 → L4 on click
- Breadcrumb trail above treemap showing current drill level
- Color intensity = spend magnitude; label = category name + amount

#### Alerts Panel
- `<VarianceAlertList>` — last 5 variance alerts: L2 label, variance %, signal dot (🔴🟡🟢), link to `/plans/[id]/variance`

**Data Sources:**
- `GET /api/dashboard/summary` — KPI values, RTB/CTB totals, L2 breakdown
- `GET /api/dashboard/treemap` — hierarchical spend data for treemap
- `GET /api/plans/{id}/variance?summary=true` — recent alerts

**User Interactions:**
- Click KPI tile → no action (display only)
- Click donut segment → filter L2 bar chart
- Click treemap cell → drill down one level
- Click variance alert → navigate to `/plans/[id]/variance`
- Breadcrumb in treemap → navigate back up levels

---

### 4. `/plans` — Plan List

**Layout:** App layout

**Key Components:**
- `<PageHeader title="Plans">` with `<Button>+ New Plan</Button>`
- `<PlanTable>` — sortable table columns:
  - Plan Name (link to `/plans/[id]`)
  - Type (badge: Annual / Quarterly / Rolling)
  - Fiscal Year
  - Status (badge: Draft / Under Review / Approved / Archived)
  - Total Spend (formatted currency)
  - Line Items (count)
  - Last Updated (relative time)
  - Actions: View, Archive

**Data Sources:**
- `GET /api/plans` — paginated plan list with status, metadata

**User Interactions:**
- "+ New Plan" → `/plans/new`
- Row click → `/plans/[id]`
- Status badge filter (tabs above table): All | Draft | Under Review | Approved
- Sort by column header click
- Archive action → `DELETE /api/plans/{id}` with confirmation modal

---

### 5. `/plans/new` — Create Plan

**Layout:** App layout, narrow centered form (max-width 640px)

**Key Components:**
- `<StepIndicator>` — 2 steps: "Plan Details" → "Upload"
- **Step 1:** `<PlanDetailsForm>`
  - Name (text input)
  - Type (select: Annual / Quarterly / Rolling)
  - Fiscal Year (select: current year ± 2)
  - Description (textarea, optional)
  - "Continue" button → validate → advance to step 2
- **Step 2:** `<UploadZone>` (see `/plans/[id]/upload` for full spec)
  - Simplified version: drag-drop or file picker, CSV/XLSX
  - "Upload & Classify" button → POST to API → redirect to `/plans/[id]/upload`

**Data Sources:**
- `POST /api/plans` — create plan record → returns `{id}`
- `POST /api/plans/{id}/upload` — initiate upload and classification

**User Interactions:**
- Step 1 complete → create plan record, advance to step 2
- Step 2 file drop → preview filename, size
- "Upload & Classify" → show loading state → redirect to `/plans/[id]/upload` for full review
- "Back" → return to step 1

---

### 6. `/plans/[id]` — Plan Detail

**Layout:** App layout

**Key Components:**
- `<PageHeader>` — plan name, status badge, fiscal year, approve button (if `status === 'under_review'`)
- **Summary Stats Row:**
  - Total spend, line item count, classified %, avg confidence
- `<PlanLineItemTable>` — main table:
  - Columns: Description, Cost Center, GL Account, Amount, L1, L2, L3, L4, Confidence, Actions
  - `<ClassificationBadge>` — color-coded L1 (blue=RTB, emerald=CTB)
  - `<ConfidenceBadge>` — green ≥0.85, yellow 0.65–0.84, red <0.65
  - Inline edit: click L1–L4 cell → dropdown to reclassify → `PATCH /api/plans/{id}/line-items/{itemId}`
  - Actions column: reclassify button, flag for review
- **Toolbar above table:**
  - Search input (filters description client-side)
  - Filter: L1 (All / RTB / CTB), L2 (multi-select dropdown), Confidence (All / High / Medium / Low)
  - Export CSV button
- **Pagination:** server-side, 50 rows/page

**Data Sources:**
- `GET /api/plans/{id}` — plan metadata, summary stats
- `GET /api/plans/{id}/line-items?page=1&limit=50&filters=...` — paginated line items
- `PATCH /api/plans/{id}/line-items/{itemId}` — update classification
- `POST /api/plans/{id}/approve` — transition status to Approved

**User Interactions:**
- Click "Approve" → confirmation modal → `POST .../approve` → status badge updates
- Click "Upload More" → `/plans/[id]/upload`
- Click "Variance" → `/plans/[id]/variance`
- Inline reclassify → edit cell → save on blur/enter
- Export → download CSV of all line items with classifications

---

### 7. `/plans/[id]/upload` — CSV Upload & AI Classification

**Layout:** App layout, full-width

**Key Components:**

**Phase 1 — Upload:**
- `<UploadZone>` — drag-drop area, or click to browse; accepts `.csv`, `.xlsx`
- File preview: filename, size, row count estimate
- "Map Columns" button to proceed

**Phase 2 — Column Mapping:**
- `<ColumnMappingTable>` — detected CSV headers on left, mapped field on right (select dropdown)
- Required fields: Description, Amount
- Optional: Cost Center, GL Account, Vendor, Department
- "Preview" shows first 5 rows with mapped values
- "Start Classification" button

**Phase 3 — AI Classification Progress:**
- `<ClassificationProgressBar>` — animated progress bar (batches of 50)
- Status text: "Classifying 150/500 line items..."
- Polls `GET /api/plans/{id}/classification-status` every 2 seconds
- On complete → advance to Phase 4

**Phase 4 — Review Table:**
- `<ReviewTable>` — all classified line items
- Row background: green (confidence ≥0.85), yellow (0.65–0.84), red (<0.65)
- Columns: Description, Amount, L1, L2, L3, L4, Confidence, Reasoning (expandable)
- Inline edit on any classification cell
- "Confirm & Save" button → `POST /api/plans/{id}/line-items/bulk`

**Data Sources:**
- `POST /api/plans/{id}/upload` — upload file, returns job ID
- `GET /api/plans/{id}/classification-status` — poll for progress
- `POST /api/plans/{id}/line-items/bulk` — save confirmed classifications

**User Interactions:**
- Drop file → preview → map columns → classify → review → confirm
- Edit any cell in review table before confirming
- Filter review table by confidence level
- "Re-classify Selected" — re-run AI on selected rows

---

### 8. `/plans/[id]/variance` — Actuals vs Plan

**Layout:** App layout, wide

**Key Components:**
- `<VarianceHeader>` — plan name, fiscal year, YTD summary (plan YTD, actual YTD, variance $, variance %)
- `<MonthlyVarianceTable>` — rows = L2 categories, columns = Jan–Dec + Full Year
  - Each cell: plan amount (light) + actual amount (bold) + variance % below
  - `<SignalDot>` — 🔴 >10% over, 🟡 5–10% over, 🟢 within 5%
  - Sticky first column (L2 category name)
  - Sticky header row
- `<RunRateCard>` — current run-rate annualized vs annual plan target
- `<YTDProgressBar>` — % of year elapsed vs % of budget consumed (visual gauge)

**Data Sources:**
- `GET /api/plans/{id}/variance` — monthly plan vs actual by L2 category
- `GET /api/actuals?plan_id={id}&period=ytd` — YTD actuals

**User Interactions:**
- Click L2 category row → expand to show L3 breakdown
- Click month column header → sort by that month's variance
- "Upload Actuals" button → modal with CSV upload for actuals data
- Export → download variance report as CSV

---

### 9. `/investments` — Investment Portfolio

**Layout:** App layout

**Key Components:**
- `<PortfolioSummaryCard>` — total portfolio spend, weighted avg ROI, active investment count
- `<BubbleChart>` — X axis = ROI (%), Y axis = total spend ($), bubble size = spend, color = L2 category
  - Hover tooltip: investment name, ROI, spend, L2
  - Click bubble → navigate to `/investments/[id]`
- `<InvestmentList>` — table below chart:
  - Columns: Name, L2 Category, Total Spend, Expected ROI, Actual ROI, Status, Signal
  - `<SignalBadge>` — on-track / at-risk / off-track
- "+ New Investment" button → `/investments/new`

**Data Sources:**
- `GET /api/investments` — all investments with ROI, spend, signals
- `GET /api/dashboard/summary` — portfolio-level aggregates

**User Interactions:**
- Click bubble or table row → `/investments/[id]`
- Filter by L2 category (pills above chart)
- Filter by status (tabs: All / Active / Completed / At Risk)
- "+ New Investment" → `/investments/new`

---

### 10. `/investments/new` — Create Investment (Multi-Step)

**Layout:** App layout, narrow centered (max-width 720px)

**Key Components:**
- `<StepIndicator steps={["Basic Info", "Benefits", "Spend Profile", "Review"]} />`

**Step 1 — Basic Info:**
- Name (text)
- Description (textarea)
- L2 Category (select from 8 L2 codes)
- Expected Start Date, End Date (date pickers)
- Owner (text or user select)

**Step 2 — Benefit Definitions:**
- `<BenefitForm>` — add 1–5 benefit definitions:
  - Benefit Type (select: Cost Reduction, Revenue Increase, Risk Mitigation, Productivity, Other)
  - Formula (text: e.g., "headcount_saved × avg_salary")
  - Target Value ($)
  - Measurement Frequency (Monthly / Quarterly / Annual)
- "+ Add Benefit" button (up to 5)
- Remove benefit (×)

**Step 3 — Spend Profile:**
- `<SpendProfileGrid>` — 12-month grid, one input per month
- Total auto-calculated below
- Paste from clipboard support (tab-separated monthly amounts)

**Step 4 — Review:**
- Summary card: name, L2, dates, owner
- Benefit table: type, formula, target
- Monthly spend bar chart (visual preview)
- "Create Investment" button

**Data Sources:**
- `POST /api/investments` — create with all nested data in one payload

**User Interactions:**
- "Next" / "Back" between steps (validates current step before advancing)
- "Create Investment" → `POST /api/investments` → redirect to `/investments/[id]`
- Step indicator is clickable (can go back to previous steps)

---

### 11. `/investments/[id]` — Investment Detail

**Layout:** App layout

**Key Components:**
- `<InvestmentHeader>` — name, L2 badge, status badge, owner, date range
- **Top Row (3 cards):**
  - Total Spend (actual vs planned), % consumed
  - Expected ROI vs Actual ROI to date
  - Investment status signal
- `<SpendTrackingChart>` — line chart: planned spend (dashed) vs actual spend (solid), monthly, area fill
- `<BenefitStatusCards>` — one card per benefit definition:
  - Benefit type, formula, target $, actual $ to date, progress bar, trend signal
- `<ROICalculation>` — expandable panel showing full ROI formula breakdown
- `<MilestoneTimeline>` — horizontal timeline (if milestones defined in future iteration)

**Data Sources:**
- `GET /api/investments/{id}` — investment detail with benefits and spend
- `GET /api/investments/{id}/actuals` — monthly actual spend
- `GET /api/investments/{id}/benefits` — benefit measurement records

**User Interactions:**
- "Edit" button → inline edit mode for name, description, owner
- "Log Actual Spend" → modal: select month, enter amount → `POST /api/investments/{id}/actuals`
- "Update Benefit" → modal: select benefit, enter measured value → `POST /api/investments/{id}/benefits`
- "Archive" → confirmation modal → archive investment

---

### 12. `/benchmarks` — Peer Comparison

**Layout:** App layout

**Key Components:**
- `<SectorSelector>` — dropdown: Technology / Healthcare / Financial Services / Industrials / Consumer / Energy / Other; also Revenue Band filter
- **Benchmark Table:**
  - Rows = L2 categories (8 rows)
  - Columns: Your %, Median %, P25 %, P75 %, vs Median (delta)
  - Color coding: green if within P25–P75, red if outside
- `<RadarChart>` — 8-axis radar: your allocation vs peer median for each L2 category
- `<RankingTable>` — anonymized company-level ranking: percentile rank for each L2 category

**Data Sources:**
- `GET /api/benchmarks?sector={sector}&revenue_band={band}` — benchmark percentiles and peer data

**User Interactions:**
- Change sector / revenue band → refetch benchmark data → update all charts
- Hover radar chart axis → tooltip with L2 label, your %, median %
- "Download Report" → PDF export of benchmark comparison (future)

---

### 13. `/settings` — Organization Settings

**Layout:** App layout

**Sections (left nav tabs within page):**

**Org Profile:**
- Company name, sector, revenue band, fiscal year start month
- Save button → `PATCH /api/organizations/{id}`

**User Management:**
- `<UserTable>` — columns: Name, Email, Role (Admin / Analyst / Viewer), Status (Active / Invited), Actions (Remove)
- "Invite User" → modal: email, role → `POST /api/organizations/{id}/members`
- Remove user → confirmation → `DELETE /api/organizations/{id}/members/{userId}`

**Custom L4 Activities:**
- Table of custom L4 codes scoped to this org
- "+ Add Activity" → modal: name, parent L3 code, description
- Edit / delete existing custom activities

**Plan Defaults:**
- Default plan type (Annual / Quarterly / Rolling)
- Default fiscal year
- Auto-classification confidence threshold (slider, default 0.85)
- Threshold determines which items are auto-approved vs flagged for review

**Data Sources:**
- `GET /api/organizations/{id}` — org profile and settings
- `PATCH /api/organizations/{id}` — update profile/defaults
- `GET /api/organizations/{id}/members` — user list
- `POST /api/organizations/{id}/members` — invite user
- `DELETE /api/organizations/{id}/members/{userId}` — remove user

**User Interactions:**
- All saves are explicit (button click), not auto-save
- Invite modal: input email → send invite email (Supabase magic link) → user appears with "Invited" status
- Confidence threshold slider — live preview of how many current line items would be auto-approved

---

## Shared Component Notes

### `<SignalBadge>` / `<SignalDot>`
- 🔴 Red: variance >10% over, confidence <0.65, ROI off-track
- 🟡 Yellow: variance 5–10%, confidence 0.65–0.84, ROI at-risk
- 🟢 Green: within threshold, confidence ≥0.85, ROI on-track

### `<ClassificationBadge>`
- RTB: `bg-blue-100 text-blue-800`
- CTB: `bg-emerald-100 text-emerald-800`
- L2/L3/L4: `bg-gray-100 text-gray-700` with code label

### `<ConfidenceBadge>`
- High (≥0.85): `bg-green-100 text-green-800` — shows "High"
- Medium (0.65–0.84): `bg-yellow-100 text-yellow-800` — shows "Med"
- Low (<0.65): `bg-red-100 text-red-800` — shows "Low"

### Loading States
- All data-fetching pages use React Suspense with skeleton loaders
- Skeleton components match the shape of the loaded content (table skeletons, card skeletons)

### Error States
- API errors → `<ErrorAlert>` with message and retry button
- 404 plans/investments → redirect to list page

### Empty States
- `/plans` with no plans → illustrated empty state + "Create your first plan" CTA
- `/investments` with no investments → illustrated empty state + "Track your first investment" CTA
