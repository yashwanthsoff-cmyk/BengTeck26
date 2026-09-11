-- Supabase Schema for Checkpoint-Native DX (v9)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS checkpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id TEXT UNIQUE NOT NULL,
    session_id TEXT,
    project_name TEXT NOT NULL,
    branch_name TEXT,
    commit_hash TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS requirements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    requirement_text TEXT NOT NULL,
    requirement_type TEXT DEFAULT 'functional' CHECK (requirement_type IN ('functional', 'non_functional', 'technical', 'ux')),
    status TEXT DEFAULT 'not_started' CHECK (status IN ('draft', 'backlog', 'ready', 'not_started', 'in_progress', 'blocked', 'in_review', 'deferred', 'done', 'superseded')),
    priority INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    priority_tier TEXT DEFAULT 'P2' CHECK (priority_tier IN ('P0', 'P1', 'P2')),
    moscow TEXT DEFAULT 'should' CHECK (moscow IN ('must', 'should', 'could', 'wont')),
    effort_points INTEGER,
    acceptance_criteria JSONB DEFAULT '[]'::jsonb,
    owner TEXT,
    priority_reasoning TEXT,
    evidence TEXT,
    source TEXT DEFAULT 'agent_extracted' CHECK (source IN ('agent_extracted', 'manual', 'user_provided')),
    status_changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status_changed_by TEXT DEFAULT 'user',
    previous_status TEXT,
    status_change_reason TEXT,
    business_impact_score INTEGER DEFAULT 5,
    urgency_score INTEGER DEFAULT 5,
    risk_score INTEGER DEFAULT 3,
    calculated_priority_score REAL,
    calculated_priority_tier TEXT,
    priority_override_reason TEXT,
    rice_reach INTEGER DEFAULT 5,
    rice_impact INTEGER DEFAULT 5,
    rice_confidence REAL DEFAULT 0.8,
    rice_effort REAL DEFAULT 3.0,
    rice_score REAL,
    rice_rank INTEGER,
    gherkin_scenarios JSONB DEFAULT '[]'::jsonb,
    complexity_factors JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resume_contracts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    session_id TEXT,
    template TEXT NOT NULL DEFAULT 'dev' CHECK (template IN ('dev', 'qa', 'pm')),
    version INTEGER NOT NULL DEFAULT 1,
    contract_version INTEGER DEFAULT 1,
    contract_text TEXT,
    contract_sections JSONB DEFAULT '{}'::jsonb,
    contract_json JSONB,
    schema_valid BOOLEAN NOT NULL DEFAULT FALSE,
    validation_errors JSONB DEFAULT '[]'::jsonb,
    integrity_check_passed BOOLEAN,
    integrity_check_details JSONB DEFAULT '{}'::jsonb,
    integrity_check_timestamp TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT DEFAULT 'agent'
);

CREATE TABLE IF NOT EXISTS dead_end_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_name TEXT NOT NULL,
    cluster_key TEXT NOT NULL,
    representative_root_cause TEXT NOT NULL,
    custom_name TEXT,
    ai_suggested_name TEXT,
    name_reasoning TEXT,
    member_count INTEGER DEFAULT 1,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    common_suggested_fix TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_name, cluster_key)
);

CREATE TABLE IF NOT EXISTS dead_end_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    databricks_trace_id TEXT,
    databricks_experiment_name TEXT DEFAULT 'checkpoint-dx-dead-ends',
    used_fallback BOOLEAN DEFAULT FALSE,
    dead_end_type TEXT NOT NULL CHECK (dead_end_type IN ('repeated_failure', 'timeout', 'api_error', 'logic_error', 'resource_exhaustion', 'unknown')),
    root_cause TEXT,
    suggested_fix TEXT,
    alternative_approaches TEXT[],
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
    failed_attempts INTEGER DEFAULT 0,
    files_affected TEXT[],
    severity TEXT DEFAULT 'minor' CHECK (severity IN ('critical', 'major', 'minor')),
    cluster_id UUID REFERENCES dead_end_clusters(id) ON DELETE SET NULL,
    cluster_key TEXT,
    fix_effectiveness TEXT DEFAULT 'untested' CHECK (fix_effectiveness IN ('worked', 'failed', 'untested')),
    fix_outcome_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intent_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    intent_text TEXT NOT NULL,
    intent_category TEXT DEFAULT 'implementation' CHECK (intent_category IN ('implementation', 'refactor', 'feature', 'bugfix', 'optimization')),
    implementation_status TEXT DEFAULT 'unknown' CHECK (implementation_status IN ('met', 'partial', 'missing', 'drift', 'gap', 'scope_creep', 'unknown')),
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
    databricks_trace_id TEXT,
    used_fallback BOOLEAN DEFAULT FALSE,
    implementation_evidence TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dashboard_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_name TEXT UNIQUE NOT NULL,
    query_sql TEXT NOT NULL,
    cached_result JSONB NOT NULL,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_valid BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS agent_memory_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    databricks_scope TEXT NOT NULL UNIQUE,
    used_fallback BOOLEAN DEFAULT FALSE,
    integrity_score FLOAT,
    integrity_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intent_requirements_map (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intent_id UUID REFERENCES intent_summaries(id) ON DELETE CASCADE,
    requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    conformance_status TEXT DEFAULT 'unknown',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS requirement_dependencies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    depends_on_requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    dependency_reasoning TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(requirement_id, depends_on_requirement_id)
);

