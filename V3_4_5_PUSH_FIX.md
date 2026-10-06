# V3.4.5 Push registration fix

Root cause of HTTP 400 confirmed:
1. Firebase Hosting companion sends `fcm_token`, while the old Edge Function expected `token`.
2. Streamlit signs `identity_type` / `identity_id`, while the old Edge Function validated `typ` / `sub`.

The updated `register-push` accepts the current names and legacy names during rollout.
CORS is restricted to https://last-demons.web.app.
No secret values are included.

Deploy only `supabase/functions/register-push/index.ts` to Supabase Edge Functions, with Verify JWT OFF.
No Firebase Hosting redeploy is required for this fix.
