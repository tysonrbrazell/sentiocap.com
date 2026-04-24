# SentioCap API Specification

**Base URL:** `http://localhost:8000` (dev) / `https://api.sentiocap.com` (prod)  
**Format:** All requests and responses are JSON unless noted.  
**Auth:** Bearer token (JWT) in `Authorization: Bearer <token>` header, unless marked `[public]`.

---

## Auth

### POST /api/auth/login
Authenticate a user and return a JWT.

**Auth:** None (public)

**Request:**
```json
{
  "email": "tyson@msci.com",
  "password": "password123"
}
```

**Response 200:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "tyson@msci.com",
    "name": "Tyson Brazell",
    "role": "admin",
    "org_id": "uuid"
  }
}
```

**Response 401:**
```json
{ "detail": "Invalid email or password" }
```

---

### POST /api/auth/register
Register a new organization and admin user.

**Auth:** None (public)

**Request:**
```json
{
  "org_name": "MSCI Inc",
  "sector": "Financials",
  "email": "tyson@msci.com",
  "name": "Tyson Brazell",
  "password": "password123"
}
```

**Response 201:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "tyson@msci.com",
    "name": "Tyson Brazell",
    "role": "admin",
    "org_id": "uuid"
  },
  "org": {
    "id": "uuid",
    "name": "MSCI Inc"
  }
}
```

---

### GET /api/auth/me
Get current authenticated user.

**Auth:** Required

**Response 200:**
```json
{
  "id": "uuid",
  "email": "tyson@msci.com",
  "name": "Tyson Brazell",
  "role": "admin",
  "org_id": "uuid",
  "org": {
    "id": "uuid",
    "name": "MSCI Inc",
    "sector": "Financials"
  }
}
```

---

## Organizations

### GET /api/org
Get the current user's organization.

**Auth:** Required

**Response 200:**
```json
{
  "id": "uuid",
  "name": "MSCI Inc",
  "industry": "Financial Services",
  "sector": "Financials",
  "ticker": "MSCI",
  "revenue": 2500000000,
  "employees": 4900,
  "fiscal_year_end": "12-31",
  "currency": "USD"
}
```

---

### PUT /api/org
Update the current organization's settings.

**Auth:** Required (admin only)

**Request:**
```json
{
  "name": "MSCI Inc",
  "industry": "Financial Services",
  "sector": "Financials",
  "ticker": "MSCI",
  "revenue": 2500000000,
  "employees": 4900,
  "fiscal_year_end": "12-31"
}
```

**Response 200:** Updated organization object (same shape as GET /api/org)

---

## Plans

### GET /api/plans
List all plans for the current organization.

**Auth:** Required

**Query params:**
- `fiscal_year` (integer, optional) — filter by year
- `status` (string, optional) — filter by status: draft/submitted/approved/locked
- `plan_type` (string, optional)

**Response 200:**
```json
{
  "plans": [
    {
      "id": "uuid",
      "name": "FY2027 Annual Budget",
      "plan_type": "annual_budget",
      "fiscal_year": 2027,
      "status": "approved",
      "total_budget": 1500000000,
      "line_item_count": 342,
      "classified_count": 340,
      "confirmed_count": 290,
      "created_at": "2026-10-15T09:00:00Z",
      "approved_at": "2026-11-01T14:30:00Z"
    }
  ],
  "total": 3
}
```

---

### POST /api/plans
Create a new plan.

**Auth:** Required (admin or analyst)

**Request:**
```json
{
  "name": "FY2027 Annual Budget",
  "plan_type": "annual_budget",
  "fiscal_year": 2027,
  "notes": "Initial board-approved plan"
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "name": "FY2027 Annual Budget",
  "plan_type": "annual_budget",
  "fiscal_year": 2027,
  "status": "draft",
  "total_budget": null,
  "created_at": "2026-10-15T09:00:00Z"
}
```

---

### GET /api/plans/:id
Get a plan with all its line items and summary stats.

**Auth:** Required

