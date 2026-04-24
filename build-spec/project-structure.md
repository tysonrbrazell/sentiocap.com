# SentioCap — Project Structure & Setup Guide

> Full-stack: Next.js 14 App Router (frontend) + Python FastAPI (backend) + Supabase PostgreSQL (DB) + Claude AI

---

## Directory Tree

```
sentiocap/
├── README.md
├── .gitignore
│
├── frontend/                          # Next.js 14 App Router
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── next.config.ts
│   ├── components.json                # shadcn/ui config
│   ├── .env.local                     # local env (gitignored)
│   ├── .env.example
│   │
│   ├── public/
│   │   ├── logo.svg
│   │   ├── favicon.ico
│   │   └── screenshots/
│   │       └── dashboard-preview.png
│   │
│   └── src/
│       ├── app/                       # App Router root
│       │   ├── layout.tsx             # Root layout — fonts, metadata, SupabaseProvider
│       │   ├── page.tsx               # / — Landing page
│       │   ├── globals.css
│       │   │
│       │   ├── (auth)/                # Auth route group — centered card layout
│       │   │   ├── layout.tsx
│       │   │   └── login/
│       │   │       └── page.tsx       # /login
│       │   │
│       │   └── (app)/                 # Authenticated route group — sidebar layout
│       │       ├── layout.tsx
│       │       │
│       │       ├── dashboard/
│       │       │   └── page.tsx       # /dashboard
│       │       │
│       │       ├── plans/
│       │       │   ├── page.tsx       # /plans — plan list
│       │       │   ├── new/
│       │       │   │   └── page.tsx   # /plans/new
│       │       │   └── [id]/
│       │       │       ├── page.tsx   # /plans/[id] — plan detail
│       │       │       ├── upload/
│       │       │       │   └── page.tsx  # /plans/[id]/upload
│       │       │       └── variance/
│       │       │           └── page.tsx  # /plans/[id]/variance
│       │       │
│       │       ├── investments/
│       │       │   ├── page.tsx       # /investments — investment list
│       │       │   ├── new/
│       │       │   │   └── page.tsx   # /investments/new
│       │       │   └── [id]/
│       │       │       └── page.tsx   # /investments/[id] — detail + RTB/CTB breakdown
│       │       │
│       │       ├── benchmarks/
│       │       │   └── page.tsx       # /benchmarks
│       │       │
│       │       └── settings/
│       │           └── page.tsx       # /settings
│       │
│       ├── components/
│       │   ├── ui/                    # shadcn/ui primitives (auto-generated)
│       │   │   ├── button.tsx
│       │   │   ├── card.tsx
│       │   │   ├── dialog.tsx
│       │   │   ├── dropdown-menu.tsx
│       │   │   ├── input.tsx
│       │   │   ├── label.tsx
│       │   │   ├── select.tsx
│       │   │   ├── table.tsx
│       │   │   ├── tabs.tsx
│       │   │   ├── toast.tsx
│       │   │   ├── toaster.tsx
│       │   │   └── badge.tsx
│       │   │
│       │   ├── layout/
│       │   │   ├── Sidebar.tsx        # Fixed left nav, collapsible
│       │   │   ├── Header.tsx         # Top bar: breadcrumb, org switcher, avatar
│       │   │   └── NavBar.tsx         # Landing page nav
│       │   │
│       │   ├── dashboard/
│       │   │   ├── KPICard.tsx        # Metric card with trend indicator
│       │   │   ├── RTBCTBDonut.tsx    # Portfolio-level RTB/CTB donut chart
│       │   │   ├── PlanStatusTable.tsx
│       │   │   └── RecentActivityFeed.tsx
│       │   │
│       │   ├── plans/
│       │   │   ├── PlanCard.tsx
│       │   │   ├── PlanForm.tsx       # New plan wizard
│       │   │   ├── UploadDropzone.tsx # File upload for capital plan documents
│       │   │   ├── VarianceTable.tsx  # Actual vs plan variance display
│       │   │   └── VarianceBadge.tsx
│       │   │
│       │   ├── investments/
│       │   │   ├── InvestmentTable.tsx
│       │   │   ├── InvestmentForm.tsx
│       │   │   ├── RTBCTBBreakdown.tsx  # RTB/CTB split bar + detail table
│       │   │   ├── ClassificationBadge.tsx
│       │   │   └── AIClassifyButton.tsx
│       │   │
│       │   ├── benchmarks/
│       │   │   ├── BenchmarkTable.tsx
│       │   │   ├── SectorSelector.tsx
│       │   │   └── SpendComparisonChart.tsx
│       │   │
│       │   └── shared/
│       │       ├── LoadingSpinner.tsx
│       │       ├── ErrorAlert.tsx
│       │       ├── EmptyState.tsx
│       │       ├── ConfirmDialog.tsx
│       │       └── PageHeader.tsx
│       │
│       ├── lib/
│       │   ├── supabase/
│       │   │   ├── client.ts          # Browser-side Supabase client
│       │   │   ├── server.ts          # Server-side Supabase client (cookies)
│       │   │   └── middleware.ts      # Session refresh middleware helper
│       │   ├── api.ts                 # Typed fetch wrapper for FastAPI
│       │   ├── utils.ts               # cn(), formatCurrency(), formatDate() etc.
│       │   └── constants.ts           # RTB/CTB categories, sector lists, etc.
│       │
│       ├── hooks/
│       │   ├── useSession.ts          # Supabase auth session hook
│       │   ├── usePlans.ts            # SWR/React Query wrapper for /api/plans
│       │   ├── useInvestments.ts
│       │   └── useBenchmarks.ts
│       │
│       ├── types/
│       │   ├── supabase.ts            # Auto-generated Supabase types (supabase gen types)
│       │   └── api.ts                 # Shared API response types
│       │
│       └── middleware.ts              # Next.js edge middleware — auth session guard
│
├── api/                               # Python FastAPI backend
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml
│   ├── .env                           # local env (gitignored)
│   ├── .env.example
│   ├── Dockerfile
│   ├── railway.toml                   # Railway deploy config
│   │
│   ├── main.py                        # FastAPI app entry point
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                  # Settings via pydantic-settings
│   │   ├── database.py                # Supabase client + asyncpg pool
│   │   ├── dependencies.py            # FastAPI dependency injectors (auth, db)
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # POST /api/auth/login, /register
│   │   │   ├── plans.py               # CRUD /api/plans, /api/plans/{id}/...
│   │   │   ├── investments.py         # CRUD /api/investments, classify, upload
│   │   │   ├── benchmarks.py          # GET /api/benchmarks, /api/benchmarks/compare
│   │   │   ├── ai.py                  # POST /api/ai/classify, /api/ai/classify-bulk
│   │   │   └── exports.py             # GET /api/exports/plans/{id}/csv
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # LoginRequest, RegisterRequest, TokenResponse
│   │   │   ├── plan.py                # Plan, PlanCreate, PlanUpdate, PlanSummary
│   │   │   ├── investment.py          # Investment, InvestmentCreate, ClassifyRequest
│   │   │   ├── benchmark.py           # Benchmark, CompareRequest, CompareResponse
│   │   │   └── ai.py                  # ClassificationResult, BulkClassifyRequest
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py        # JWT creation, password hashing, session mgmt
│   │   │   ├── plan_service.py        # Business logic for capital plans
│   │   │   ├── investment_service.py  # Investment CRUD, variance calc, aggregations
│   │   │   ├── benchmark_service.py   # Peer comparison queries
│   │   │   ├── ai_service.py          # Claude API integration — classify investments
│   │   │   ├── document_service.py    # PDF/Excel parse, Supabase Storage upload
│   │   │   └── export_service.py      # CSV/Excel generation
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── security.py            # bcrypt, JWT encode/decode helpers
│   │       └── formatting.py          # Currency, percentage formatters
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_plans.py
│       ├── test_investments.py
│       └── test_ai.py
│
├── supabase/                          # Supabase local config (optional)
│   ├── config.toml
│   └── migrations/
│       └── 001_initial_schema.sql     # Full schema from database-schema.sql
│
└── build-spec/                        # Project documentation (this folder)
    ├── AGENTS.md
    ├── pages.md
    ├── api-spec.md
    ├── database-schema.sql
    ├── ai-prompts.md
    └── project-structure.md           # ← this file
```

