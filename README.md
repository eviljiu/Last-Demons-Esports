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


## Novità V2.2
- Navigazione Founder e Player tramite menu a tendina.
- Accesso Founder rimosso dalla home pubblica.
- Accesso Founder riservato tramite `?founder=1`, per esempio:
  `https://NOME-APP.streamlit.app/?founder=1`
- Rimozione definitiva player dal pannello Founder.
- Foto profilo e banner caricabili dai player e salvati su Supabase Storage.
- Anteprima foto/banner nella gestione player Founder.

### Nota accesso Founder
Il parametro `?founder=1` nasconde l'ingresso amministrativo dalla home, ma la sicurezza
resta affidata alla password Founder salvata nei Secrets di Streamlit.


## V2.3
- Home pubblica con sola registrazione/verifica candidatura.
- Login Player mostrato soltanto quando la candidatura risulta Approved.
- Bacheca comunicazioni Founder.
- Notifiche player per candidatura, prove e cambio ruolo.
- Roster pubblico.
- Ruoli organizzazione Player / Coach / Manager.
- Stagioni con storico: nuova stagione senza cancellare i dati precedenti.
- Player Card pubblica condivisibile tramite `?player=ACTIVISION_ID`.
- Restano disponibili avatar, banner, rimozione player e accesso Founder tramite `?founder=1`.


## V2.4 — Leaderboard Edition
- Nuovo template esports dedicato alle classifiche.
- Podio grafico Top 3 con avatar e medaglie.
- Modalità Top Fragger / Win Rate.
- Filtri divisione Élite / Academy, stagione e mese.
- Classifica completa dal 4° posto in poi.
- Highlight del player loggato.
- Season Kill Leader e Season Win Rate Leader.
- Layout responsive per mobile.

## V2.4.1 Hotfix
- Corretto il NameError della funzione stagione.
- Navigazione Founder e Player verticale nella sidebar.
- Dashboard Founder ampliata: Operations Center, Top 5 organizzazione e attività recente.


## V2.4.2 Hotfix
- Corretto PostgreSQL InvalidColumnReference nell'Archivio Prove per Activision ID.


## V2.5 — Performance
- Cache breve (20s) per le letture PostgreSQL; invalidazione immediata dopo ogni modifica.
- Indici PostgreSQL per player, prove, leaderboard, notifiche e comunicazioni.
- Meno round-trip DB nella Founder Dashboard.
- Navigazione sidebar più compatta.
- Mantiene tutti gli hotfix e la Leaderboard Edition.

## V2.6 — Full Audit Hotfix
- Corretto bug critico V2.5: `get_db_connection()` inesistente, causa degli errori nelle sezioni Founder.
- Ripristinata l'esecuzione `init_db()` dopo il refactor performance.
- Ripristinate le funzioni `notify_player()` e `public_player_card()`.
- Cache DB resa compatibile con il comportamento originale di `db_query`.
- Ridotta la cache a 15 secondi e invalidata dopo le scritture.
- Mantenuti indici PostgreSQL, leaderboard, menu verticali e hotfix archivio prove.
- Controllo statico delle chiamate a funzioni: nessun riferimento globale mancante.


## V2.7 — Speed + Full Player Audit
- `init_db()` ora viene eseguito una sola volta per processo Streamlit invece che a ogni cambio pagina.
- Cache letture PostgreSQL portata a 45 secondi; ogni scrittura la invalida immediatamente.
- Nuovi indici per login/player, prove personali e cronologia.
- Audit statico completo delle 6 sezioni Founder e delle 6 sezioni Player.
- Verificate funzioni mancanti, sintassi, compilazione, query archivio e leaderboard.
- Nessuna modifica richiesta ai Secrets o a Supabase.

## V2.8
- Accesso Player sempre visibile ma utilizzabile solo dagli Approved.
- Login rilegge lo stato aggiornato dal DB.
- Ruoli/divisioni con badge tipografici.
- Gestione Player Founder compatta con ricerca e selettore, adatta a roster grandi.
- Avatar/banner ridimensionati nella gestione.


## V2.8.1 — Storage Upload Hotfix
- Corretto crash `requests.exceptions.HTTPError` durante Carica Prova.
- Upload Supabase Storage ora gestisce 401/403, 404, 409 e problemi di rete.
- Errori Storage vengono mostrati nella pagina senza mandare in crash l'app.
- Validazione di SUPABASE_URL, SUPABASE_SERVICE_KEY e SUPABASE_BUCKET.
- URL pubblico dell'oggetto generato in modo sicuro.

## V2.9 — Remember Device
- Player login can remember the browser/device for 30 days.
- Password is never stored; browser stores only a signed HMAC token with expiration.
- Every restored session rechecks that the player is still Approved.
- Player logout removes the remembered-device token.
- Optional hardening: add a random `AUTH_SECRET` to Streamlit Secrets.

## V2.9.1 — Remember Founder Device
- Anche il login Founder può ricordare il browser/dispositivo per 30 giorni.
- La password Founder non viene memorizzata nel browser.
- Viene usato un token HMAC firmato e con scadenza.
- Il ripristino Founder funziona soltanto sulla route nascosta `?founder=1`.
- Logout Founder cancella il token persistente.

## V2.9.2 — Full Stability Audit
- Fix `validate_storage_config` mancante.
- Fix `safe_name` mancante.
- Fix import `Path` richiesto da Storage.
- Audit funzioni chiamate: nessun riferimento diretto mancante.
- Audit call-before-definition: superato.
- Verificati Storage, DB/cache, Player/Founder remember-device, leaderboard, notifiche, Player Card, stagioni e gestione player.

## V2.9.3 — Auth Token Hotfix
- Corretto `NameError: base64 is not defined` nel login Founder e Player.
- Verificati encode/decode dei token remember-device.
- Mantenuti i fix Storage e l'audit V2.9.2.

## V2.9.4 — Storage + Full Audit
- Supporto corretto per bucket con spazi come `Prove Screenshot`.
- URL Supabase Storage centralizzati e codificati.
- Audit completo funzioni e riferimenti diretti superato.

## V2.9.5 — Automatic Supabase Bucket Resolver
- Interroga `/storage/v1/bucket` con la Secret key e recupera il vero `id` del bucket.
- `SUPABASE_BUCKET` può corrispondere al nome o all'id; confronto case-insensitive.
- Upload prove, avatar/banner, URL pubblici e delete usano sempre l'id risolto.
- Resolver bucket in cache 5 minuti per non rallentare la navigazione.
- In caso di bucket non trovato mostra i bucket visibili senza esporre chiavi.
- Audit statico completo superato.
