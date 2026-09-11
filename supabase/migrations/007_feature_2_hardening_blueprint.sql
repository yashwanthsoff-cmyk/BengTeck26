-- Migration 007: Feature 2 (Unfinished Requirement Ledger Hardened+) Blueprint
-- Adds multi-dimensional workflow, audit history, dynamic priority scoring, RICE, Gherkin scenarios, and complexity factors.

-- 1. Create requirement_status_history table
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

-- Indices for fast timeline and cycle analytics queries
CREATE INDEX IF NOT EXISTS idx_req_status_hist_req_id ON requirement_status_history(requirement_id);
CREATE INDEX IF NOT EXISTS idx_req_status_hist_cp_id ON requirement_status_history(checkpoint_id);
CREATE INDEX IF NOT EXISTS idx_req_status_hist_created ON requirement_status_history(created_at DESC);

-- Enable RLS
ALTER TABLE requirement_status_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access to requirement_status_history"
    ON requirement_status_history
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- 2. Add workflow, priority scoring, RICE, and Gherkin columns to requirements table
DO $$
BEGIN
    -- Workflow columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='status_changed_at') THEN
        ALTER TABLE requirements ADD COLUMN status_changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='status_changed_by') THEN
        ALTER TABLE requirements ADD COLUMN status_changed_by TEXT DEFAULT 'user';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='previous_status') THEN
        ALTER TABLE requirements ADD COLUMN previous_status TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='status_change_reason') THEN
        ALTER TABLE requirements ADD COLUMN status_change_reason TEXT;
    END IF;

    -- Dynamic priority scoring columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='business_impact_score') THEN
        ALTER TABLE requirements ADD COLUMN business_impact_score INTEGER DEFAULT 5;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='urgency_score') THEN
        ALTER TABLE requirements ADD COLUMN urgency_score INTEGER DEFAULT 5;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='risk_score') THEN
        ALTER TABLE requirements ADD COLUMN risk_score INTEGER DEFAULT 3;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='calculated_priority_score') THEN
        ALTER TABLE requirements ADD COLUMN calculated_priority_score REAL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='calculated_priority_tier') THEN
        ALTER TABLE requirements ADD COLUMN calculated_priority_tier TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='priority_override_reason') THEN
        ALTER TABLE requirements ADD COLUMN priority_override_reason TEXT;
    END IF;

    -- RICE scoring columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='rice_reach') THEN
        ALTER TABLE requirements ADD COLUMN rice_reach INTEGER DEFAULT 5;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='rice_impact') THEN
        ALTER TABLE requirements ADD COLUMN rice_impact INTEGER DEFAULT 5;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='rice_confidence') THEN
        ALTER TABLE requirements ADD COLUMN rice_confidence REAL DEFAULT 0.8;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='rice_effort') THEN
        ALTER TABLE requirements ADD COLUMN rice_effort REAL DEFAULT 3.0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='rice_score') THEN
        ALTER TABLE requirements ADD COLUMN rice_score REAL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='rice_rank') THEN
        ALTER TABLE requirements ADD COLUMN rice_rank INTEGER;
    END IF;

    -- Gherkin structured acceptance criteria
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='gherkin_scenarios') THEN
        ALTER TABLE requirements ADD COLUMN gherkin_scenarios JSONB DEFAULT '[]'::jsonb;
    END IF;

    -- Complexity analysis factors
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='requirements' AND column_name='complexity_factors') THEN
        ALTER TABLE requirements ADD COLUMN complexity_factors JSONB DEFAULT '{}'::jsonb;
    END IF;
END $$;
