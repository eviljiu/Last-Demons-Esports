"""Hourly server-side proof retention. Default is a non-destructive preview."""
import argparse
import json
import os
import time
from urllib.parse import unquote, urlsplit, quote

ELIGIBLE = "status IN ('Approved','Rejected') AND timestamp <= CURRENT_TIMESTAMP - INTERVAL '72 hours' AND photo_path <> ''"


def object_key(photo_url, base_url, bucket):
    actual, base = urlsplit(photo_url), urlsplit(base_url)
    prefix = '/storage/v1/object/public/' + quote(bucket, safe='') + '/'
    if (actual.scheme != 'https' or actual.netloc != base.netloc
            or actual.query or actual.fragment or not actual.path.startswith(prefix)):
        raise ValueError('Unrecognized proof URL')
    key = unquote(actual.path[len(prefix):])
    if not key.startswith('proofs/') or any(p in ('', '.', '..') for p in key.split('/')) or '\\' in key:
        raise ValueError('Not a proof object')
    return key


def delete_image(session, base_url, bucket, key):
    # Use Storage API: deleting storage.objects via SQL would leave file bytes behind.
    response = session.delete(
        base_url + '/storage/v1/object/' + quote(bucket, safe=''),
        json={'prefixes': [key]}, timeout=(5, 20), allow_redirects=False,
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError('Storage deletion failed')
    # Supabase batch removal is idempotent, including an already absent object.


def run(conn, session, base_url, bucket, apply=False, limit=100, budget=180):
    totals = dict(eligible=0, deleted=0, failed=0, skipped=0)
    started = time.monotonic()
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM public.submissions WHERE ' + ELIGIBLE + ' ORDER BY timestamp,id LIMIT %s', (limit,))
        ids = [row[0] for row in cur.fetchall()]
    conn.commit()
    totals['eligible'] = len(ids)
    for sid in ids:
        if time.monotonic() - started >= budget:
            break
        try:
            with conn.cursor() as cur:
                # Hold the row lock through removal: it cannot become Pending mid-delete.
                cur.execute('SELECT photo_path FROM public.submissions WHERE id=%s AND ' + ELIGIBLE + ' FOR UPDATE SKIP LOCKED', (sid,))
                row = cur.fetchone()
                if not row:
                    totals['skipped'] += 1
                else:
                    key = object_key(row[0], base_url, bucket)
                    if apply:
                        delete_image(session, base_url, bucket, key)
                        # Keep the submission and all its statistics; NOT NULL uses empty string.
                        cur.execute("UPDATE public.submissions SET photo_path='' WHERE id=%s", (sid,))
            conn.commit()
            if row and apply:
                totals['deleted'] += 1
        except Exception:
            conn.rollback()
            totals['failed'] += 1
            # Never log URLs, player identities, database credentials or service keys.
            print(json.dumps({'submission_id': sid, 'error': 'cleanup_failed_retry_next_run'}))
    return totals


def main():
    import psycopg2
    import requests
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    required = ('DATABASE_URL', 'SUPABASE_URL', 'SUPABASE_SERVICE_KEY', 'SUPABASE_BUCKET')
    if any(not os.environ.get(k, '').strip() for k in required):
        raise SystemExit('Configure all four cleanup secrets before running.')
    base_url = os.environ['SUPABASE_URL'].strip().rstrip('/')
    if urlsplit(base_url).scheme != 'https':
        raise SystemExit('SUPABASE_URL must use HTTPS.')
    conn = psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require', connect_timeout=10,
        application_name='ld_proof_cleanup', options='-c statement_timeout=8000 -c lock_timeout=2000 -c idle_in_transaction_session_timeout=60000')
    try:
        with requests.Session() as session:
            key = os.environ['SUPABASE_SERVICE_KEY'].strip()
            session.headers.update({'Authorization': 'Bearer ' + key, 'apikey': key})
            result = run(conn, session, base_url, os.environ['SUPABASE_BUCKET'].strip(), args.apply)
            print(json.dumps(dict(result, mode='apply' if args.apply else 'preview')))
            if result['failed']:
                raise SystemExit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Cleanup failed. Check connectivity, configuration and permissions; no credentials logged.')