---

## Environment Variables

### Frontend (`frontend/.env.local`)

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional
NEXT_PUBLIC_DEMO_CALENDLY_URL=https://calendly.com/your-link
```

### Backend (`api/.env`)

```env
# Supabase
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Database (direct connection for migrations/heavy queries)
DATABASE_URL=postgresql://postgres:[password]@db.xxxxxxxxxxxx.supabase.co:5432/postgres

# Auth
JWT_SECRET=your-super-secret-jwt-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080   # 7 days

# Anthropic (Claude AI)
ANTHROPIC_API_KEY=sk-ant-...

# App
APP_ENV=development        # development | production
CORS_ORIGINS=http://localhost:3000,https://app.sentiocap.com

# Storage
SUPABASE_STORAGE_BUCKET=plan-documents
```

---

## Local Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- `pnpm` (recommended) or `npm`
- A [Supabase](https://supabase.com) project (free tier works)
- An [Anthropic](https://console.anthropic.com) API key

---

### 1. Clone & Bootstrap

```bash
git clone https://github.com/your-org/sentiocap.git
cd sentiocap
```

---

### 2. Database Setup (Supabase)

1. Create a new project at [supabase.com](https://supabase.com)
2. In the Supabase SQL Editor, run the full schema:
   ```bash
   # Copy contents of supabase/migrations/001_initial_schema.sql
   # Paste into Supabase SQL Editor → Run
   ```
3. Copy your project credentials from **Settings → API**:
   - `Project URL` → `SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_URL`
   - `anon public` key → `SUPABASE_ANON_KEY` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`