CREATE TABLE IF NOT EXISTS contract_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_family_id UUID NOT NULL,
    resume_contract_id UUID REFERENCES resume_contracts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    changelog TEXT NOT NULL,
    diff_from_previous JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS contract_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_contract_id UUID REFERENCES resume_contracts(id) ON DELETE CASCADE,
    consumer_type TEXT NOT NULL CHECK (consumer_type IN ('agent_session', 'human_ui_view', 'api_fetch')),
    consumer_identifier TEXT,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    outcome_reported BOOLEAN DEFAULT FALSE,
    outcome_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_id ON checkpoints(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id);
CREATE INDEX IF NOT EXISTS idx_requirements_checkpoint ON requirements(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_req_dep_requirement ON requirement_dependencies(requirement_id);
CREATE INDEX IF NOT EXISTS idx_req_dep_depends_on ON requirement_dependencies(depends_on_requirement_id);
CREATE INDEX IF NOT EXISTS idx_dead_ends_checkpoint ON dead_end_summaries(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_dead_ends_cluster ON dead_end_summaries(cluster_id);
CREATE INDEX IF NOT EXISTS idx_dead_ends_severity ON dead_end_summaries(severity);
CREATE INDEX IF NOT EXISTS idx_dead_end_clusters_proj ON dead_end_clusters(project_name);
CREATE INDEX IF NOT EXISTS idx_dead_end_clusters_key ON dead_end_clusters(cluster_key);
CREATE INDEX IF NOT EXISTS idx_intents_checkpoint ON intent_summaries(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_contracts_checkpoint ON resume_contracts(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_contracts_family ON contract_versions(contract_family_id);
CREATE INDEX IF NOT EXISTS idx_executions_contract ON contract_executions(resume_contract_id);
CREATE INDEX IF NOT EXISTS idx_cache_query ON dashboard_cache(query_name);
CREATE INDEX IF NOT EXISTS idx_memory_checkpoint ON agent_memory_snapshots(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_intent_req_map_intent ON intent_requirements_map(intent_id);
CREATE INDEX IF NOT EXISTS idx_intent_req_map_req ON intent_requirements_map(requirement_id);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_checkpoints_updated_at ON checkpoints;
CREATE TRIGGER update_checkpoints_updated_at BEFORE UPDATE ON checkpoints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_requirements_updated_at ON requirements;
CREATE TRIGGER update_requirements_updated_at BEFORE UPDATE ON requirements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE requirements ENABLE ROW LEVEL SECURITY;
ALTER TABLE requirement_dependencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE dead_end_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE dead_end_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE intent_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_memory_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE intent_requirements_map ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'checkpoints') THEN
        CREATE POLICY "Allow all operations" ON checkpoints FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'requirements') THEN
        CREATE POLICY "Allow all operations" ON requirements FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'requirement_dependencies') THEN
        CREATE POLICY "Allow all operations" ON requirement_dependencies FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'resume_contracts') THEN
        CREATE POLICY "Allow all operations" ON resume_contracts FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'contract_versions') THEN
        CREATE POLICY "Allow all operations" ON contract_versions FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'contract_executions') THEN
        CREATE POLICY "Allow all operations" ON contract_executions FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'dead_end_clusters') THEN
        CREATE POLICY "Allow all operations" ON dead_end_clusters FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'dead_end_summaries') THEN
        CREATE POLICY "Allow all operations" ON dead_end_summaries FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'intent_summaries') THEN
        CREATE POLICY "Allow all operations" ON intent_summaries FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'agent_memory_snapshots') THEN
        CREATE POLICY "Allow all operations" ON agent_memory_snapshots FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'intent_requirements_map') THEN
        CREATE POLICY "Allow all operations" ON intent_requirements_map FOR ALL USING (true);
    END IF;
END $$;

-- Feature 5 Hardening Tables
CREATE TABLE IF NOT EXISTS integrity_score_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    integrity_score FLOAT,
    reason TEXT,
    stale_memory_count INTEGER DEFAULT 0,
    conflict_count INTEGER DEFAULT 0,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_integrity_history_session ON integrity_score_history(session_id);
CREATE INDEX IF NOT EXISTS idx_integrity_history_recorded ON integrity_score_history(recorded_at);
ALTER TABLE integrity_score_history ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS memory_conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    memory_key_a TEXT NOT NULL,
    memory_key_b TEXT NOT NULL,
    conflict_reason TEXT,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_session_memory_keys UNIQUE (session_id, memory_key_a, memory_key_b)
);
CREATE INDEX IF NOT EXISTS idx_memory_conflicts_session ON memory_conflicts(session_id);
ALTER TABLE memory_conflicts ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'integrity_score_history') THEN
        CREATE POLICY "Allow all operations" ON integrity_score_history FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'memory_conflicts') THEN
        CREATE POLICY "Allow all operations" ON memory_conflicts FOR ALL USING (true);
    END IF;
