CREATE TABLE IF NOT EXISTS push_subscriptions (
  id BIGSERIAL PRIMARY KEY,
  identity_type TEXT NOT NULL CHECK (identity_type IN ('player','founder')),
  identity_id TEXT NOT NULL,
  fcm_token TEXT UNIQUE NOT NULL,
  user_agent TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_push_identity_active
ON push_subscriptions(identity_type, identity_id, is_active);
