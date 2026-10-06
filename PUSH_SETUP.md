# LAST DEMONS V3.4 — attivazione Push Firebase

La configurazione Web Firebase e la VAPID **pubblica** sono già integrate. Non mettere mai una private key in GitHub.

## 1. Firebase: crea Service Account
Firebase Console → Impostazioni progetto → Account di servizio → Genera nuova chiave privata.
Dal JSON usa SOLO questi valori per i secret Supabase:
- `client_email` → `FIREBASE_CLIENT_EMAIL`
- `private_key` → `FIREBASE_PRIVATE_KEY`
Il file JSON non va caricato su GitHub.

## 2. Genera due segreti casuali
Genera due stringhe casuali lunghe (almeno 32 byte):
- `PUSH_REGISTRATION_SECRET`
- `PUSH_SEND_SECRET`
Devono avere gli stessi valori in Streamlit Secrets e nei secret delle Edge Functions.

## 3. Supabase Edge Functions
Installa la Supabase CLI, collega il progetto e dalla cartella del repo esegui:

supabase functions deploy register-push --no-verify-jwt
supabase functions deploy send-push --no-verify-jwt

Imposta i secret Edge Functions:
- PUSH_REGISTRATION_SECRET
- PUSH_SEND_SECRET
- FIREBASE_PROJECT_ID=last-demons
- FIREBASE_CLIENT_EMAIL
- FIREBASE_PRIVATE_KEY

SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY sono forniti dall'ambiente Supabase alle funzioni.

## 4. Streamlit Secrets
Aggiungi:
PUSH_REGISTRATION_SECRET = "stesso valore Supabase"
PUSH_SEND_SECRET = "stesso valore Supabase"

## 5. Test
Apri Last Demons dal telefono → Notifiche → “ATTIVA NOTIFICHE PUSH”.
Accetta il permesso del browser. Poi approva/rifiuta una prova o genera una notifica: la notifica interna resta salvata e la push viene inviata in parallelo.

Nota iPhone/iPad: per le Web Push installa il sito nella Home e aprilo come web app prima di attivare le notifiche.
