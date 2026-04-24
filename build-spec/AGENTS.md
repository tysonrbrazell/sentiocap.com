# SentioCap — Cursor Build Instructions

## Project Overview

**SentioCap** is an AI-powered expense intelligence platform that helps companies understand, classify, and optimize their spending through the Investment Intent Taxonomy (RTB vs CTB). 

Core value props:
1. **AI Classification** — Upload a GL export or budget spreadsheet; AI auto-classifies every line into L1–L4 taxonomy (RTB/CTB → Category → Domain → Activity)
2. **Planning Layer** — Upload annual operating plans, track actuals vs plan monthly, get variance signals
3. **Investment Analyzer** — Define CTB investments, model benefits, track ROI across the portfolio
4. **Benchmarking** — Compare your RTB/CTB split against S&P 500 peers by sector

The taxonomy is a 5-level hierarchy:
- **L1**: RTB (Run the Business) vs CTB (Change the Business)
- **L2**: 8 categories — RTB-OPS, RTB-MNT, RTB-CMP, RTB-SUP, CTB-GRW, CTB-TRN, CTB-EFF, CTB-INN
- **L3**: 8 functional domains — TECH, PPL, COM, PRD, FAC, FIN, CRP, DAT
- **L4**: 89 standard activity types (e.g., TECH-CLOUD, PPL-COMP, COM-DIGMKT)
- **L5**: Raw GL line items (company-specific)

---

## Tech Stack

### Frontend
- **Next.js 14+** with App Router (not Pages Router)
- **TypeScript** — strict mode always on
- **Tailwind CSS** — utility-first, no component CSS files
- **shadcn/ui** — component library (Radix-based, Tailwind-styled)
- **Recharts** — for charts (treemap, donut, bar, line)
- **React Hook Form + Zod** — for form handling and validation
- **TanStack Query** — for server state, caching, and mutations

### Backend
- **Python 3.11+** with **FastAPI** — API layer
- **Pydantic v2** — request/response validation
- **SQLAlchemy 2.0** — ORM (async via asyncpg)
- **Alembic** — database migrations

### Database
- **PostgreSQL 15+** via **Supabase** (managed Postgres + Auth + Storage)
- Use Supabase client in frontend for auth; use direct Postgres in API

### AI
- **Anthropic Claude API** (claude-3-5-sonnet) — expense classification engine
- Model prompts live in `api/services/classification/prompts.py`

### File Processing
- **pandas** — CSV/XLSX parsing in the API
- **openpyxl** — Excel file support

---

## Directory Structure

