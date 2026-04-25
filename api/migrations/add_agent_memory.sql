-- Per-company agent memory tables
-- Run against Supabase: host='aws-1-us-east-1.pooler.supabase.com', port=5432

-- Classification corrections: Scout learns from these
CREATE TABLE IF NOT EXISTS classification_corrections (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  source_description TEXT NOT NULL,
  source_cost_center VARCHAR(100),
  source_gl_account VARCHAR(100),
  original_l1 VARCHAR(10),
  original_l2 VARCHAR(20),
  original_l3 VARCHAR(10),
  original_l4 VARCHAR(50),
  corrected_l1 VARCHAR(10) NOT NULL,
  corrected_l2 VARCHAR(20) NOT NULL,
  corrected_l3 VARCHAR(10),
  corrected_l4 VARCHAR(50),
  corrected_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_class_corrections_org ON classification_corrections(org_id);
CREATE INDEX IF NOT EXISTS idx_class_corrections_desc ON classification_corrections(source_description);

-- Firm glossary: maps company-specific terms to taxonomy
CREATE TABLE IF NOT EXISTS firm_glossary (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  firm_term VARCHAR(255) NOT NULL,
  mapped_l1 VARCHAR(10),
  mapped_l2 VARCHAR(20),
  mapped_l3 VARCHAR(10),
  mapped_l4 VARCHAR(50),
  confidence FLOAT DEFAULT 1.0,
  source VARCHAR(50) DEFAULT 'manual', -- 'manual', 'learned', 'correction'
  usage_count INTEGER DEFAULT 1,
  last_used_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, firm_term)
);
CREATE INDEX IF NOT EXISTS idx_firm_glossary_org ON firm_glossary(org_id);
CREATE INDEX IF NOT EXISTS idx_firm_glossary_term ON firm_glossary(firm_term);

-- Signal preferences: Sentinel learns what each org cares about
CREATE TABLE IF NOT EXISTS signal_preferences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  category VARCHAR(50) NOT NULL,
  action VARCHAR(20) NOT NULL, -- 'acknowledged', 'resolved', 'dismissed'
  count INTEGER DEFAULT 1,
  last_action_at TIMESTAMPTZ DEFAULT NOW(),
  sensitivity_override FLOAT, -- null = default, 0.5 = less sensitive, 2.0 = more sensitive
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, category, action)
);
CREATE INDEX IF NOT EXISTS idx_signal_prefs_org ON signal_preferences(org_id);

-- Custom peer groups: Compass remembers preferred comparisons
CREATE TABLE IF NOT EXISTS custom_peer_groups (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  tickers TEXT[] NOT NULL, -- array of tickers
  is_default BOOLEAN DEFAULT FALSE,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_peer_groups_org ON custom_peer_groups(org_id);

-- Decision outcomes: tracks what happened after signals were acted on
CREATE TABLE IF NOT EXISTS decision_outcomes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  decision_id UUID REFERENCES decisions(id),
  category VARCHAR(50) NOT NULL,
  action_taken VARCHAR(50) NOT NULL, -- 'killed', 'accelerated', 'reallocated', 'extended', 'ignored'
  investment_id UUID REFERENCES investments(id),
  metrics_before JSONB DEFAULT '{}', -- snapshot of key metrics at decision time
  metrics_after JSONB DEFAULT '{}', -- snapshot 90 days later
  outcome_score FLOAT, -- -1 to 1: negative = bad decision, positive = good decision
  outcome_notes TEXT,
  measured_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_org ON decision_outcomes(org_id);
CREATE INDEX IF NOT EXISTS idx_decision_outcomes_category ON decision_outcomes(category);

-- Forecast accuracy: Oracle tracks its own predictions vs actuals
CREATE TABLE IF NOT EXISTS forecast_accuracy (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  period VARCHAR(7) NOT NULL, -- 'YYYY-MM'
  forecast_date DATE NOT NULL, -- when the forecast was made
  l2_category VARCHAR(20) NOT NULL,
  forecasted_amount NUMERIC(18,2) NOT NULL,
  actual_amount NUMERIC(18,2), -- filled in after actuals arrive
  variance_pct FLOAT, -- computed: (actual - forecast) / forecast
  bias_direction VARCHAR(10), -- 'over' or 'under'
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_forecast_accuracy_org ON forecast_accuracy(org_id);
CREATE INDEX IF NOT EXISTS idx_forecast_accuracy_period ON forecast_accuracy(period);

-- Report preferences: Scribe learns what format works
CREATE TABLE IF NOT EXISTS report_preferences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  report_type VARCHAR(50) NOT NULL, -- 'board_deck', 'monthly_briefing', 'investment_case'
  preferences JSONB DEFAULT '{}', -- {max_pages, focus_areas, exclude_sections, tone, detail_level}
  feedback_scores JSONB DEFAULT '[]', -- [{generated_at, score, feedback_text}]
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, report_type)
);
CREATE INDEX IF NOT EXISTS idx_report_prefs_org ON report_preferences(org_id);

-- Cross-network intelligence: aggregated, anonymized learning (not org-specific)
CREATE TABLE IF NOT EXISTS network_intelligence (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  intelligence_type VARCHAR(50) NOT NULL, -- 'classification_consensus', 'benchmark_update', 'decision_outcome_stat', 'forecast_bias'
  key VARCHAR(255) NOT NULL, -- lookup key (e.g., expense description, category, sector)
  data JSONB NOT NULL, -- the aggregated intelligence
  n_companies INTEGER DEFAULT 0, -- how many companies contributed (must be >= 5 to use)
  confidence FLOAT DEFAULT 0.5,
  last_updated TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(intelligence_type, key)
);
CREATE INDEX IF NOT EXISTS idx_network_intel_type ON network_intelligence(intelligence_type);
CREATE INDEX IF NOT EXISTS idx_network_intel_key ON network_intelligence(key);

-- Add RLS
ALTER TABLE classification_corrections ENABLE ROW LEVEL SECURITY;
ALTER TABLE firm_glossary ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_peer_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecast_accuracy ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_preferences ENABLE ROW LEVEL SECURITY;

-- Triggers for updated_at
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['firm_glossary','signal_preferences','custom_peer_groups','decision_outcomes','forecast_accuracy','report_preferences']
  LOOP
    EXECUTE format(
      'DROP TRIGGER IF EXISTS trg_%s_updated_at ON %s;
       CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();',
      t, t, t, t
    );
  END LOOP;
END;
$$;
