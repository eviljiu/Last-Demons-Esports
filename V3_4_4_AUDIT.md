# V3.4.4 deep audit
- AST parse and Python compile passed.
- Proof uploads now validate real image bytes, guard pixel count, normalize EXIF and optimize to WebP.
- Uploaded proof is deleted if the database INSERT fails.
- Partial avatar/banner uploads are cleaned up if a later upload or DB update fails.
- Player removal also clears notifications and player push subscriptions; Storage cleanup happens after DB removal.
- Player sidebar counters use one aggregate DB round trip.
- Player profile history is bounded to the latest 500 records for predictable rendering cost.
- Cache invalidation, DB pool/timeout, PBKDF2 password verification, actionable badges/navigation, Firebase companion, profile media and Founder mobile UI verified.
- Secret scan passed: no private Firebase key, Supabase secret key, PostgreSQL credential URL or Google API key.