```
sentiocap/
├── frontend/                    # Next.js 14 app
│   ├── app/                     # App Router — all pages here
│   │   ├── (auth)/              # Auth routes (login, register)
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── (app)/               # Protected app routes
│   │   │   ├── layout.tsx       # App shell with sidebar nav
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── plans/
│   │   │   │   ├── page.tsx     # Plans list
│   │   │   │   ├── new/page.tsx
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx         # Plan detail + line items
│   │   │   │       ├── upload/page.tsx
│   │   │   │       └── variance/page.tsx
│   │   │   ├── investments/
│   │   │   │   ├── page.tsx
│   │   │   │   ├── new/page.tsx
│   │   │   │   └── [id]/page.tsx
│   │   │   ├── benchmarks/page.tsx
│   │   │   └── settings/page.tsx
│   │   ├── layout.tsx           # Root layout
│   │   └── page.tsx             # Landing page (/)
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components (Button, Card, etc.)
│   │   ├── charts/              # Chart wrappers
│   │   │   ├── RtbCtbDonut.tsx
│   │   │   ├── ExpenseTreemap.tsx
│   │   │   ├── VarianceWaterfall.tsx
│   │   │   ├── InvestmentBubble.tsx
│   │   │   └── TimeseriesBar.tsx
│   │   ├── dashboard/
│   │   │   ├── KpiTile.tsx
│   │   │   ├── SignalBadge.tsx
│   │   │   └── CategoryCard.tsx
│   │   ├── plans/
│   │   │   ├── LineItemTable.tsx
│   │   │   ├── ClassificationBadge.tsx
│   │   │   ├── UploadDropzone.tsx
│   │   │   └── VarianceTable.tsx
│   │   ├── investments/
│   │   │   ├── InvestmentCard.tsx
│   │   │   ├── BenefitForm.tsx
│   │   │   └── RoiSummary.tsx
│   │   └── layout/
│   │       ├── Sidebar.tsx
│   │       ├── TopNav.tsx
│   │       └── PageHeader.tsx
│   ├── lib/
│   │   ├── api.ts               # API client (typed fetch wrapper)
│   │   ├── types.ts             # Shared TypeScript types
│   │   ├── utils.ts             # Utility functions (cn, formatCurrency, etc.)
│   │   └── constants.ts         # Taxonomy enums, signal colors, etc.
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── usePlans.ts
│   │   └── useInvestments.ts
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── next.config.ts
│
├── api/                         # Python FastAPI
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings (env vars via pydantic-settings)
│   ├── database.py              # SQLAlchemy async engine + session
│   ├── routers/
│   │   ├── auth.py
│   │   ├── org.py
│   │   ├── plans.py
│   │   ├── actuals.py
│   │   ├── investments.py
│   │   ├── dashboard.py
│   │   ├── classify.py
│   │   └── benchmarks.py
│   ├── models/
│   │   ├── db.py                # SQLAlchemy ORM models
│   │   └── schemas.py           # Pydantic request/response schemas
│   ├── services/
│   │   ├── classification/
│   │   │   ├── __init__.py
│   │   │   ├── classifier.py    # Main classification logic
│   │   │   ├── prompts.py       # Claude prompts
│   │   │   └── rules.py         # Rule-based pre-classification
│   │   ├── benchmarks/
│   │   │   ├── __init__.py
│   │   │   └── calculator.py    # Benchmark calculations
│   │   └── analysis/
│   │       ├── __init__.py
│   │       ├── variance.py      # Variance + signal generation
│   │       ├── roi.py           # Investment ROI engine
│   │       └── reforecast.py    # Full-year projection
│   ├── db/
│   │   └── queries.py           # Complex SQL queries
│   └── requirements.txt
│
├── data/
│   ├── sp500/                   # S&P 500 benchmark dataset
│   │   ├── sp500_data.csv
│   │   └── load_sp500.py
│   └── xbrl/                   # XBRL parsing scripts
│       └── parse_xbrl.py
│
├── supabase/
│   └── migrations/              # SQL migration files
│       └── 001_initial_schema.sql
│
├── build-spec/                  # This directory — reference docs for Cursor
│   ├── AGENTS.md                # ← You are here
│   ├── database-schema.sql
│   ├── api-spec.md
│   ├── pages.md
│   ├── ai-prompts.md
│   └── project-structure.md
│
└── docker-compose.yml           # Local dev: postgres + api
```

---

## Key Conventions

### TypeScript
- `"strict": true` in tsconfig always
- No `any` types — use `unknown` + type guards
- All API responses have typed interfaces in `lib/types.ts`
- Use `zod` for runtime validation at form boundaries

### Styling
- Tailwind only — no CSS modules, no styled-components
- Use `cn()` utility (from `lib/utils.ts`) for conditional class merging
- shadcn/ui components live in `components/ui/` — don't modify, extend with wrappers
- Color palette: neutral grays + brand blue (`blue-600`) + signal colors (green-500, yellow-500, red-500)

### shadcn/ui Usage
- Install components via `npx shadcn-ui@latest add <component>`
- Prefer shadcn components over custom HTML elements
- Key components: Card, Table, Badge, Button, Dialog, Select, Tabs, Progress

