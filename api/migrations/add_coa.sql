-- Chart of Accounts learning tables

-- The learned chart of accounts structure
CREATE TABLE chart_of_accounts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Account identity
  account_code VARCHAR(50) NOT NULL,        -- e.g., '5020', '5020-200-001', '6200100300'
  account_name VARCHAR(500) NOT NULL,        -- e.g., 'AWS Hosting - Production'
  account_name_normalized VARCHAR(500),      -- lowercase, stripped
  
  -- Parsed segments (Scout learns the structure)
  segment_category VARCHAR(50),              -- extracted category segment (e.g., '5020')
  segment_cost_center VARCHAR(50),           -- extracted cost center (e.g., '200', '4520')
  segment_sub VARCHAR(50),                   -- extracted sub-account (e.g., '001')
  segment_location VARCHAR(50),              -- extracted location if present
  
  -- Classification (learned over time)
  classified_l1 VARCHAR(10),
  classified_l2 VARCHAR(20),
  classified_l3 VARCHAR(10),
  classified_l4 VARCHAR(50),
  classification_confidence FLOAT DEFAULT 0.5,
  classification_source VARCHAR(20) DEFAULT 'ai',  -- 'ai', 'user', 'propagated'
  
  -- Metadata
  account_type VARCHAR(20),                  -- 'expense', 'revenue', 'asset', 'liability', 'equity'
  is_expense BOOLEAN DEFAULT FALSE,          -- True for accounts Scout should classify
  parent_code VARCHAR(50),                   -- parent account for hierarchical CoAs
  typical_monthly_amount NUMERIC(18,2),      -- learned average for anomaly detection
  times_seen INTEGER DEFAULT 1,              -- how many times this account appeared in uploads
  last_seen_at TIMESTAMPTZ DEFAULT NOW(),
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, account_code)
);

CREATE INDEX idx_coa_org ON chart_of_accounts(org_id);
CREATE INDEX idx_coa_code ON chart_of_accounts(account_code);
CREATE INDEX idx_coa_category ON chart_of_accounts(segment_category);
CREATE INDEX idx_coa_expense ON chart_of_accounts(is_expense);

-- Account code structure: Scout learns how this company formats account numbers
CREATE TABLE coa_structure (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  -- Detected structure
  delimiter VARCHAR(5),                      -- '-', '.', '/', or '' (none)
  num_segments INTEGER,                      -- how many segments in the code
  segment_definitions JSONB DEFAULT '[]',    -- [{position: 0, name: 'category', length: 4, type: 'expense_type'}, ...]
  
  -- Category ranges (e.g., 5000-5999 = expenses)
  expense_range_start VARCHAR(20),
  expense_range_end VARCHAR(20),
  revenue_range_start VARCHAR(20),
  revenue_range_end VARCHAR(20),
  
  -- ERP detection
  detected_erp VARCHAR(50),                  -- 'sap', 'oracle', 'workday', 'netsuite', 'quickbooks', 'unknown'
  detection_confidence FLOAT DEFAULT 0.5,
  
  -- Learned from N uploads
  samples_analyzed INTEGER DEFAULT 0,
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id)
);

CREATE INDEX idx_coa_structure_org ON coa_structure(org_id);

-- Period normalization: how this company represents time periods
CREATE TABLE period_formats (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  
  detected_format VARCHAR(50),               -- 'YYYY-MM', 'MM/YYYY', 'QX-YYYY', 'Month YYYY', etc.
  fiscal_year_end_month INTEGER DEFAULT 12,  -- 1-12
  fiscal_year_start_month INTEGER DEFAULT 1,
  example_values TEXT[],                     -- actual values seen
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id)
);

ALTER TABLE chart_of_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE coa_structure ENABLE ROW LEVEL SECURITY;
ALTER TABLE period_formats ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['chart_of_accounts','coa_structure','period_formats']
  LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();', t, t);
  END LOOP;
END;
$$;
