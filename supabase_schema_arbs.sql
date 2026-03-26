-- Arb tracking table
CREATE TABLE IF NOT EXISTS arb_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id TEXT UNIQUE NOT NULL,
    sport TEXT NOT NULL,
    sport_key TEXT NOT NULL,
    game TEXT NOT NULL,
    market TEXT NOT NULL,
    margin_pct DECIMAL(10, 4) NOT NULL,
    books JSONB NOT NULL,  -- Array of book names involved
    legs JSONB NOT NULL,   -- Full leg details
    sent_at TIMESTAMPTZ DEFAULT NOW(),

    -- User feedback tracking
    feedback_positive INTEGER DEFAULT 0,
    feedback_negative INTEGER DEFAULT 0,
    feedback_users JSONB DEFAULT '[]'::jsonb,  -- Array of user IDs who provided feedback

    -- Status tracking
    status TEXT DEFAULT 'active',  -- active, verified, failed, expired

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_arb_alerts_sent_at ON arb_alerts(sent_at DESC);
CREATE INDEX idx_arb_alerts_sport_key ON arb_alerts(sport_key);
CREATE INDEX idx_arb_alerts_status ON arb_alerts(status);
CREATE INDEX idx_arb_alerts_margin ON arb_alerts(margin_pct DESC);

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_arb_alerts_updated_at
    BEFORE UPDATE ON arb_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security (optional - adjust as needed)
ALTER TABLE arb_alerts ENABLE ROW LEVEL SECURITY;

-- Allow public read access to stats (for public dashboard)
CREATE POLICY "Allow public read access for stats"
    ON arb_alerts FOR SELECT
    USING (true);

-- Only allow inserts/updates from service role
CREATE POLICY "Allow service role full access"
    ON arb_alerts
    USING (auth.role() = 'service_role');
