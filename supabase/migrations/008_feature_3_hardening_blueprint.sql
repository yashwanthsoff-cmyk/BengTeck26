-- Migration 008: Feature 3 (Intent Conformance Diff Hardened+) Blueprint
-- Adds compliance violations tracking, compliance history auditing, and rich semantic conformance metadata.

-- 1. Create compliance_violations table
CREATE TABLE IF NOT EXISTS compliance_violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    clause_id TEXT NOT NULL,
    clause_text TEXT NOT NULL,
    violation_type TEXT NOT NULL DEFAULT 'functional' CHECK (violation_type IN ('security', 'performance', 'accessibility', 'legal', 'functional', 'code_quality')),
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    remediation_deadline TIMESTAMP WITH TIME ZONE,
    assigned_to TEXT NOT NULL DEFAULT 'unassigned',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'waived')),
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_compliance_violations_cp ON compliance_violations(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_compliance_violations_status ON compliance_violations(status);
CREATE INDEX IF NOT EXISTS idx_compliance_violations_sev ON compliance_violations(severity);

ALTER TABLE compliance_violations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to compliance_violations"
    ON compliance_violations
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 2. Create compliance_history table
CREATE TABLE IF NOT EXISTS compliance_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    overall_score REAL NOT NULL,
    total_clauses INTEGER NOT NULL,
    compliant_clauses INTEGER NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compliance_hist_cp ON compliance_history(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_compliance_hist_time ON compliance_history(recorded_at DESC);

ALTER TABLE compliance_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to compliance_history"
    ON compliance_history
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 3. Extend intent_summaries table with semantic conformance & audit columns
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='semantic_intent') THEN
        ALTER TABLE intent_summaries ADD COLUMN semantic_intent TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='matched_hunks') THEN
        ALTER TABLE intent_summaries ADD COLUMN matched_hunks JSONB DEFAULT '[]'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='conformance_grade') THEN
        ALTER TABLE intent_summaries ADD COLUMN conformance_grade TEXT DEFAULT 'B';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='conformance_scores') THEN
        ALTER TABLE intent_summaries ADD COLUMN conformance_scores JSONB DEFAULT '{}'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='sub_status') THEN
        ALTER TABLE intent_summaries ADD COLUMN sub_status JSONB DEFAULT '{}'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='remediation_suggestions') THEN
        ALTER TABLE intent_summaries ADD COLUMN remediation_suggestions JSONB DEFAULT '[]'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='calibrated_confidence') THEN
        ALTER TABLE intent_summaries ADD COLUMN calibrated_confidence REAL DEFAULT 0.8;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='confidence_interval') THEN
        ALTER TABLE intent_summaries ADD COLUMN confidence_interval JSONB DEFAULT '[]'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='uncertainty_sources') THEN
        ALTER TABLE intent_summaries ADD COLUMN uncertainty_sources JSONB DEFAULT '[]'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='compliance_category') THEN
        ALTER TABLE intent_summaries ADD COLUMN compliance_category TEXT DEFAULT 'functional';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='intent_summaries' AND column_name='violation_details') THEN
        ALTER TABLE intent_summaries ADD COLUMN violation_details JSONB;
    END IF;
END $$;