END $$;

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
CREATE INDEX IF NOT EXISTS idx_preflight_overrides_session ON preflight_overrides(session_id);
CREATE INDEX IF NOT EXISTS idx_preflight_overrides_created ON preflight_overrides(created_at DESC);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'preflight_overrides') THEN
        CREATE POLICY "Allow all operations" ON preflight_overrides FOR ALL USING (true);
    END IF;
END $$;

-- Requirement Status History Table (Feature 2 Hardened+)
CREATE TABLE IF NOT EXISTS requirement_status_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    changed_by TEXT NOT NULL DEFAULT 'user',
    change_reason TEXT,
    duration_in_prev_status_hours REAL DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE requirement_status_history ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_req_status_hist_req_id ON requirement_status_history(requirement_id);
CREATE INDEX IF NOT EXISTS idx_req_status_hist_cp_id ON requirement_status_history(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_req_status_hist_created ON requirement_status_history(created_at DESC);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'requirement_status_history') THEN
        CREATE POLICY "Allow all operations" ON requirement_status_history FOR ALL USING (true);
    END IF;
END $$;

-- Compliance Violations Table (Feature 3 Hardened+)
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

ALTER TABLE compliance_violations ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_compliance_violations_cp ON compliance_violations(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_compliance_violations_status ON compliance_violations(status);
CREATE INDEX IF NOT EXISTS idx_compliance_violations_sev ON compliance_violations(severity);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'compliance_violations') THEN
        CREATE POLICY "Allow all operations" ON compliance_violations FOR ALL USING (true);
    END IF;
END $$;

-- Compliance History Table (Feature 3 Hardened+)
CREATE TABLE IF NOT EXISTS compliance_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    overall_score REAL NOT NULL,
    total_clauses INTEGER NOT NULL,
    compliant_clauses INTEGER NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE compliance_history ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_compliance_hist_cp ON compliance_history(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_compliance_hist_time ON compliance_history(recorded_at DESC);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'compliance_history') THEN
        CREATE POLICY "Allow all operations" ON compliance_history FOR ALL USING (true);
    END IF;
END $$;


-- Feature 4 (Agent Resume Contract Hardened+) Extensions
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


-- Feature 5 (Resume Integrity Check Hardened+) Extensions
-- Migration 010: Feature 5 (Resume Integrity Check Hardened+) Blueprint
-- Adds multi-session tracking columns, integrity trends table, integrity alerts table, and memory TTL configuration.

-- 1. Add multi-session tracking columns to agent_memory_snapshots
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_memory_snapshots' AND column_name='multi_session_integrity_score') THEN
        ALTER TABLE agent_memory_snapshots ADD COLUMN multi_session_integrity_score FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_memory_snapshots' AND column_name='multi_session_integrity_reason') THEN
        ALTER TABLE agent_memory_snapshots ADD COLUMN multi_session_integrity_reason TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_memory_snapshots' AND column_name='integrity_trend_7d') THEN
        ALTER TABLE agent_memory_snapshots ADD COLUMN integrity_trend_7d FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_memory_snapshots' AND column_name='integrity_anomaly_detected') THEN
        ALTER TABLE agent_memory_snapshots ADD COLUMN integrity_anomaly_detected BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_memory_snapshots' AND column_name='last_cleanup_at') THEN
        ALTER TABLE agent_memory_snapshots ADD COLUMN last_cleanup_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- 2. Create integrity_trends table
CREATE TABLE IF NOT EXISTS integrity_trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    integrity_score FLOAT NOT NULL,
    integrity_reason TEXT,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    trend_direction TEXT CHECK (trend_direction IN ('improving', 'stable', 'degrading')),
    trend_magnitude FLOAT
);

CREATE INDEX IF NOT EXISTS idx_integrity_trends_session ON integrity_trends(session_id);
CREATE INDEX IF NOT EXISTS idx_integrity_trends_recorded ON integrity_trends(recorded_at DESC);

ALTER TABLE integrity_trends ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to integrity_trends"
    ON integrity_trends
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 3. Create integrity_alerts table
CREATE TABLE IF NOT EXISTS integrity_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    alert_type TEXT CHECK (alert_type IN ('anomaly_detected', 'critical_drop', 'stale_memory', 'trend_degrading')),
    severity TEXT CHECK (severity IN ('critical', 'major', 'minor')),
    message TEXT NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_integrity_alerts_session ON integrity_alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_integrity_alerts_unack ON integrity_alerts(acknowledged) WHERE acknowledged = FALSE;

ALTER TABLE integrity_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to integrity_alerts"
    ON integrity_alerts
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 4. Create memory_ttl_config table
CREATE TABLE IF NOT EXISTS memory_ttl_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT UNIQUE NOT NULL,
    ttl_days INTEGER DEFAULT 30,
    auto_cleanup_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_ttl_session ON memory_ttl_config(session_id);

ALTER TABLE memory_ttl_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to memory_ttl_config"
    ON memory_ttl_config
    FOR ALL
    USING (true)
    WITH CHECK (true);