4. Create a Storage bucket named `plan-documents` (public: false)

---

### 3. Backend Setup

```bash
cd api

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill env vars
cp .env.example .env
# → edit .env with your Supabase + Anthropic credentials

# Run dev server
uvicorn main:app --reload --port 8000
```

API docs available at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Copy and fill env vars
cp .env.example .env.local
# → edit .env.local with your Supabase URL + anon key + API URL

# Initialize shadcn/ui (if not already done)
pnpm dlx shadcn@latest init

# Add required shadcn components
pnpm dlx shadcn@latest add button card dialog dropdown-menu input label select table tabs toast badge

# Run dev server
pnpm dev
```

Frontend available at: [http://localhost:3000](http://localhost:3000)

---

### 5. Generate Supabase TypeScript Types (Optional but Recommended)

```bash
cd frontend
pnpm dlx supabase gen types typescript \
  --project-id YOUR_PROJECT_ID \
  --schema public \
  > src/types/supabase.ts
```

---

## Key Dependencies

### Frontend (`frontend/package.json`)

```json
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "typescript": "^5.4.0",
    "@supabase/supabase-js": "^2.43.0",
    "@supabase/ssr": "^0.4.0",
    "tailwindcss": "^3.4.0",
    "@tailwindcss/typography": "^0.5.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.3.0",
    "lucide-react": "^0.378.0",
    "recharts": "^2.12.0",
    "swr": "^2.2.0",
    "react-hook-form": "^7.51.0",
    "zod": "^3.23.0",
    "@hookform/resolvers": "^3.3.0",
    "react-dropzone": "^14.2.0",
    "date-fns": "^3.6.0"
  }
}
```

### Backend (`api/requirements.txt`)

```txt
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.1
pydantic-settings==2.2.1
supabase==2.4.3
asyncpg==0.29.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
anthropic==0.26.0
openpyxl==3.1.2
PyPDF2==3.0.1
pandas==2.2.2
httpx==0.27.0
python-dotenv==1.0.1
```

---

## Deployment

### Frontend → Vercel

1. Push code to GitHub
2. Import repo at [vercel.com/new](https://vercel.com/new)
3. Set **Root Directory** to `frontend`
4. Add environment variables in Vercel dashboard:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` → your Railway API URL (e.g. `https://sentiocap-api.up.railway.app`)
5. Deploy — Vercel auto-builds on every push to `main`

**Vercel Settings:**
- Framework: Next.js (auto-detected)
- Build command: `pnpm build`
- Output directory: `.next`
- Node version: 20.x

---

### Backend → Railway

