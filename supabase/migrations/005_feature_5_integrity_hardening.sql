-- Migration 005: Feature 5 Hardening — Resume-Integrity Checking
-- Adds integrity_score_history and memory_conflicts tables

-- 1. Table: integrity_score_history
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
DROP POLICY IF EXISTS "Allow all operations" ON integrity_score_history;
CREATE POLICY "Allow all operations" ON integrity_score_history FOR ALL USING (true);

-- 2. Table: memory_conflicts
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
DROP POLICY IF EXISTS "Allow all operations" ON memory_conflicts;
CREATE POLICY "Allow all operations" ON memory_conflicts FOR ALL USING (true);
