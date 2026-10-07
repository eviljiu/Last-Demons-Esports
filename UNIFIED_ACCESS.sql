-- Run once in Supabase SQL Editor BEFORE deploying the updated Edge Functions.
BEGIN;
LOCK TABLE public.push_subscriptions IN ACCESS EXCLUSIVE MODE;
-- Only the trusted server may read or change delivery identities.
ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.push_subscriptions FROM anon, authenticated;

-- Old versions allowed one token to be active for several roles/accounts.
-- Ambiguous tokens are disabled, never guessed to belong to a Founder.
UPDATE public.push_subscriptions
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE fcm_token IN (
  SELECT fcm_token FROM public.push_subscriptions
  WHERE is_active = TRUE GROUP BY fcm_token HAVING COUNT(*) > 1
);

DO $$
DECLARE c RECORD;
BEGIN
  FOR c IN SELECT conname FROM pg_constraint
    WHERE conrelid='public.push_subscriptions'::regclass AND contype='u'
    AND array_length(conkey, 1)=1 AND EXISTS (
      SELECT 1 FROM pg_attribute a WHERE a.attrelid=conrelid
      AND a.attnum=conkey[1] AND a.attname='fcm_token'
    )
  LOOP
    EXECUTE format('ALTER TABLE public.push_subscriptions DROP CONSTRAINT %I', c.conname);
  END LOOP;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS idx_push_identity_token_unique
ON public.push_subscriptions(identity_type, identity_id, fcm_token);
CREATE UNIQUE INDEX IF NOT EXISTS idx_push_one_active_identity
ON public.push_subscriptions(fcm_token) WHERE is_active = TRUE;

CREATE OR REPLACE FUNCTION public.ld_register_push_identity(
  p_identity_type TEXT, p_identity_id TEXT, p_token TEXT, p_user_agent TEXT
) RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  IF p_identity_type <> 'player' OR p_identity_type IS NULL
    OR p_identity_id IS NULL OR p_identity_id = ''
    OR p_token IS NULL OR p_token = '' OR length(p_token) > 4096
 THEN
    RAISE EXCEPTION 'Invalid push identity';
  END IF;
  IF p_identity_type = 'player' AND NOT EXISTS (
    SELECT 1 FROM public.players WHERE activision_id=p_identity_id AND status='Approved'
  ) THEN
    RAISE EXCEPTION 'Player not approved';
  END IF;
  -- Serialize concurrent registrations of the same browser token.
  PERFORM pg_advisory_xact_lock(hashtextextended(p_token, 0));
  UPDATE public.push_subscriptions SET is_active=FALSE, updated_at=CURRENT_TIMESTAMP
    WHERE fcm_token=p_token AND is_active=TRUE
    AND (identity_type<>p_identity_type OR identity_id<>p_identity_id);
  INSERT INTO public.push_subscriptions(identity_type,identity_id,fcm_token,user_agent,is_active,updated_at)
    VALUES(p_identity_type,p_identity_id,p_token,left(p_user_agent,500),TRUE,CURRENT_TIMESTAMP)
    ON CONFLICT(identity_type,identity_id,fcm_token) DO UPDATE
    SET user_agent=EXCLUDED.user_agent, is_active=TRUE, updated_at=CURRENT_TIMESTAMP;
END;
$$;
REVOKE ALL ON FUNCTION public.ld_register_push_identity(TEXT,TEXT,TEXT,TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.ld_register_push_identity(TEXT,TEXT,TEXT,TEXT) TO service_role;
-- Shared Founder subscriptions cannot identify an individual approved account.
UPDATE public.push_subscriptions SET is_active=FALSE, updated_at=CURRENT_TIMESTAMP
WHERE identity_type='founder';

-- The application authenticates through Streamlit, not Supabase client Auth.
-- Only its server connection/service_role may access these tables directly.
DO $$
DECLARE tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['players','submissions','announcements','notifications','seasons','founder_notifications'] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC, anon, authenticated', tbl);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO service_role', tbl);
  END LOOP;
END $$;
REVOKE ALL ON public.push_subscriptions FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.push_subscriptions TO service_role;
COMMIT;