**Response 200:**
```json
{
  "id": "uuid",
  "name": "FY2027 Annual Budget",
  "plan_type": "annual_budget",
  "fiscal_year": 2027,
  "status": "approved",
  "total_budget": 1500000000,
  "currency": "USD",
  "approved_by": { "id": "uuid", "name": "Sarah Chen" },
  "approved_at": "2026-11-01T14:30:00Z",
  "summary": {
    "rtb_total": 1340000000,
    "ctb_total": 160000000,
    "rtb_pct": 89.3,
    "ctb_pct": 10.7,
    "by_l2": {
      "RTB-OPS": 890000000,
      "RTB-MNT": 220000000,
      "RTB-CMP": 150000000,
      "RTB-SUP": 80000000,
      "CTB-GRW": 70000000,
      "CTB-TRN": 40000000,
      "CTB-EFF": 40000000,
      "CTB-INN": 10000000
    }
  },
  "line_items": [
    {
      "id": "uuid",
      "source_description": "Cloud Infrastructure - AWS",
      "source_cost_center": "CC-4500",
      "source_gl_account": "6100-100",
      "classified_l1": "RTB",
      "classified_l2": "RTB-OPS",
      "classified_l3": "TECH",
      "classified_l4": "TECH-CLOUD",
      "classification_confidence": 0.95,
      "classification_method": "ai_auto",
      "user_confirmed": true,
      "jan": 4200000, "feb": 4200000, "mar": 4300000,
      "apr": 4300000, "may": 4400000, "jun": 4400000,
      "jul": 4500000, "aug": 4500000, "sep": 4600000,
      "oct": 4600000, "nov": 4700000, "dec": 4700000,
      "annual_total": 53400000,
      "notes": null
    }
  ],
  "line_items_total": 342,
  "line_items_page": 1,
  "line_items_per_page": 50
}
```

**Query params:**
- `page` (integer, default 1)
- `per_page` (integer, default 50, max 200)
- `l2` (string, optional) — filter by L2 category
- `confirmed` (boolean, optional) — filter by confirmation status
- `min_confidence` / `max_confidence` (float, optional)

---

### PUT /api/plans/:id
Update plan metadata (name, notes, status).

**Auth:** Required (admin or analyst)

**Request:**
```json
{
  "name": "FY2027 Annual Budget v2",
  "notes": "Revised after Q4 review",
  "status": "submitted"
}
```

**Response 200:** Updated plan object

---

### POST /api/plans/:id/upload
Upload a CSV or XLSX file containing budget line items. Returns a preview before committing.

**Auth:** Required (admin or analyst)

**Content-Type:** `multipart/form-data`

**Form fields:**
- `file` — the CSV or XLSX file
- `description_column` — column name for expense description (string)
- `cost_center_column` — column name for cost center (string, optional)
- `gl_account_column` — column name for GL account (string, optional)
- `jan_column` through `dec_column` — column names for monthly amounts (string, optional)
- `annual_column` — column name for annual total if no monthly breakdown (string, optional)

**Response 200:**
```json
{
  "upload_id": "upload_uuid",
  "rows_detected": 342,
  "columns_detected": ["Cost Center", "GL Account", "Description", "Jan", "Feb", ...],
  "preview": [
    {
      "row": 1,
      "source_description": "Cloud Infrastructure - AWS",
      "source_cost_center": "CC-4500",
      "source_gl_account": "6100-100",
      "amounts": { "jan": 4200000, "feb": 4200000, ... },
      "annual_total": 53400000,
      "suggested_classification": {
        "l1": "RTB",
        "l2": "RTB-OPS",
        "l3": "TECH",
        "l4": "TECH-CLOUD",
        "confidence": 0.95
      }
    }
  ],
  "preview_count": 5
}
```

---

### POST /api/plans/:id/classify
Trigger AI classification of all unclassified (or re-classify all) line items.

**Auth:** Required (admin or analyst)

**Request:**
```json
{
  "mode": "unclassified_only",  // "unclassified_only" | "all" | "low_confidence"
  "confidence_threshold": 0.7
}
```

**Response 202:** (async — classification runs in background)
```json
{
  "job_id": "job_uuid",
  "status": "queued",
  "total_items": 342,
  "message": "Classification queued. Poll /api/jobs/job_uuid for status."
}
```

---

### PUT /api/plans/:id/line-items/:lineId
Update the classification of a single line item. Used for manual review/override.

**Auth:** Required (analyst or admin)

**Request:**
```json
{
  "classified_l1": "CTB",
  "classified_l2": "CTB-GRW",
  "classified_l3": "COM",
  "classified_l4": "COM-NEWBIZ",
  "user_confirmed": true,
  "notes": "Reclassified — this is for the new wealth segment initiative"
}
```

**Response 200:** Updated line item object

