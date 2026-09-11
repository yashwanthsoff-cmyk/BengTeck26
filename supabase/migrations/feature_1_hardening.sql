-- Feature 1 Hardening Migration: Dead-End Registry enhancements
-- Gap 2: Clustering table
CREATE TABLE IF NOT EXISTS dead_end_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_name TEXT NOT NULL,
    cluster_key TEXT NOT NULL,
    representative_root_cause TEXT NOT NULL,
    member_count INTEGER DEFAULT 1,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    common_suggested_fix TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(project_name, cluster_key)
);

CREATE INDEX IF NOT EXISTS idx_dead_end_clusters_proj ON dead_end_clusters(project_name);
CREATE INDEX IF NOT EXISTS idx_dead_end_clusters_key ON dead_end_clusters(cluster_key);

ALTER TABLE dead_end_clusters ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all operations' AND tablename = 'dead_end_clusters') THEN
        CREATE POLICY "Allow all operations" ON dead_end_clusters FOR ALL USING (true);
    END IF;
END $$;

-- Gap 3 & 4: Severity, cluster reference, and fix tracking on dead_end_summaries
ALTER TABLE dead_end_summaries
    ADD COLUMN IF NOT EXISTS severity TEXT DEFAULT 'minor' CHECK (severity IN ('critical', 'major', 'minor')),
    ADD COLUMN IF NOT EXISTS cluster_id UUID REFERENCES dead_end_clusters(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS cluster_key TEXT,
    ADD COLUMN IF NOT EXISTS fix_effectiveness TEXT DEFAULT 'untested' CHECK (fix_effectiveness IN ('worked', 'failed', 'untested')),
    ADD COLUMN IF NOT EXISTS fix_outcome_notes TEXT;

CREATE INDEX IF NOT EXISTS idx_dead_ends_cluster ON dead_end_summaries(cluster_id);
CREATE INDEX IF NOT EXISTS idx_dead_ends_severity ON dead_end_summaries(severity);
