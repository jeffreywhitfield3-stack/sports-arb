-- User profiles for regional optimization
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'discord' or 'telegram'
    state TEXT,  -- US state code (NY, NJ, PA, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, platform)
);

-- Index for quick lookups
CREATE INDEX idx_user_profiles_state ON user_profiles(state);
CREATE INDEX idx_user_profiles_platform ON user_profiles(platform);

-- Auto-update updated_at
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable Row Level Security
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Allow public read/write (for bot commands)
CREATE POLICY "Allow public access"
    ON user_profiles
    USING (true)
    WITH CHECK (true);
