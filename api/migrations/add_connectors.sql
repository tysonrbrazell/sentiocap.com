-- ============================================================
-- SentioCap: Connector Framework Migration
-- Run against Supabase PostgreSQL
-- ============================================================

CREATE TYPE connector_type AS ENUM ('salesforce', 'jira', 'hubspot', 'dynamics', 'workday', 'sap', 'servicenow');
CREATE TYPE connector_status AS ENUM ('disconnected', 'connected', 'syncing', 'error');
CREATE TYPE sync_status AS ENUM ('pending', 'running', 'completed', 'failed');

CREATE TABLE connector_configs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connector_type connector_type NOT NULL,
  status connector_status NOT NULL DEFAULT 'disconnected',
  -- OAuth tokens (encrypted in production)
  access_token TEXT,
  refresh_token TEXT,
  token_expires_at TIMESTAMPTZ,
  instance_url VARCHAR(500),
  -- Settings
  sync_frequency VARCHAR(20) DEFAULT 'daily', -- 'hourly', 'daily', 'weekly', 'manual'
  last_sync_at TIMESTAMPTZ,
  config JSONB DEFAULT '{}', -- connector-specific settings
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, connector_type)
);
CREATE INDEX idx_connector_configs_org ON connector_configs(org_id);

CREATE TABLE connector_syncs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  connector_id UUID NOT NULL REFERENCES connector_configs(id) ON DELETE CASCADE,
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  status sync_status NOT NULL DEFAULT 'pending',
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  records_synced INTEGER DEFAULT 0,
  records_mapped INTEGER DEFAULT 0,
  errors JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_connector_syncs_connector ON connector_syncs(connector_id);

CREATE TABLE connector_mappings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connector_type connector_type NOT NULL,
  source_type VARCHAR(50) NOT NULL, -- 'product', 'project', 'epic', 'campaign'
  source_id VARCHAR(255) NOT NULL, -- ID in the external system
  source_name VARCHAR(500) NOT NULL, -- name in external system
  investment_id UUID REFERENCES investments(id),
  l2_category VARCHAR(20),
  mapping_method VARCHAR(20) DEFAULT 'ai', -- 'ai', 'manual', 'rule'
  confidence FLOAT DEFAULT 0.5,
  confirmed BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, connector_type, source_type, source_id)
);
CREATE INDEX idx_connector_mappings_org ON connector_mappings(org_id);
CREATE INDEX idx_connector_mappings_investment ON connector_mappings(investment_id);

-- Revenue data synced from CRM
CREATE TABLE crm_revenue_data (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connector_type connector_type NOT NULL,
  period VARCHAR(7) NOT NULL, -- 'YYYY-MM'
  source_product VARCHAR(500),
  source_segment VARCHAR(255),
  investment_id UUID REFERENCES investments(id),
  pipeline_amount NUMERIC(18,2) DEFAULT 0,
  closed_won_amount NUMERIC(18,2) DEFAULT 0,
  new_logos INTEGER DEFAULT 0,
  churned_amount NUMERIC(18,2) DEFAULT 0,
  avg_deal_size NUMERIC(18,2),
  win_rate NUMERIC(6,4),
  avg_cycle_days INTEGER,
  synced_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_crm_revenue_org ON crm_revenue_data(org_id);
CREATE INDEX idx_crm_revenue_period ON crm_revenue_data(period);
CREATE INDEX idx_crm_revenue_investment ON crm_revenue_data(investment_id);

-- Effort data synced from JIRA
CREATE TABLE effort_data (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connector_type connector_type NOT NULL,
  period VARCHAR(7) NOT NULL,
  source_project VARCHAR(500),
  source_epic VARCHAR(500),
  investment_id UUID REFERENCES investments(id),
  hours_logged NUMERIC(10,2) DEFAULT 0,
  effort_cost NUMERIC(18,2) DEFAULT 0, -- hours * blended rate
  story_points_completed INTEGER DEFAULT 0,
  issues_total INTEGER DEFAULT 0,
  issues_bugs INTEGER DEFAULT 0,
  issues_features INTEGER DEFAULT 0,
  issues_tasks INTEGER DEFAULT 0,
  velocity_trend NUMERIC(8,4), -- % change from prior period
  backlog_growth INTEGER DEFAULT 0, -- new - completed
  completion_pct NUMERIC(6,2),
  synced_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_effort_data_org ON effort_data(org_id);
CREATE INDEX idx_effort_data_period ON effort_data(period);
CREATE INDEX idx_effort_data_investment ON effort_data(investment_id);

ALTER TABLE connector_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_syncs ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_revenue_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE effort_data ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['connector_configs','connector_mappings']
  LOOP
    EXECUTE format('CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();', t, t);
  END LOOP;
END;
$$;
