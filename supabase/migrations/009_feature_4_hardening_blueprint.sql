-- Migration 009: Feature 4 (Agent Resume Contract Hardened+) Blueprint
-- Adds custom templates builder, template versioning & A/B testing,
-- cross-feature conflict registry, and deep contract interaction analytics.

-- 1. Create custom_templates table
CREATE TABLE IF NOT EXISTS custom_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_name TEXT NOT NULL UNIQUE,
    target_audience TEXT NOT NULL DEFAULT 'dev',
    created_by TEXT NOT NULL DEFAULT 'user',
    sections JSONB NOT NULL DEFAULT '[]'::jsonb,
    theme JSONB NOT NULL DEFAULT '{"layout": "standard", "accent": "#0ea5e9"}'::jsonb,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    validation_errors JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_custom_templates_aud ON custom_templates(target_audience);
ALTER TABLE custom_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to custom_templates"
    ON custom_templates
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 2. Create template_versions table
CREATE TABLE IF NOT EXISTS template_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id UUID REFERENCES custom_templates(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    changelog TEXT NOT NULL DEFAULT 'Initial version',
    sections JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_template_versions_tpl ON template_versions(template_id);
ALTER TABLE template_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to template_versions"
    ON template_versions
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 3. Create template_ab_tests table
CREATE TABLE IF NOT EXISTS template_ab_tests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    test_name TEXT NOT NULL,
    variant_a_id TEXT NOT NULL,
    variant_b_id TEXT NOT NULL,
    traffic_split REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'paused')),
    results JSONB DEFAULT '{"variant_a_impressions": 0, "variant_b_impressions": 0, "variant_a_conversions": 0, "variant_b_conversions": 0}'::jsonb,
    start_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_template_ab_status ON template_ab_tests(status);
ALTER TABLE template_ab_tests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to template_ab_tests"
    ON template_ab_tests
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 4. Create contract_conflicts table
CREATE TABLE IF NOT EXISTS contract_conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    session_id TEXT,
    conflict_type TEXT NOT NULL DEFAULT 'requirement_vs_dead_end' CHECK (conflict_type IN ('requirement_vs_dead_end', 'intent_vs_requirement', 'integrity_vs_intent', 'custom')),
    severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    description TEXT NOT NULL,
    involved_features JSONB NOT NULL DEFAULT '[]'::jsonb,
    resolution_strategies JSONB NOT NULL DEFAULT '[]'::jsonb,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolution_strategy_id TEXT,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_contract_conflicts_cp ON contract_conflicts(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_contract_conflicts_res ON contract_conflicts(resolved);
CREATE INDEX IF NOT EXISTS idx_contract_conflicts_sev ON contract_conflicts(severity);
ALTER TABLE contract_conflicts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to contract_conflicts"
    ON contract_conflicts
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 5. Create contract_interactions table
CREATE TABLE IF NOT EXISTS contract_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_contract_id UUID REFERENCES resume_contracts(id) ON DELETE CASCADE,
    consumer_type TEXT NOT NULL DEFAULT 'human_ui_view' CHECK (consumer_type IN ('agent_session', 'human_ui_view', 'api_fetch')),
    interaction_type TEXT NOT NULL DEFAULT 'view' CHECK (interaction_type IN ('view', 'scroll', 'click_section', 'export_pdf', 'export_md', 'copy_json')),
    section_name TEXT,
    duration_seconds REAL DEFAULT 0.0,
    scroll_depth REAL DEFAULT 0.0,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contract_interactions_rc ON contract_interactions(resume_contract_id);
CREATE INDEX IF NOT EXISTS idx_contract_interactions_type ON contract_interactions(interaction_type);
ALTER TABLE contract_interactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to contract_interactions"
    ON contract_interactions
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 6. Extend resume_contracts with synthesis weights and contract purpose
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='resume_contracts' AND column_name='synthesis_weights') THEN
        ALTER TABLE resume_contracts ADD COLUMN synthesis_weights JSONB DEFAULT '{"requirements": 0.35, "dead_ends": 0.25, "intents": 0.25, "integrity": 0.15}'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='resume_contracts' AND column_name='contract_purpose') THEN
        ALTER TABLE resume_contracts ADD COLUMN contract_purpose TEXT DEFAULT 'development';
    END IF;
END $$;
