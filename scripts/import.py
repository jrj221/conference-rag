"""Load scripts/output/talks.json into the Supabase `talks` table.

Needs:  config.public.json -> SUPABASE_URL
        config.secret.json -> SUPABASE_SERVICE_KEY  (Project Settings > API > service_role / secret key)

The service key bypasses RLS, which is why it's only used here, never in the browser.
Safe to re-run: rows are upserted on `url`, so nothing gets duplicated.
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATCH_SIZE = 50
MIN_YEAR = 2015  # free-tier storage is small; skip older conferences

public = json.loads((ROOT / "config.public.json").read_text())
secret = json.loads((ROOT / "config.secret.json").read_text())
talks = json.loads((ROOT / "scripts" / "output" / "talks.json").read_text())

endpoint = f"{public['SUPABASE_URL']}/rest/v1/talks?on_conflict=url"
key = secret["SUPABASE_SERVICE_KEY"]
headers = {
    "apikey": key,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}
# Legacy service_role keys are JWTs and go in Authorization too; new sb_secret_ keys are not JWTs.
if not key.startswith("sb_"):
    headers["Authorization"] = f"Bearer {key}"

# Only send columns that exist in the table (the scraper also records `conference`)
rows = [{k: t[k] for k in ("title", "speaker", "url", "text")} for t in talks if int(t["conference"][:4]) >= MIN_YEAR]

for i in range(0, len(rows), BATCH_SIZE):
    batch = rows[i : i + BATCH_SIZE]
    req = urllib.request.Request(endpoint, data=json.dumps(batch).encode(), headers=headers, method="POST")
    try:
        urllib.request.urlopen(req).close()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Batch starting at {i} failed: {e.code} {e.read().decode()}")
    print(f"Imported {min(i + BATCH_SIZE, len(rows))}/{len(rows)}")

print("Done.")
