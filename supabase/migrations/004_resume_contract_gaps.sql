-- migrations/004_resume_contract_gaps.sql

-- Alter existing resume_contracts table if present, or create fresh
CREATE TABLE IF NOT EXISTS resume_contracts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_id UUID REFERENCES checkpoints(id) ON DELETE CASCADE,
    session_id TEXT,
    template TEXT NOT NULL DEFAULT 'dev' CHECK (template IN ('dev', 'qa', 'pm')),
    version INTEGER NOT NULL DEFAULT 1,
    contract_json JSONB,
    schema_valid BOOLEAN NOT NULL DEFAULT FALSE,
    validation_errors JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add columns if resume_contracts already existed
ALTER TABLE resume_contracts
    ADD COLUMN IF NOT EXISTS session_id TEXT,
    ADD COLUMN IF NOT EXISTS template TEXT NOT NULL DEFAULT 'dev' CHECK (template IN ('dev', 'qa', 'pm')),
    ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS contract_json JSONB,
    ADD COLUMN IF NOT EXISTS schema_valid BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS validation_errors JSONB DEFAULT '[]'::jsonb;

-- Gap 2: versioning + changelog
CREATE TABLE IF NOT EXISTS contract_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_family_id UUID NOT NULL,
    resume_contract_id UUID REFERENCES resume_contracts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    changelog TEXT NOT NULL,
    diff_from_previous JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Gap 4: execution tracking
CREATE TABLE IF NOT EXISTS contract_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_contract_id UUID REFERENCES resume_contracts(id) ON DELETE CASCADE,
    consumer_type TEXT NOT NULL CHECK (consumer_type IN ('agent_session', 'human_ui_view', 'api_fetch')),
    consumer_identifier TEXT,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    outcome_reported BOOLEAN DEFAULT FALSE,
    outcome_notes TEXT
);

ALTER TABLE resume_contracts ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE contract_executions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'resume_contracts') THEN
        CREATE POLICY "Allow all operations" ON resume_contracts FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'contract_versions') THEN
        CREATE POLICY "Allow all operations" ON contract_versions FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'contract_executions') THEN
        CREATE POLICY "Allow all operations" ON contract_executions FOR ALL USING (true);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_contracts_checkpoint ON resume_contracts(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_contracts_family ON contract_versions(contract_family_id);
CREATE INDEX IF NOT EXISTS idx_executions_contract ON contract_executions(resume_contract_id);
