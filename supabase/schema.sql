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
    status TEXT DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'done', 'blocked', 'deferred', 'superseded')),
    priority INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    evidence TEXT,
    source TEXT DEFAULT 'agent_extracted' CHECK (source IN ('agent_extracted', 'manual', 'user_provided')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resume_contracts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    contract_version INTEGER DEFAULT 1,
    contract_text TEXT NOT NULL,
    contract_sections JSONB DEFAULT '{}'::jsonb,
    integrity_check_passed BOOLEAN,
    integrity_check_details JSONB DEFAULT '{}'::jsonb,
    integrity_check_timestamp TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by TEXT DEFAULT 'agent'
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

CREATE INDEX IF NOT EXISTS idx_checkpoints_id ON checkpoints(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_session ON checkpoints(session_id);
CREATE INDEX IF NOT EXISTS idx_requirements_checkpoint ON requirements(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_dead_ends_checkpoint ON dead_end_summaries(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_intents_checkpoint ON intent_summaries(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_contracts_checkpoint ON resume_contracts(checkpoint_id);
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
ALTER TABLE resume_contracts ENABLE ROW LEVEL SECURITY;
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
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'resume_contracts') THEN
        CREATE POLICY "Allow all operations" ON resume_contracts FOR ALL USING (true);
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