1. Create new project at [railway.app](https://railway.app)
2. Add service → **GitHub Repo** → select `sentiocap`, set root directory to `api`
3. Railway auto-detects Python. Add `railway.toml` at `api/railway.toml`:

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on-failure"
```

4. Add environment variables in Railway dashboard (all from `api/.env`)
5. Set custom domain or use Railway-generated URL (e.g. `sentiocap-api.up.railway.app`)

---

### Database → Supabase (already deployed)

Supabase manages its own hosting. No additional deploy steps needed.

**Production checklist:**
- [ ] Enable Row Level Security (RLS) on all tables (see `database-schema.sql`)
- [ ] Set up Supabase Auth email templates
- [ ] Enable `pg_cron` extension if using scheduled jobs
- [ ] Configure Storage bucket CORS for your frontend domain
- [ ] Set up database backups (Supabase Pro or Point-in-Time Recovery)

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│  User Browser                                │
│  Next.js 14 App (Vercel)                    │
│  - App Router, TypeScript, Tailwind          │
│  - shadcn/ui components                      │
│  - Supabase JS (auth session)                │
└───────────────┬─────────────────────────────┘
                │ HTTP (JWT Bearer)
                ▼
┌─────────────────────────────────────────────┐
│  FastAPI (Railway)                           │
│  - REST API — /api/*                         │
│  - Auth: JWT (python-jose)                   │
│  - AI: Claude 3.5 Sonnet (anthropic SDK)     │
│  - File parsing: PyPDF2, openpyxl            │
└───────────────┬─────────────────────────────┘
                │ supabase-py + asyncpg
                ▼
┌─────────────────────────────────────────────┐
│  Supabase (PostgreSQL)                       │
│  - Tables: orgs, users, plans,               │
│    investments, benchmarks, uploads          │
│  - Storage: plan-documents bucket            │
│  - RLS: tenant isolation per org_id          │
└─────────────────────────────────────────────┘
```

### Data Flow: AI Classification

```
User clicks "Classify with AI"
  → POST /api/ai/classify
    → FastAPI pulls investment record from Supabase
    → Builds structured prompt (see ai-prompts.md)
    → Calls Claude 3.5 Sonnet via Anthropic API
    → Parses structured JSON response
    → Updates investment record: rtb_ctb, category, subcategory, confidence, reasoning
    → Returns ClassificationResult to frontend
  → Frontend updates UI with classification + confidence badge
```

### Auth Flow

```
User submits login form
  → POST /api/auth/login (FastAPI)
    → Validates credentials against Supabase users table
    → Returns JWT (7-day expiry)
  → Frontend stores JWT in httpOnly cookie / localStorage
  → All subsequent API calls: Authorization: Bearer <token>
  → FastAPI dependency validates JWT on every protected route
  → Middleware in Next.js checks Supabase session for page-level auth
```

---

## Development Tips

### Running Both Servers Concurrently

```bash
# Terminal 1 — API
cd api && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && pnpm dev
```

Or use a tool like `concurrently` or `tmux`.

### Testing the AI Classifier Locally

```bash
curl -X POST http://localhost:8000/api/ai/classify \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"investment_id": "YOUR_INVESTMENT_UUID"}'
```

### Seeding Test Data

```bash
# Via Supabase SQL Editor — run a seed script
# Or via the API after registering a test org:
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"org_name": "Test Corp", "sector": "Financials", "email": "test@test.com", "name": "Test User", "password": "password123"}'
```

### Type Safety Across the Stack

- **DB → API:** Pydantic models in `app/models/` mirror DB schema
- **API → Frontend:** TypeScript types in `src/types/api.ts` mirror Pydantic response models
- **DB → Frontend (direct):** Auto-generated Supabase types in `src/types/supabase.ts`

---

## File Naming Conventions

| Layer | Convention | Example |
|-------|-----------|---------|
| Next.js pages | `page.tsx` in route folder | `app/(app)/plans/page.tsx` |
| Next.js components | PascalCase `.tsx` | `PlanCard.tsx` |
| Next.js hooks | camelCase `use*.ts` | `usePlans.ts` |
| FastAPI routers | snake_case `.py` | `plans.py` |
| FastAPI models | snake_case `.py` | `plan.py` |
| FastAPI services | snake_case `*_service.py` | `plan_service.py` |
| DB tables | snake_case plural | `capital_plans` |
| DB columns | snake_case | `rtb_ctb_split` |

---

*This file is part of the SentioCap build spec. See also: `pages.md`, `api-spec.md`, `database-schema.sql`, `ai-prompts.md`.*
