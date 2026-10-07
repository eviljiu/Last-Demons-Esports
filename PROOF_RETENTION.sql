-- Run once in Supabase SQL Editor before enabling the scheduled cleanup.
-- No files or match results are deleted by this migration.
CREATE INDEX IF NOT EXISTS submissions_retention_idx
ON public.submissions (timestamp, id)
WHERE status IN ('Approved', 'Rejected') AND photo_path <> '';
