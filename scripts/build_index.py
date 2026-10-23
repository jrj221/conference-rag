"""Build the IVFFlat vector index (kept separate: it's the step most likely to hit memory/time limits)."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
public = json.loads((ROOT / "config.public.json").read_text())
secret = json.loads((ROOT / "config.secret.json").read_text())
ref = public["SUPABASE_URL"].split("//")[1].split(".")[0]


def sql(query: str, timeout=300):
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{ref}/database/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {secret['SUPABASE_ACCESS_TOKEN']}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{e.code} {e.read().decode()[:300]}")


t = time.time()
sql("set statement_timeout = 0; set maintenance_work_mem = '128MB'; "
    "create index if not exists sentence_embeddings_embedding_idx "
    "on sentence_embeddings using ivfflat (embedding halfvec_cosine_ops) with (lists = 50);")
print(f"Index built in {time.time() - t:.0f}s")
print(sql("select pg_size_pretty(pg_database_size(current_database())) as database_size"))
