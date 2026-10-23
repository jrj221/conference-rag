"""Attach the vectors saved by embed.py to the sentences now in the database, then build the vector index.

Works even after the database was rebuilt (new ids): it re-derives the sentence order from talks.json,
checks it matches embeddings.f32 row-for-row, keeps only years >= MIN_YEAR, and pairs those with the
database rows in id order (sentences.py inserted them in that same order).

Reads:  scripts/output/talks.json, sentence_rows.json, embeddings.f32
Needs:  SUPABASE_SERVICE_KEY, SUPABASE_ACCESS_TOKEN in config.secret.json
Safe to re-run.
"""
import array
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "output"
sys.path.insert(0, str(ROOT / "scripts"))
from sentences import MIN_YEAR, split_sentences  # noqa: E402

DIMS = 1536
BATCH = 100  # ~1.5 MB of JSON per request
LISTS = 50   # IVFFlat clusters; ~rows/1000 is the usual rule of thumb

public = json.loads((ROOT / "config.public.json").read_text())
secret = json.loads((ROOT / "config.secret.json").read_text())
key = secret["SUPABASE_SERVICE_KEY"]
base = f"{public['SUPABASE_URL']}/rest/v1"
headers = {"apikey": key, "Content-Type": "application/json"}
if not key.startswith("sb_"):
    headers["Authorization"] = f"Bearer {key}"


def call(method, url, body=None, hdrs=None, timeout=120, retries=4):
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers=hdrs or headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read() or "null")
        except urllib.error.HTTPError as e:
            if (e.code < 500 and e.code != 429) or attempt == retries:
                raise SystemExit(f"{e.code} {e.read().decode()[:300]}")
        except (TimeoutError, urllib.error.URLError):
            if attempt == retries:
                raise
        time.sleep(2 ** attempt)


# 1. Re-derive every sentence in embed order and confirm it matches the saved vectors
talks = json.loads((OUT / "talks.json").read_text())
all_sentences = [(int(t["conference"][:4]), s) for t in talks for s in split_sentences(t["text"])]
saved = json.loads((OUT / "sentence_rows.json").read_text())
vectors = array.array("f")
vectors.frombytes((OUT / "embeddings.f32").read_bytes())
if not (len(all_sentences) == len(saved) == len(vectors) // DIMS
        and all(a[1] == b["sentence"] for a, b in zip(all_sentences, saved))):
    raise SystemExit("talks.json, sentence_rows.json and embeddings.f32 don't line up. Re-run embed.py.")
kept = [(i, s) for i, (year, s) in enumerate(all_sentences) if year >= MIN_YEAR]

# 2. Fetch the database rows in id order and pair them with the kept vectors
db_rows, last = [], 0
while True:
    page = call("GET", f"{base}/sentence_embeddings?select=id,talk_id,sentence&id=gt.{last}&order=id&limit=1000")
    if not page:
        break
    db_rows += page
    last = page[-1]["id"]
if len(db_rows) != len(kept) or any(r["sentence"] != s for r, (_, s) in zip(db_rows, kept)):
    raise SystemExit(f"Database has {len(db_rows)} sentences but expected {len(kept)} (years >= {MIN_YEAR}). Re-run sentences.py.")
print(f"{len(db_rows)} sentences paired with their vectors")

# 3. Write vectors (upsert needs the NOT NULL columns too; pgvector accepts the "[...]" text form)
up = {**headers, "Prefer": "resolution=merge-duplicates,return=minimal"}
for start in range(0, len(db_rows), BATCH):
    batch = []
    for r, (i, _) in zip(db_rows[start : start + BATCH], kept[start : start + BATCH]):
        vec = vectors[i * DIMS : (i + 1) * DIMS]
        batch.append({**r, "embedding": "[" + ",".join(f"{x:.7g}" for x in vec) + "]"})
    call("POST", f"{base}/sentence_embeddings?on_conflict=id", batch, up)
    if (start // BATCH) % 20 == 0 or start + BATCH >= len(db_rows):
        print(f"Loaded {min(start + BATCH, len(db_rows))}/{len(db_rows)}")
print("Vectors loaded. Run scripts/build_index.py next.")