---

### POST /api/plans/:id/approve
Approve and lock a plan. Only admin can approve.

**Auth:** Required (admin only)

**Request:**
```json
{
  "notes": "Approved by board on 2026-11-01"
}
```

**Response 200:**
```json
{
  "id": "uuid",
  "status": "approved",
  "approved_by": { "id": "uuid", "name": "Tyson Brazell" },
  "approved_at": "2026-11-01T14:30:00Z"
}
```

---

## Actuals

### POST /api/actuals/upload
Upload monthly actual GL data. Auto-classifies using same AI engine.

**Auth:** Required (admin or analyst)

**Content-Type:** `multipart/form-data`

**Form fields:**
- `file` — CSV or XLSX
- `period` — period string e.g., `2027-01`
- `description_column`, `cost_center_column`, `gl_account_column`, `amount_column` — column mappings

**Response 200:**
```json
{
  "period": "2027-01",
  "rows_imported": 289,
  "rows_classified": 285,
  "rows_flagged": 4,
  "total_amount": 118500000,
  "variances_updated": true
}
```

---

### GET /api/actuals
Get actuals for a period, optionally filtered.

**Auth:** Required

**Query params:**
- `period` (string, required) — e.g., `2027-01`
- `l2` (string, optional)
- `l1` (string, optional)

**Response 200:**
```json
{
  "period": "2027-01",
  "total_amount": 118500000,
  "by_l2": {
    "RTB-OPS": 72000000,
    "RTB-MNT": 18000000,
    "RTB-CMP": 12000000,
    "RTB-SUP": 6000000,
    "CTB-GRW": 5000000,
    "CTB-TRN": 3200000,
    "CTB-EFF": 1800000,
    "CTB-INN": 500000
  },
  "line_items": [ /* same structure as plan line items */ ]
}
```

---

## Investments

### GET /api/investments
List all investments for the organization.

**Auth:** Required

**Query params:**
- `status` (string, optional) — proposed/approved/in_progress/completed/cancelled
- `l2` (string, optional) — filter by L2 category
- `plan_id` (string, optional)

**Response 200:**
```json
{
  "investments": [
    {
      "id": "uuid",
      "name": "Wealth Segment Expansion",
      "description": "Expand MSCI products into wealth management",
      "owner": "Sarah Chen",
      "l2_category": "CTB-GRW",
      "l3_domain": "COM",
      "l4_activity": "COM-NEWBIZ",
      "status": "in_progress",
      "start_date": "2025-01-01",
      "target_completion": "2026-06-30",
      "planned_total": 25000000,
      "actual_total": 18500000,
      "roi": {
        "planned_roi": 2.4,
        "current_roi": 2.1,
        "payback_months": 14,
        "composite_score": 82,
        "signal": "GREEN"
      },
      "benefit_count": 2,
      "benefits_realized_pct": 73.0
    }
  ],
  "total": 12,
  "portfolio_summary": {
    "total_planned": 160000000,
    "total_actual": 110000000,
    "deployment_rate": 68.8,
    "portfolio_roi": 1.6,
    "at_risk_count": 2
  }
}
```

---

### POST /api/investments
Create a new investment.

**Auth:** Required (admin or analyst)

**Request:**
```json
{
  "name": "Wealth Segment Expansion",
  "description": "Expand MSCI products into wealth management",
  "owner": "Sarah Chen",
  "l2_category": "CTB-GRW",
  "l3_domain": "COM",
  "l4_activity": "COM-NEWBIZ",
  "status": "proposed",
  "start_date": "2025-01-01",
  "target_completion": "2026-06-30",
  "planned_total": 25000000,
  "strategic_rating": 5,
  "plan_id": "uuid",
  "benefits": [
    {
      "benefit_type": "NEW_REVENUE",
      "description": "New ARR from wealth management clients",
      "calculation_method": "formula",
      "formula": "new_wealth_clients × average_acv",
      "target_value": 52000000,
      "measurement_start": "2025-04-01",
      "measurement_source": "CRM - new wealth segment pipeline",
      "confidence": "high"
    }
  ]
}
```

**Response 201:** Created investment object

---

### GET /api/investments/:id
Get a single investment with full detail.

**Auth:** Required

