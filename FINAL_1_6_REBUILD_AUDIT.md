# FINAL 1.6 — rebuild from V3.5.2

Base used: LAST_DEMONS_V3_5_2_PLAYER_FOUNDER_OPTIMIZED.

Post-3.5.2 changes reapplied deliberately:
- robust current Streamlit return URL;
- Founder portrait full-height F O U N D E R;
- transactional player deletion and season rollover;
- Founder notification archive/delete controls;
- red sidebar counters;
- hot-path DB indexes;
- proof history cap;
- Firebase activation-page click fix and clearer status/error display;
- push registration flow without upsert/onConflict.

Corrections made during rebuild:
- Prove Player now lists every Activision ID from players, plus historical IDs present only in submissions.
- legacy fcm_token UNIQUE cleanup targets only the old single-column constraint; it cannot drop the composite identity/token constraint.
- register-push rebuilt from scratch with makeResponse(), removing the identifier implicated by the live `ReferenceError: response is not defined`.
- register-push uses explicit lookup -> update/insert, with duplicate-race retry.

Static checks passed for Python syntax/compile, duplicate Python functions, Firebase click-handler structure, and push-flow source invariants.
Live Firebase/Supabase behavior still requires one deployment test.
