-- Migration 006: Feature 1/A Dead-End Registry Hardened+ Blueprint
-- Adds preflight_overrides table and custom naming columns to dead_end_clusters

ALTER TABLE dead_end_clusters
  ADD COLUMN IF NOT EXISTS custom_name TEXT,
  ADD COLUMN IF NOT EXISTS ai_suggested_name TEXT,
  ADD COLUMN IF NOT EXISTS name_reasoning TEXT;

CREATE TABLE IF NOT EXISTS preflight_overrides (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id TEXT,
    session_id TEXT,
    candidate_approach TEXT NOT NULL,
    jaccard_similarity FLOAT NOT NULL DEFAULT 0.0,
    warning_threshold FLOAT NOT NULL DEFAULT 0.6,
    matched_failures JSONB DEFAULT '[]'::jsonb,
    override_reason TEXT NOT NULL,
    override_category TEXT CHECK (override_category IN ('justified_exception', 'false_positive', 'urgent_fix', 'experiment')) DEFAULT 'justified_exception',
    requires_approval BOOLEAN DEFAULT FALSE,
    approval_status TEXT CHECK (approval_status IN ('pending', 'approved', 'rejected')) DEFAULT 'approved',
    approved_by TEXT,
    risk_score INTEGER DEFAULT 0,
    risk_category TEXT CHECK (risk_category IN ('low', 'medium', 'high', 'critical')) DEFAULT 'low',
    fix_applied TEXT,
    fix_outcome TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE preflight_overrides ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all operations" ON preflight_overrides FOR ALL USING (true);
CREATE INDEX IF NOT EXISTS idx_preflight_overrides_session ON preflight_overrides(session_id);
CREATE INDEX IF NOT EXISTS idx_preflight_overrides_created ON preflight_overrides(created_at DESC);
