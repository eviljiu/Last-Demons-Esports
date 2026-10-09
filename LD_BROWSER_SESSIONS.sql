-- Execute once in Supabase SQL Editor before deploying the app.
CREATE TABLE IF NOT EXISTS public.ld_browser_sessions (
 token_hash text PRIMARY KEY,
 player_id text NOT NULL,
 auth_fingerprint text NOT NULL,
 expires_at timestamptz NOT NULL,
 revoked_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ld_browser_sessions_expiry ON public.ld_browser_sessions(expires_at);
ALTER TABLE public.ld_browser_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.ld_browser_sessions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ld_browser_sessions TO service_role;
-- Optional scheduled cleanup: DELETE FROM public.ld_browser_sessions WHERE expires_at < now() - interval '7 days';
