-- =============================================================================
-- Migration: Add decisions table for signal detection engine
-- =============================================================================

CREATE TYPE decision_severity AS ENUM ('critical', 'warning', 'info');
CREATE TYPE decision_status AS ENUM ('new', 'acknowledged', 'in_progress', 'resolved', 'dismissed');

CREATE TABLE decisions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  investment_id UUID REFERENCES investments(id),
  plan_id UUID REFERENCES plans(id),

  -- Decision category (1-20)
  category VARCHAR(50) NOT NULL,
  category_number INTEGER NOT NULL CHECK (category_number BETWEEN 1 AND 20),
  severity decision_severity NOT NULL,

  -- What triggered it
  trigger_type VARCHAR(100),
  trigger_data JSONB NOT NULL DEFAULT '{}',

  -- AI-generated content
  title VARCHAR(500) NOT NULL,
  description TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  impact_estimate TEXT,

  -- Assignment
  owner VARCHAR(255),

  -- Status tracking
  status decision_status NOT NULL DEFAULT 'new',
  resolved_at TIMESTAMPTZ,
  resolved_by UUID REFERENCES users(id),
  resolution_notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_decisions_org_id ON decisions(org_id);
CREATE INDEX idx_decisions_severity ON decisions(severity);
CREATE INDEX idx_decisions_status ON decisions(status);
CREATE INDEX idx_decisions_category ON decisions(category);
CREATE INDEX idx_decisions_investment_id ON decisions(investment_id);

CREATE TRIGGER trg_decisions_updated_at BEFORE UPDATE ON decisions
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_decisions" ON decisions
  FOR ALL USING (org_id IN (SELECT org_id FROM users WHERE supabase_uid = auth.uid()));
