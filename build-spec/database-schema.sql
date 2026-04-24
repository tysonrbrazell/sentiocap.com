-- =============================================================================
-- SentioCap PostgreSQL Schema
-- Version: 1.0 (MVP)
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE user_role AS ENUM ('admin', 'analyst', 'viewer');
CREATE TYPE plan_type AS ENUM ('annual_budget', 'reforecast', 'scenario');
CREATE TYPE plan_status AS ENUM ('draft', 'submitted', 'approved', 'locked');
CREATE TYPE l1_type AS ENUM ('RTB', 'CTB');
CREATE TYPE l2_category AS ENUM (
  'RTB-OPS', 'RTB-MNT', 'RTB-CMP', 'RTB-SUP',
  'CTB-GRW', 'CTB-TRN', 'CTB-EFF', 'CTB-INN'
);
CREATE TYPE l3_domain AS ENUM ('TECH', 'PPL', 'COM', 'PRD', 'FAC', 'FIN', 'CRP', 'DAT');
CREATE TYPE classification_method AS ENUM ('ai_auto', 'user_manual', 'rule_based');
CREATE TYPE investment_status AS ENUM ('proposed', 'approved', 'in_progress', 'completed', 'cancelled');
CREATE TYPE benefit_calc_method AS ENUM ('formula', 'milestone', 'proxy');
CREATE TYPE confidence_level AS ENUM ('high', 'medium', 'low');
CREATE TYPE variance_signal AS ENUM ('GREEN', 'YELLOW', 'RED');

-- =============================================================================
-- ORGANIZATIONS
-- =============================================================================

