# LAST DEMONS ESPORTS — V2.1 Cloud

Versione pronta per GitHub + Streamlit Community Cloud.

## 1. Crea il progetto Supabase
1. Crea un nuovo progetto Supabase.
2. In **Storage** crea un bucket chiamato `proof-screenshots`.
3. Imposta il bucket come **Public**: le immagini sono mostrate nell'area Founder tramite URL pubblico.
4. In Supabase copia:
   - Project URL
   - `service_role` key (non la anon key)
   - PostgreSQL connection string / pooler connection string.

> La service_role key è un segreto: non inserirla mai nel repository GitHub.

## 2. Carica questa cartella su GitHub
Nel repository devono esserci almeno:

- `app.py`
- `requirements.txt`
- `.gitignore`
- `.streamlit/config.toml`

`secrets.toml.example` è solo un modello e non contiene credenziali reali.

## 3. Configura Streamlit Cloud
Crea l'app da GitHub e usa `app.py` come Main file.

Poi vai in **App → Settings → Secrets** e inserisci:

```toml
FOUNDER_PASSWORD = "la-tua-password-founder"
DATABASE_URL = "la-connection-string-postgresql-di-supabase"
SUPABASE_URL = "https://PROJECT_REF.supabase.co"
SUPABASE_SERVICE_KEY = "la-tua-service-role-key"
SUPABASE_BUCKET = "proof-screenshots"
```

Salva i Secrets e riavvia/redeploya l'app.

## 4. Persistenza
Questa versione NON salva i dati importanti sul disco temporaneo di Streamlit:

- Player, login, candidature e statistiche → PostgreSQL Supabase
- Screenshot → Supabase Storage
- Password player → hash PBKDF2, non testo in chiaro
- Password Founder e chiavi cloud → Streamlit Secrets

In questo modo un normale redeploy di Streamlit non elimina il database o gli screenshot.

## Nota migrazione V2 locale
Il vecchio file `last_demons.db` locale non viene automaticamente copiato in Supabase.
La V2.1 crea le tabelle cloud automaticamente al primo avvio.
