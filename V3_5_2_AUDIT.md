# V3.5.2 — Player + Founder audit

The optimization pass applies to both sides of the application.

- Shared PostgreSQL pool and statement timeout retained.
- Cross-session table-version cache invalidation retained/fixed.
- Per-session hot cache bounded to prevent growth in long-lived Player and Founder sessions.
- Mobile controls/forms polished for both Player and Founder.
- Player notification/profile/submission flows compile and retain cache invalidation.
- Founder notification/archive/candidate/proof flows compile and retain cache invalidation.
- Proof sender overview/search retained.
- Founder portrait Diablo_TV/full-height vertical label retained.
- No duplicate Python function definitions.
- All Python files parse and compile.