CREATE TABLE organizations (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name            VARCHAR(255) NOT NULL,
  industry        VARCHAR(100),                    -- e.g., 'Financial Services'
  sector          VARCHAR(100),                    -- S&P GICS sector, e.g., 'Financials'
  ticker          VARCHAR(20),                     -- Stock ticker if public
  revenue         NUMERIC(20, 2),                  -- Annual revenue in USD
  employees       INTEGER,                         -- FTE headcount
  fiscal_year_end VARCHAR(5),                      -- e.g., '12-31' or '06-30'
  currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_organizations_sector ON organizations(sector);

-- =============================================================================
-- USERS
-- =============================================================================

CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email           VARCHAR(255) NOT NULL UNIQUE,
  name            VARCHAR(255) NOT NULL,
  role            user_role NOT NULL DEFAULT 'analyst',
  password_hash   VARCHAR(255),                    -- NULL if using Supabase Auth
  supabase_uid    UUID UNIQUE,                     -- Supabase Auth user ID
  last_login_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_email ON users(email);

-- =============================================================================
-- PLANS
-- =============================================================================

CREATE TABLE plans (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name            VARCHAR(255) NOT NULL,           -- e.g., 'FY2027 Annual Budget'
  plan_type       plan_type NOT NULL DEFAULT 'annual_budget',
  fiscal_year     INTEGER NOT NULL,                -- e.g., 2027
  status          plan_status NOT NULL DEFAULT 'draft',
  total_budget    NUMERIC(20, 2),                  -- Computed from line items
  currency        VARCHAR(3) NOT NULL DEFAULT 'USD',
  created_by      UUID REFERENCES users(id),
  approved_by     UUID REFERENCES users(id),
  approved_at     TIMESTAMPTZ,
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plans_org_id ON plans(org_id);
CREATE INDEX idx_plans_fiscal_year ON plans(fiscal_year);
CREATE INDEX idx_plans_status ON plans(status);

-- =============================================================================
-- PLAN LINE ITEMS
-- =============================================================================

CREATE TABLE plan_line_items (
  id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  plan_id                  UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,

  -- Source data (from uploaded spreadsheet / GL)
  source_description       TEXT NOT NULL,          -- Original GL description
  source_cost_center       VARCHAR(100),           -- Cost center code
  source_gl_account        VARCHAR(100),           -- GL account code
  source_row_number        INTEGER,                -- Row number in original upload

  -- Classification (L1-L4)
  classified_l1            l1_type,
  classified_l2            l2_category,
  classified_l3            l3_domain,
  classified_l4            VARCHAR(50),            -- e.g., 'TECH-CLOUD', 'PPL-COMP'
  classification_confidence FLOAT CHECK (classification_confidence BETWEEN 0 AND 1),
  classification_method    classification_method NOT NULL DEFAULT 'ai_auto',
  user_confirmed           BOOLEAN NOT NULL DEFAULT FALSE,
  classified_at            TIMESTAMPTZ,
  classified_by            UUID REFERENCES users(id),

  -- Monthly amounts (Jan-Dec) in plan currency
  jan                      NUMERIC(18, 2) DEFAULT 0,
  feb                      NUMERIC(18, 2) DEFAULT 0,
  mar                      NUMERIC(18, 2) DEFAULT 0,
  apr                      NUMERIC(18, 2) DEFAULT 0,
  may                      NUMERIC(18, 2) DEFAULT 0,
  jun                      NUMERIC(18, 2) DEFAULT 0,
  jul                      NUMERIC(18, 2) DEFAULT 0,
  aug                      NUMERIC(18, 2) DEFAULT 0,
  sep                      NUMERIC(18, 2) DEFAULT 0,
  oct                      NUMERIC(18, 2) DEFAULT 0,
  nov                      NUMERIC(18, 2) DEFAULT 0,
  dec                      NUMERIC(18, 2) DEFAULT 0,

  -- Computed total (trigger-maintained or application-maintained)
  annual_total             NUMERIC(18, 2) GENERATED ALWAYS AS (
    COALESCE(jan,0) + COALESCE(feb,0) + COALESCE(mar,0) + COALESCE(apr,0) +
    COALESCE(may,0) + COALESCE(jun,0) + COALESCE(jul,0) + COALESCE(aug,0) +
    COALESCE(sep,0) + COALESCE(oct,0) + COALESCE(nov,0) + COALESCE(dec,0)
  ) STORED,

  notes                    TEXT,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_plan_line_items_plan_id ON plan_line_items(plan_id);
CREATE INDEX idx_plan_line_items_l1 ON plan_line_items(classified_l1);
CREATE INDEX idx_plan_line_items_l2 ON plan_line_items(classified_l2);
CREATE INDEX idx_plan_line_items_l3 ON plan_line_items(classified_l3);
CREATE INDEX idx_plan_line_items_confirmed ON plan_line_items(user_confirmed);
CREATE INDEX idx_plan_line_items_confidence ON plan_line_items(classification_confidence);

-- =============================================================================
-- ACTUALS
-- =============================================================================
-- Monthly actual GL data uploaded by the org after each period close.

CREATE TABLE actuals (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id                UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period                VARCHAR(7) NOT NULL,        -- 'YYYY-MM' e.g., '2027-01'

  -- Source data
  source_description    TEXT NOT NULL,
  source_cost_center    VARCHAR(100),
  source_gl_account     VARCHAR(100),

  -- Classification (same taxonomy as plan_line_items)
  classified_l1         l1_type,
  classified_l2         l2_category,
  classified_l3         l3_domain,
  classified_l4         VARCHAR(50),
  classification_confidence FLOAT CHECK (classification_confidence BETWEEN 0 AND 1),
  classification_method classification_method NOT NULL DEFAULT 'ai_auto',
  user_confirmed        BOOLEAN NOT NULL DEFAULT FALSE,

  -- Amount
  amount                NUMERIC(18, 2) NOT NULL DEFAULT 0,

  uploaded_by           UUID REFERENCES users(id),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_actuals_org_id ON actuals(org_id);
CREATE INDEX idx_actuals_period ON actuals(period);
CREATE INDEX idx_actuals_org_period ON actuals(org_id, period);
CREATE INDEX idx_actuals_l2 ON actuals(classified_l2);

-- =============================================================================
-- INVESTMENTS
-- =============================================================================
-- Individual CTB investment cards — each CTB spend should map to an investment.

CREATE TABLE investments (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id            UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  plan_id           UUID REFERENCES plans(id),     -- Optional: which plan does this belong to?
  name              VARCHAR(255) NOT NULL,
  description       TEXT,
  owner             VARCHAR(255),                  -- Name/email of accountable person
  l2_category       l2_category,                   -- Should be CTB-*
  l3_domain         l3_domain,
  l4_activity       VARCHAR(50),                   -- e.g., 'COM-NEWBIZ'
  status            investment_status NOT NULL DEFAULT 'proposed',
  start_date        DATE,
  target_completion DATE,
  planned_total     NUMERIC(18, 2),                -- Total planned spend (all years)
  actual_total      NUMERIC(18, 2) DEFAULT 0,      -- Actual spend to date
  strategic_rating  INTEGER CHECK (strategic_rating BETWEEN 1 AND 5),  -- User-rated strategic importance
  notes             TEXT,
  created_by        UUID REFERENCES users(id),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_investments_org_id ON investments(org_id);
CREATE INDEX idx_investments_plan_id ON investments(plan_id);
CREATE INDEX idx_investments_status ON investments(status);
CREATE INDEX idx_investments_l2 ON investments(l2_category);

-- =============================================================================
-- INVESTMENT BENEFITS
-- =============================================================================
-- Each investment declares expected benefits with measurement methods.

CREATE TABLE investment_benefits (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  investment_id         UUID NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
  benefit_type          VARCHAR(50) NOT NULL,       -- e.g., 'NEW_REVENUE', 'COST_REDUCTION'
  description           TEXT NOT NULL,
  calculation_method    benefit_calc_method NOT NULL DEFAULT 'formula',
  formula               TEXT,                       -- e.g., 'new_clients × average_acv'
  target_value          NUMERIC(18, 2),             -- What success looks like ($)
  actual_value          NUMERIC(18, 2),             -- Measured value to date ($)
  measurement_start     DATE,                       -- When to begin measuring
  measurement_source    TEXT,                       -- Where data comes from
  confidence            confidence_level NOT NULL DEFAULT 'medium',
  notes                 TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_investment_benefits_investment_id ON investment_benefits(investment_id);
CREATE INDEX idx_investment_benefits_type ON investment_benefits(benefit_type);

-- =============================================================================
-- INVESTMENT SPEND MONTHLY
-- =============================================================================
-- Monthly planned vs actual spend per investment.

CREATE TABLE investment_spend_monthly (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  investment_id  UUID NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
  period         VARCHAR(7) NOT NULL,               -- 'YYYY-MM'
  planned        NUMERIC(18, 2) DEFAULT 0,
  actual         NUMERIC(18, 2) DEFAULT 0,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (investment_id, period)
);

CREATE INDEX idx_investment_spend_investment_id ON investment_spend_monthly(investment_id);
CREATE INDEX idx_investment_spend_period ON investment_spend_monthly(period);

-- =============================================================================
-- VARIANCES
-- =============================================================================
-- Pre-computed monthly variance records (plan vs actuals) per L2 category.
-- Populated by the backend after each actuals upload.

CREATE TABLE variances (
  id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  plan_id              UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
  org_id               UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period               VARCHAR(7) NOT NULL,         -- 'YYYY-MM'
  l2_category          l2_category NOT NULL,
  planned              NUMERIC(18, 2) NOT NULL DEFAULT 0,
  actual               NUMERIC(18, 2) NOT NULL DEFAULT 0,
  variance_amount      NUMERIC(18, 2) GENERATED ALWAYS AS (actual - planned) STORED,
  variance_pct         NUMERIC(8, 4),               -- (actual - planned) / planned × 100
  ytd_planned          NUMERIC(18, 2),
  ytd_actual           NUMERIC(18, 2),
  full_year_forecast   NUMERIC(18, 2),              -- Extrapolated full-year at current run rate
  signal               variance_signal NOT NULL DEFAULT 'GREEN',
  signal_reason        TEXT,                        -- AI-generated explanation
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (plan_id, period, l2_category)
);

CREATE INDEX idx_variances_plan_id ON variances(plan_id);
CREATE INDEX idx_variances_org_id ON variances(org_id);
CREATE INDEX idx_variances_period ON variances(period);
CREATE INDEX idx_variances_signal ON variances(signal);

-- =============================================================================
-- BENCHMARKS
-- =============================================================================
-- Industry benchmark data by sector and L2 category (% of revenue).
-- Seeded from S&P 500 XBRL analysis.

CREATE TABLE benchmarks (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  sector        VARCHAR(100) NOT NULL,              -- GICS sector name
  year          INTEGER NOT NULL,
  l2_category   l2_category NOT NULL,
  median_pct    NUMERIC(8, 4),                      -- Median % of revenue
  p25_pct       NUMERIC(8, 4),                      -- 25th percentile
  p75_pct       NUMERIC(8, 4),                      -- 75th percentile
  mean_pct      NUMERIC(8, 4),                      -- Mean % of revenue
  n_companies   INTEGER,                            -- Sample size
  source        VARCHAR(255),                       -- Data source note
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (sector, year, l2_category)
);

CREATE INDEX idx_benchmarks_sector ON benchmarks(sector);
CREATE INDEX idx_benchmarks_year ON benchmarks(year);
CREATE INDEX idx_benchmarks_l2 ON benchmarks(l2_category);

-- =============================================================================
-- S&P 500 DATA
-- =============================================================================
-- Raw S&P 500 company data used for peer comparison and benchmark calculation.

CREATE TABLE sp500_data (
  id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  ticker           VARCHAR(20) NOT NULL,
  company          VARCHAR(255),
  sector           VARCHAR(100),
  year             INTEGER NOT NULL,
  revenue          NUMERIC(20, 2),                  -- Total revenue
  rd               NUMERIC(20, 2),                  -- R&D expense (ASC 730)
  capex            NUMERIC(20, 2),                  -- Capital expenditure
  sw_capitalized   NUMERIC(20, 2),                  -- Capitalized software (ASC 350-40)
  operating_income NUMERIC(20, 2),
  ctb_proxy        NUMERIC(20, 2),                  -- Estimated CTB (R&D + CapEx + SW)
  ctb_pct_rev      NUMERIC(8, 4),                   -- ctb_proxy / revenue × 100
  price            NUMERIC(12, 4),                  -- Year-end stock price
  return_1yr       NUMERIC(8, 4),                   -- 1-year total return %
  return_3yr       NUMERIC(8, 4),                   -- 3-year annualized return %
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (ticker, year)
);

CREATE INDEX idx_sp500_ticker ON sp500_data(ticker);
CREATE INDEX idx_sp500_sector ON sp500_data(sector);
CREATE INDEX idx_sp500_year ON sp500_data(year);
CREATE INDEX idx_sp500_ctb_pct ON sp500_data(ctb_pct_rev);

-- =============================================================================
-- UPDATED_AT TRIGGERS
-- =============================================================================
-- Auto-update updated_at on all tables.

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'organizations', 'users', 'plans', 'plan_line_items',
    'actuals', 'investments', 'investment_benefits',
    'investment_spend_monthly', 'variances', 'benchmarks', 'sp500_data'
  ]
  LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();',
      t, t
    );
  END LOOP;
END;
$$;

-- =============================================================================
-- ROW LEVEL SECURITY (for Supabase)
-- =============================================================================
-- Enable RLS on all tables so org data is isolated.

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_line_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE actuals ENABLE ROW LEVEL SECURITY;
ALTER TABLE investments ENABLE ROW LEVEL SECURITY;
ALTER TABLE investment_benefits ENABLE ROW LEVEL SECURITY;
ALTER TABLE investment_spend_monthly ENABLE ROW LEVEL SECURITY;
ALTER TABLE variances ENABLE ROW LEVEL SECURITY;

-- Users can only see their own org's data
-- (Service role bypasses RLS; use service role in API backend)

CREATE POLICY "org_isolation_organizations" ON organizations
  FOR ALL USING (id IN (SELECT org_id FROM users WHERE supabase_uid = auth.uid()));

CREATE POLICY "org_isolation_plans" ON plans
  FOR ALL USING (org_id IN (SELECT org_id FROM users WHERE supabase_uid = auth.uid()));

CREATE POLICY "org_isolation_actuals" ON actuals
  FOR ALL USING (org_id IN (SELECT org_id FROM users WHERE supabase_uid = auth.uid()));

CREATE POLICY "org_isolation_investments" ON investments
  FOR ALL USING (org_id IN (SELECT org_id FROM users WHERE supabase_uid = auth.uid()));

-- Benchmarks and sp500_data are public (no RLS restriction)
CREATE POLICY "benchmarks_public_read" ON benchmarks
  FOR SELECT USING (true);

-- =============================================================================
-- SEED DATA — L4 ACTIVITY REFERENCE TABLE
-- =============================================================================
-- Optional: a lookup table for the 89 standard L4 activity codes.

CREATE TABLE taxonomy_l4 (
  code             VARCHAR(30) PRIMARY KEY,         -- e.g., 'TECH-CLOUD'
  name             VARCHAR(100) NOT NULL,
  l3_domain        l3_domain NOT NULL,
  default_l2       l2_category NOT NULL,
  description      TEXT,
  is_custom        BOOLEAN NOT NULL DEFAULT FALSE,
  comparable_std   VARCHAR(30) REFERENCES taxonomy_l4(code),  -- for custom activities
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert standard L4 codes (sample — full list in seed file)
INSERT INTO taxonomy_l4 (code, name, l3_domain, default_l2, description) VALUES
-- TECH
('TECH-INFRA',   'Infrastructure & Hosting',          'TECH', 'RTB-OPS', 'On-prem, colocation infrastructure'),
('TECH-CLOUD',   'Cloud Services',                    'TECH', 'RTB-OPS', 'IaaS, PaaS cloud spending'),
('TECH-SAAS',    'SaaS Licenses & Subscriptions',     'TECH', 'RTB-OPS', 'Third-party SaaS products'),
('TECH-APPDEV',  'Application Development (new)',      'TECH', 'CTB-TRN', 'Net-new application development'),
('TECH-APPMNT',  'Application Maintenance & Support',  'TECH', 'RTB-MNT', 'Maintaining existing applications'),
('TECH-DATA',    'Data Platform & Engineering',        'TECH', 'RTB-OPS', 'Data infrastructure and pipelines'),
('TECH-AI',      'AI/ML Development & Operations',    'TECH', 'CTB-INN', 'AI and machine learning projects'),
('TECH-SEC',     'Cybersecurity & InfoSec',           'TECH', 'RTB-CMP', 'Security controls and compliance'),
('TECH-NET',     'Network & Telecommunications',       'TECH', 'RTB-OPS', 'Networking infrastructure'),
('TECH-EUC',     'End-User Computing',                'TECH', 'RTB-SUP', 'Laptops, phones, desk software'),
('TECH-ITSM',    'IT Service Management',             'TECH', 'RTB-SUP', 'Help desk, ITSM tools'),
('TECH-DEVOPS',  'DevOps & Site Reliability',         'TECH', 'RTB-OPS', 'DevOps tooling and SRE'),
('TECH-ARCH',    'Enterprise Architecture',            'TECH', 'CTB-EFF', 'Architecture standards and governance'),
('TECH-MIG',     'Migration & Modernization',          'TECH', 'CTB-EFF', 'Legacy system migration'),
('TECH-INT',     'System Integration',                'TECH', 'RTB-OPS', 'Integration middleware and APIs'),
-- PPL
('PPL-COMP',     'Base Compensation',                  'PPL',  'RTB-SUP', 'Salaries and wages'),
('PPL-VAR',      'Variable Compensation',              'PPL',  'RTB-SUP', 'Bonus, commission, equity'),
('PPL-BEN',      'Benefits',                           'PPL',  'RTB-SUP', 'Health, retirement, equity benefits'),
('PPL-HIRE',     'Recruiting & Talent Acquisition',    'PPL',  'CTB-GRW', 'Recruiting fees and sourcing'),
('PPL-TRAIN',    'Training & Development',             'PPL',  'CTB-EFF', 'L&D programs and conferences'),
('PPL-CONT',     'Contractors & Temp Staff',           'PPL',  'RTB-OPS', 'External contractors'),
('PPL-REORG',    'Restructuring & Severance',          'PPL',  'CTB-EFF', 'Reorg costs and severance'),
('PPL-DEI',      'DEI Programs',                       'PPL',  'CTB-GRW', 'Diversity and inclusion initiatives'),
-- COM
('COM-DIGMKT',   'Digital Marketing',                  'COM',  'CTB-GRW', 'SEO, SEM, paid social'),
('COM-BRAND',    'Brand Marketing & Awareness',        'COM',  'CTB-GRW', 'Brand campaigns'),
('COM-EVENT',    'Events & Conferences',               'COM',  'CTB-GRW', 'Trade shows, company events'),
('COM-SALES',    'Sales Operations & Enablement',      'COM',  'RTB-OPS', 'Sales ops, CRM, tools'),
('COM-ACCTMGT',  'Account Management',                 'COM',  'RTB-OPS', 'Existing client management'),
('COM-NEWBIZ',   'New Business Development',           'COM',  'CTB-GRW', 'New logo acquisition'),
('COM-CUST',     'Customer Success & Retention',       'COM',  'RTB-OPS', 'CS team and retention'),
('COM-PARTNER',  'Partnership & Channel Development',  'COM',  'CTB-GRW', 'Partner programs'),
('COM-RESEARCH', 'Market Research',                    'COM',  'CTB-INN', 'Market and competitive intelligence'),
-- PRD
('PRD-RD',       'Research & Development',             'PRD',  'CTB-INN', 'Pure R&D, exploratory research'),
('PRD-ENG',      'Core Product Engineering',           'PRD',  'CTB-GRW', 'Core product feature development'),
('PRD-PM',       'Product Management',                 'PRD',  'RTB-OPS', 'Product management function'),
('PRD-DESIGN',   'Product Design (UX/UI)',             'PRD',  'CTB-GRW', 'User experience design'),
('PRD-QA',       'Quality Assurance & Testing',        'PRD',  'RTB-OPS', 'QA and testing'),
('PRD-PROTO',    'Prototyping & Proof of Concept',     'PRD',  'CTB-INN', 'PoC and prototype work'),
('PRD-LAUNCH',   'New Product Launch',                 'PRD',  'CTB-TRN', 'Go-to-market for new products'),
('PRD-ENHANCE',  'Product Enhancement & Feature Dev',  'PRD',  'CTB-GRW', 'Incremental product improvements'),
('PRD-SUPP',     'Product Support & Bug Fixes',        'PRD',  'RTB-MNT', 'Bug fixes and support'),
('PRD-DOC',      'Documentation & Knowledge Base',     'PRD',  'RTB-SUP', 'Docs, wikis, knowledge management'),
-- FAC
('FAC-RENT',     'Office Rent & Leases',               'FAC',  'RTB-OPS', 'Office space costs'),
('FAC-UTIL',     'Utilities',                          'FAC',  'RTB-OPS', 'Power, water, HVAC'),
('FAC-MAINT',    'Facilities Maintenance',             'FAC',  'RTB-MNT', 'Maintenance and repairs'),
('FAC-EQUIP',    'Equipment & Furniture',              'FAC',  'RTB-OPS', 'Office equipment'),
('FAC-NEWSITE',  'New Site / Expansion',               'FAC',  'CTB-TRN', 'New office or facility'),
('FAC-RENO',     'Renovation & Improvement',           'FAC',  'CTB-EFF', 'Office renovations'),
('FAC-SECPHY',   'Physical Security',                  'FAC',  'RTB-CMP', 'Physical security systems'),
('FAC-INSUR',    'Property & Casualty Insurance',      'FAC',  'RTB-CMP', 'Property insurance'),
-- FIN
('FIN-ACCT',     'Accounting & Financial Reporting',   'FIN',  'RTB-OPS', 'Core accounting function'),
('FIN-TAX',      'Tax Planning & Compliance',          'FIN',  'RTB-CMP', 'Tax compliance and planning'),
('FIN-AUDIT',    'Internal & External Audit',          'FIN',  'RTB-CMP', 'Audit fees and internal audit'),
('FIN-TREAS',    'Treasury & Cash Management',         'FIN',  'RTB-OPS', 'Treasury function'),
('FIN-LEGAL',    'Legal Operations',                   'FIN',  'RTB-CMP', 'Legal counsel and contracts'),
('FIN-RISK',     'Enterprise Risk Management',         'FIN',  'RTB-CMP', 'ERM program'),
('FIN-MA',       'M&A / Corporate Development',        'FIN',  'CTB-TRN', 'Acquisitions and corporate dev'),
('FIN-FPA',      'Financial Planning & Analysis',      'FIN',  'RTB-SUP', 'FP&A function'),
-- CRP
('CRP-EXEC',     'Executive Office',                   'CRP',  'RTB-SUP', 'C-suite office costs'),
('CRP-BOARD',    'Board of Directors',                 'CRP',  'RTB-SUP', 'Board fees and governance'),
('CRP-STRAT',    'Corporate Strategy',                 'CRP',  'CTB-TRN', 'Strategy function'),
('CRP-IR',       'Investor Relations',                 'CRP',  'RTB-OPS', 'IR function'),
('CRP-COMMS',    'Corporate Communications',           'CRP',  'RTB-SUP', 'PR and comms'),
-- DAT
('DAT-FEED',     'Market Data Feeds & Subscriptions',  'DAT',  'RTB-OPS', 'Bloomberg, Refinitiv, etc.'),
('DAT-RES',      'Research & Analytics Subscriptions', 'DAT',  'RTB-OPS', 'Research subscriptions'),
('DAT-ACQ',      'Data Acquisition',                   'DAT',  'CTB-GRW', 'New dataset purchases'),
('DAT-GOV',      'Data Governance & Quality',          'DAT',  'RTB-CMP', 'Data governance programs'),
('DAT-VIS',      'BI & Visualization Tools',           'DAT',  'RTB-SUP', 'Tableau, PowerBI, etc.');