**Response 200:**
```json
{
  "id": "uuid",
  "name": "Wealth Segment Expansion",
  "description": "...",
  "owner": "Sarah Chen",
  "l2_category": "CTB-GRW",
  "l3_domain": "COM",
  "l4_activity": "COM-NEWBIZ",
  "status": "in_progress",
  "start_date": "2025-01-01",
  "target_completion": "2026-06-30",
  "planned_total": 25000000,
  "actual_total": 18500000,
  "strategic_rating": 5,
  "benefits": [
    {
      "id": "uuid",
      "benefit_type": "NEW_REVENUE",
      "description": "New ARR from wealth management clients",
      "calculation_method": "formula",
      "formula": "new_wealth_clients × average_acv",
      "target_value": 52000000,
      "actual_value": 38000000,
      "measurement_start": "2025-04-01",
      "measurement_source": "CRM",
      "confidence": "high",
      "realization_pct": 73.1
    }
  ],
  "spend_monthly": [
    { "period": "2025-01", "planned": 1800000, "actual": 1750000 },
    { "period": "2025-02", "planned": 1900000, "actual": 1850000 }
  ],
  "roi": {
    "planned_roi": 2.4,
    "current_roi": 2.1,
    "payback_months": 14,
    "npv_roi": 1.9,
    "composite_score": 82,
    "signal": "GREEN",
    "total_benefits": 41500000,
    "total_costs": 18500000
  }
}
```

---

### PUT /api/investments/:id
Update an investment (metadata, status, benefits, spend).

**Auth:** Required (admin or analyst)

**Request:** Partial update — include only fields to change
```json
{
  "status": "approved",
  "actual_total": 19200000
}
```

**Response 200:** Updated investment object

---

### GET /api/investments/:id/roi
Get detailed ROI calculation breakdown.

**Auth:** Required

**Response 200:**
```json
{
  "investment_id": "uuid",
  "name": "Wealth Segment Expansion",
  "total_costs": 18500000,
  "total_benefits": 41500000,
  "roi": 2.24,
  "roi_pct": 124.3,
  "npv_roi": 1.9,
  "payback_months": 14,
  "discount_rate": 0.10,
  "composite_score": 82,
  "signal": "GREEN",
  "benefit_breakdown": [
    {
      "benefit_type": "NEW_REVENUE",
      "target": 52000000,
      "actual": 38000000,
      "realization_pct": 73.1,
      "confidence": "high"
    }
  ],
  "spend_vs_plan": {
    "total_planned": 25000000,
    "total_actual": 18500000,
    "deployment_pct": 74.0
  }
}
```

---

## Dashboard

### GET /api/dashboard/summary
Top-level KPI summary for the dashboard.

**Auth:** Required

**Query params:**
- `plan_id` (string, optional) — which plan to use for targets
- `fiscal_year` (integer, optional) — defaults to current year

**Response 200:**
```json
{
  "org": { "name": "MSCI Inc", "sector": "Financials" },
  "fiscal_year": 2027,
  "plan_id": "uuid",
  "plan_name": "FY2027 Annual Budget",
  "total_budget": 1500000000,
  "rtb": {
    "total": 1340000000,
    "pct": 89.3,
    "peer_median_pct": 87.0,
    "signal": "YELLOW",
    "vs_plan_pct": 0.8
  },
  "ctb": {
    "total": 160000000,
    "pct": 10.7,
    "peer_median_pct": 13.0,
    "signal": "YELLOW",
    "deployment_rate": 68.8
  },
  "investments": {
    "active_count": 8,
    "at_risk_count": 2,
    "portfolio_roi": 1.6,
    "deployment_rate": 68.8
  },
  "by_l2": {
    "RTB-OPS": { "amount": 890000000, "pct": 59.3, "signal": "GREEN" },
    "RTB-MNT": { "amount": 220000000, "pct": 14.7, "signal": "YELLOW" },
    "RTB-CMP": { "amount": 150000000, "pct": 10.0, "signal": "GREEN" },
    "RTB-SUP": { "amount": 80000000,  "pct": 5.3,  "signal": "GREEN" },
    "CTB-GRW": { "amount": 70000000,  "pct": 4.7,  "signal": "GREEN" },
    "CTB-TRN": { "amount": 40000000,  "pct": 2.7,  "signal": "YELLOW" },
    "CTB-EFF": { "amount": 40000000,  "pct": 2.7,  "signal": "GREEN" },
    "CTB-INN": { "amount": 10000000,  "pct": 0.7,  "signal": "RED" }
  }
}
```

---