### Taxonomy Constants
Define all taxonomy enums in `lib/constants.ts`:
```typescript
export const L1_TYPES = ['RTB', 'CTB'] as const
export const L2_CATEGORIES = ['RTB-OPS', 'RTB-MNT', 'RTB-CMP', 'RTB-SUP', 'CTB-GRW', 'CTB-TRN', 'CTB-EFF', 'CTB-INN'] as const
export const L3_DOMAINS = ['TECH', 'PPL', 'COM', 'PRD', 'FAC', 'FIN', 'CRP', 'DAT'] as const
export const SIGNALS = ['GREEN', 'YELLOW', 'RED'] as const
export type Signal = typeof SIGNALS[number]
```

### API Client
All API calls go through `lib/api.ts`. Never use raw `fetch` in components.
```typescript
// lib/api.ts pattern
export const api = {
  plans: {
    list: () => get<Plan[]>('/api/plans'),
    create: (data: CreatePlanInput) => post<Plan>('/api/plans', data),
    get: (id: string) => get<Plan>(`/api/plans/${id}`),
  },
  // ...
}
```

### Python / FastAPI
- Async everywhere (`async def` for all route handlers)
- Pydantic v2 models for all request/response schemas
- Use dependency injection for auth (`Depends(get_current_user)`)
- Database sessions via `Depends(get_db)` — never create sessions manually
- Return consistent error responses: `{"detail": "error message"}` with proper HTTP status codes

### File Processing
- CSV/XLSX uploads go to `/api/plans/:id/upload`
- Server processes file, returns preview (first 20 rows with suggested classifications)
- Classification is triggered separately via `/api/plans/:id/classify`

---

## Running Locally

### Prerequisites
- Node.js 20+
- Python 3.11+
- Docker (for PostgreSQL)
- Supabase account (or local Supabase CLI)

### Setup

```bash
# 1. Start local PostgreSQL
docker-compose up -d postgres

# 2. API setup
cd api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in ANTHROPIC_API_KEY, DATABASE_URL, JWT_SECRET
alembic upgrade head
uvicorn main:app --reload --port 8000

# 3. Frontend setup
cd frontend
npm install
cp .env.local.example .env.local  # fill in NEXT_PUBLIC_API_URL
npm run dev
```

### Environment Variables

**api/.env:**
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/sentiocap
JWT_SECRET=your-secret-key
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=...
```

**frontend/.env.local:**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

---

## Key Files to Reference

When building a new feature, read these files first:

| File | Purpose |
|------|---------|
| `build-spec/database-schema.sql` | Authoritative DB schema — all tables and fields |
| `build-spec/api-spec.md` | All API endpoints with request/response shapes |
| `build-spec/pages.md` | Each frontend page's layout, components, and data sources |
| `build-spec/ai-prompts.md` | The actual Claude prompts for classification |
| `lib/types.ts` | Shared TypeScript types matching DB schema |
| `lib/constants.ts` | Taxonomy enums (L1-L4 codes, signal colors) |

---

## Important Domain Concepts

### RTB vs CTB
- **RTB** = Run the Business (maintaining current revenue)
- **CTB** = Change the Business (investing in future value)
- The L1 split (RTB% vs CTB%) is THE primary metric — everything else is detail

### Signal Colors
- 🟢 **GREEN** = within ±5% of plan or top quartile vs peers
- 🟡 **YELLOW** = 5-15% variance or middle quartiles
- 🔴 **RED** = >15% variance or bottom quartile

### CTB Under-Execution
A critical insight: companies often budget CTB but fail to deploy it. The gap between "planned CTB" and "actual CTB deployed" is a key metric to surface prominently. RED signal when CTB >15% under plan.

### Investment Cards
Every CTB dollar should trace to a named investment with:
- A benefit hypothesis (what value will this create?)
- A measurement method (how will we know it worked?)
- An ROI calculation (was it worth it?)

### Classification Confidence
- **>90%** → auto-confirmed (user can override)
- **70–90%** → suggested (user should review, shown in yellow)
- **<70%** → flagged for manual classification (user must select)
