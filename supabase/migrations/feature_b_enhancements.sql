-- Feature B Enhancements: Requirement Ledger (Prioritization, Dependencies, Effort, Acceptance Criteria, Owner)

ALTER TABLE requirements
  ADD COLUMN IF NOT EXISTS priority_tier TEXT CHECK (priority_tier IN ('P0', 'P1', 'P2')) DEFAULT 'P2',
  ADD COLUMN IF NOT EXISTS moscow TEXT CHECK (moscow IN ('must', 'should', 'could', 'wont')) DEFAULT 'should',
  ADD COLUMN IF NOT EXISTS effort_points INTEGER,
  ADD COLUMN IF NOT EXISTS acceptance_criteria JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS owner TEXT,
  ADD COLUMN IF NOT EXISTS priority_reasoning TEXT;

CREATE TABLE IF NOT EXISTS requirement_dependencies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    depends_on_requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    dependency_reasoning TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(requirement_id, depends_on_requirement_id)
);

ALTER TABLE requirement_dependencies ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'requirement_dependencies') THEN
        CREATE POLICY "Allow all operations" ON requirement_dependencies FOR ALL USING (true);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_req_dep_requirement ON requirement_dependencies(requirement_id);
CREATE INDEX IF NOT EXISTS idx_req_dep_depends_on ON requirement_dependencies(depends_on_requirement_id);