### GET /api/dashboard/treemap
Hierarchical expense data for treemap visualization.

**Auth:** Required

**Query params:**
- `plan_id` (string, optional)
- `fiscal_year` (integer, optional)
- `depth` (integer, default 3) — 1=L1, 2=L2, 3=L3

**Response 200:**
```json
{
  "name": "Total Budget",
  "value": 1500000000,
  "children": [
    {
      "name": "RTB",
      "value": 1340000000,
      "color": "#3B82F6",
      "children": [
        {
          "name": "RTB-OPS",
          "value": 890000000,
          "children": [
            { "name": "TECH", "value": 380000000, "pct": 25.3 },
            { "name": "PPL",  "value": 290000000, "pct": 19.3 },
            { "name": "FAC",  "value": 140000000, "pct": 9.3 },
            { "name": "COM",  "value": 80000000,  "pct": 5.3 }
          ]
        }
      ]
    },
    {
      "name": "CTB",
      "value": 160000000,
      "color": "#10B981"
    }
  ]
}
```

---

### GET /api/dashboard/variance
Monthly variance data (plan vs actuals) for a period.

**Auth:** Required

**Query params:**
- `period` (string, required) — e.g., `2027-03`
- `plan_id` (string, optional)

**Response 200:**
```json
{
  "period": "2027-03",
  "plan_id": "uuid",
  "variances": [
    {
      "l2_category": "CTB-GRW",
      "planned": 6000000,
      "actual": 4200000,
      "variance_amount": -1800000,
      "variance_pct": -30.0,
      "ytd_planned": 16000000,
      "ytd_actual": 11500000,
      "full_year_forecast": 46000000,
      "signal": "RED",
      "signal_reason": "CTB-GRW under-execution: only 66% of planned growth spend deployed in Q1."
    }
  ]
}
```

---

### GET /api/dashboard/benchmarks
Compare org's L2 allocation against sector benchmarks.

**Auth:** Required

**Query params:**
- `sector` (string, optional) — defaults to org's sector
- `year` (integer, optional) — benchmark year

**Response 200:**
```json
{
  "org": { "name": "MSCI Inc", "sector": "Financials" },
  "benchmark_year": 2025,
  "benchmark_sector": "Financials",
  "comparison": [
    {
      "l2_category": "CTB-INN",
      "org_pct": 0.7,
      "peer_p25": 0.8,
      "peer_median": 1.5,
      "peer_p75": 2.8,
      "signal": "RED",
      "insight": "Innovation spend is below the 25th percentile for Financials sector peers."
    }
  ]
}
```

---

### GET /api/dashboard/timeseries
Monthly RTB/CTB trends over time.

**Auth:** Required

**Query params:**
- `from_period` (string) — e.g., `2026-01`
- `to_period` (string) — e.g., `2027-03`
- `granularity` (string) — `monthly` | `quarterly`

**Response 200:**
```json
{
  "series": [
    {
      "period": "2027-01",
      "rtb_actual": 112000000,
      "ctb_actual": 8500000,
      "rtb_planned": 111666667,
      "ctb_planned": 13333333,
      "rtb_pct": 92.9,
      "ctb_pct": 7.1
    }
  ]
}
```

---

## Classification

### POST /api/classify
Classify a single expense description into the L1–L4 taxonomy.

**Auth:** Required

**Request:**
```json
{
  "description": "AWS EC2 Reserved Instances - Production",
  "cost_center": "CC-4500",
  "gl_account": "6100-100",
  "amount": 4200000,
  "context": {
    "industry": "Financials",
    "company_name": "MSCI Inc"
  }
}
```

**Response 200:**
```json
{
  "classified_l1": "RTB",
  "classified_l2": "RTB-OPS",
  "classified_l3": "TECH",
  "classified_l4": "TECH-CLOUD",
  "confidence": 0.96,
  "method": "ai_auto",
  "reasoning": "AWS EC2 is a cloud infrastructure service. Cost center CC-4500 maps to the Technology domain. Reserved instances are operational (RTB-OPS) as they support existing production workloads.",
  "alternatives": [
    { "l2": "CTB-EFF", "l3": "TECH", "l4": "TECH-MIG", "confidence": 0.04, "reason": "Could be migration if in transition period" }
  ]
}
```

---

### POST /api/classify/batch
Classify an array of expense items in one call (up to 100 items).

**Auth:** Required

