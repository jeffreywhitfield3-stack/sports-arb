-- subscriptions table for Stripe payment tracking
-- Run this in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, platform)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_customer ON subscriptions(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_active ON subscriptions(active, platform);
CREATE INDEX IF NOT EXISTS idx_user_platform ON subscriptions(user_id, platform);

-- Enable Row Level Security
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Policy: Allow public read access for subscription checks
CREATE POLICY "Allow public read access" ON subscriptions
    FOR SELECT
    USING (true);

-- Policy: Allow service role to insert/update
CREATE POLICY "Allow service role full access" ON subscriptions
    FOR ALL
    USING (true);

COMMENT ON TABLE subscriptions IS 'Tracks user subscriptions via Stripe';
COMMENT ON COLUMN subscriptions.user_id IS 'Discord or Telegram user ID';
COMMENT ON COLUMN subscriptions.platform IS 'discord or telegram';
COMMENT ON COLUMN subscriptions.stripe_customer_id IS 'Stripe customer ID for billing portal';
COMMENT ON COLUMN subscriptions.stripe_subscription_id IS 'Stripe subscription ID';
COMMENT ON COLUMN subscriptions.active IS 'True if subscription is active';
