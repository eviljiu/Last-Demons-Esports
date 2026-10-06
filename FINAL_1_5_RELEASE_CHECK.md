# LAST DEMONS FINAL 1.5 — Release Candidate Audit

Full regression pass over the current consolidated package.

Verified/fixed:
- All Python files parse and compile; no duplicate Python function definitions.
- PostgreSQL Prove Player DISTINCT/ORDER BY bug is absent; grouped query is used.
- Cross-session cache keys include shared table versions; per-session cache is bounded.
- PostgreSQL pool remains max 20 with 8s statement timeout.
- Player deletion and season switch use transactions.
- Founder application notifications auto-archive after approve/reject.
- Founder active notifications now have explicit Archive and Delete actions; archived notifications have permanent Delete.
- Red sidebar count is restored.
- Founder portrait retains Diablo_TV, full-height F/O/U/N/D/E/R rail and mobile contain/no-crop rules.
- Proof sender overview/search retained.
- Proof upload 50MB/pixel validation and profile 15MB/pixel validation retained.
- Remember-device remains 30 days.
- Obsolete Streamlit deployment URL is absent.
- Firebase activation page JavaScript was rebuilt cleanly: click handler exists, immediate status feedback exists, no duplicate else syntax regression.
- register-push does explicit lookup/update/insert and contains no upsert/onConflict dependency.
- Firebase hosting JSON parses successfully and service worker messaging remains present.

This is a static/package audit. Live Firebase permission behavior and Supabase execution still depend on the deployed browser/device and server configuration.