**Request:**
```json
{
  "items": [
    {
      "id": "row_1",
      "description": "AWS EC2 Reserved Instances",
      "cost_center": "CC-4500",
      "gl_account": "6100-100",
      "amount": 4200000
    },
    {
      "id": "row_2",
      "description": "Google Ads - Q1 Campaign",
      "cost_center": "CC-3100",
      "gl_account": "7200-200",
      "amount": 150000
    }
  ],
  "context": {
    "industry": "Financials",
    "company_name": "MSCI Inc"
  }
}
```

**Response 200:**
```json
{
  "results": [
    {
      "id": "row_1",
      "classified_l1": "RTB",
      "classified_l2": "RTB-OPS",
      "classified_l3": "TECH",
      "classified_l4": "TECH-CLOUD",
      "confidence": 0.96,
      "method": "ai_auto"
    },
    {
      "id": "row_2",
      "classified_l1": "CTB",
      "classified_l2": "CTB-GRW",
      "classified_l3": "COM",
      "classified_l4": "COM-DIGMKT",
      "confidence": 0.91,
      "method": "ai_auto"
    }
  ],
  "total": 2,
  "auto_confirmed": 2,
  "needs_review": 0,
  "flagged": 0
}
```

---

## Benchmarks

### GET /api/benchmarks
Get sector benchmark data for L2 categories.

**Auth:** Required

**Query params:**
- `sector` (string, optional) — GICS sector name, e.g., `Financials`
- `year` (integer, optional) — benchmark year, defaults to latest available

**Response 200:**
```json
{
  "sector": "Financials",
  "year": 2025,
  "n_companies": 87,
  "benchmarks": [
    {
      "l2_category": "CTB-INN",
      "median_pct": 1.5,
      "p25_pct": 0.8,
      "p75_pct": 2.8,
      "mean_pct": 1.7,
      "n_companies": 87
    }
  ]
}
```

---

### GET /api/benchmarks/peer-comparison
Compare org to specific named peers.

**Auth:** Required

**Query params:**
- `tickers` (comma-separated, required) — e.g., `MSCI,FDS,SPGI`
- `year` (integer, optional)

**Response 200:**
```json
{
  "year": 2025,
  "peers": [
    {
      "ticker": "MSCI",
      "company": "MSCI Inc",
      "revenue": 2500000000,
      "ctb_pct_rev": 11.2,
      "rd": 45000000,
      "capex": 180000000,
      "sw_capitalized": 55000000,
      "return_1yr": 0.18,
      "return_3yr": 0.12
    },
    {
      "ticker": "FDS",
      "company": "FactSet Research Systems",
      "revenue": 2000000000,
      "ctb_pct_rev": 13.8,
      "rd": 62000000,
      "capex": 120000000,
      "sw_capitalized": 94000000,
      "return_1yr": 0.08,
      "return_3yr": 0.09
    }
  ],
  "correlation": {
    "ctb_pct_vs_return_1yr": 0.42,
    "ctb_pct_vs_return_3yr": 0.61,
    "insight": "Higher CTB allocation correlates positively with 3-year returns in this peer group."
  }
}
```

---

## Jobs (Background Processing)

### GET /api/jobs/:id
Poll the status of a background job (e.g., batch classification).

**Auth:** Required

**Response 200:**
```json
{
  "job_id": "uuid",
  "status": "completed",      // queued | running | completed | failed
  "progress": 100,
  "total_items": 342,
  "processed_items": 342,
  "errors": 0,
  "result_summary": {
    "auto_confirmed": 298,
    "needs_review": 38,
    "flagged": 6
  },
  "completed_at": "2026-10-15T09:05:22Z"
}
```

---

## Users (Settings)

### GET /api/users
List users in the organization.

**Auth:** Required (admin only)

**Response 200:**
```json
{
  "users": [
    { "id": "uuid", "email": "tyson@msci.com", "name": "Tyson Brazell", "role": "admin", "last_login_at": "..." }
  ]
}
```

### POST /api/users/invite
Invite a new user to the organization.

**Auth:** Required (admin only)

**Request:**
```json
{ "email": "sarah@msci.com", "name": "Sarah Chen", "role": "analyst" }
```

**Response 201:** Created user object

### PUT /api/users/:id
Update a user's role or name.

**Auth:** Required (admin only)

**Request:**
```json
{ "role": "viewer" }
```

**Response 200:** Updated user object
