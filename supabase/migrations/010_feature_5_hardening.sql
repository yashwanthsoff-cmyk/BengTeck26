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
