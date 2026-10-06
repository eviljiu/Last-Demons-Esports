# LAST DEMONS — FINAL 1.0 deep audit

## Scope
Full static review of the current app package, covering public registration/login, Founder and Player areas, PostgreSQL/Supabase Storage, leaderboard/rating, notifications/push integration, mobile UI, profile media and proof uploads.

## Final corrections
- Fixed cross-session stale reads: the per-session hot cache now includes the shared table-version key.
- Bounded the per-session hot cache for long-lived Player and Founder sessions.
- Player deletion is now one PostgreSQL transaction before best-effort Storage cleanup.
- Season rollover is now atomic (close current + create next season in one transaction).
- Migrates push token uniqueness from token-only to identity + identity_id + token, allowing the same browser/device to subscribe as different roles.
- Added hot-path partial/composite indexes for pending proofs, active Founder notifications and leaderboard reads.
- Founder proof archive queries capped to avoid rendering unbounded histories.
- Resolved application notifications auto-archive and no longer count as active alerts.
- Founder proof queue identifies sender, supports search and jumps to that player's proofs.
- Founder portrait keeps full image on mobile, shows Diablo_TV at the bottom and a full-height vertical FOUNDER rail.
- Obsolete Streamlit deployment URL is absent from the package.
- Push explanatory text is cleaned.

## Retained functionality verified
- Registration + approval + Player login.
- Separate Founder route/auth and 30-day signed remember-device flow.
- Roles and LD Player display mapping while preserving Academy internally.
- Top Fragger, placement-based Win Rate and rating multiplier model.
- Season/month leaderboards and progression chart.
- Proof upload validation, 50 MB raw cap, pixel guard, WebP optimization and orphan cleanup.
- Profile avatar/banner validation, 15 MB cap, pixel guard, WebP optimization and replacement cleanup.
- Founder notifications/archive, candidate/proof badges and contextual navigation.
- Player notifications, profile, card, Performance Center and announcements.
- Shared PostgreSQL connection pool (max 20) and 8s statement timeout.
- No duplicate Python function definitions; all Python files parse and compile.
- No SELECT * queries.

- Remember-device token expiry verified at `REMEMBER_DAYS = 30` for both Player and Founder flows.
