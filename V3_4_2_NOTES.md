V3.4.2
- Firebase Hosting push companion connected at https://last-demons.web.app/
- Player/Founder push activation now uses a 5-minute HMAC-signed assertion.
- Assertion is passed in URL fragment (#a=...), so it is not sent in the Firebase Hosting HTTP request.
- No Firebase Web API key or service worker is hosted by Streamlit.
- Existing Supabase register-push/send-push Edge Functions retained.
- Founder mobile portrait, vertical FOUNDER treatment, redesigned operational alerts and cache regex fix retained.
