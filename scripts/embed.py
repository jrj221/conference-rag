"""Generate OpenAI embeddings for every sentence and save them to disk (NOT to the database yet).

Why disk first: if the database step fails, you don't pay OpenAI a second time.

Output (scripts/output/):
    sentence_rows.json   [{"id", "talk_id", "sentence"}, ...]  in a fixed order
    embeddings.f32       raw float32 values; row i = embedding of sentence_rows[i] (1536 floats each)

Resumable: if interrupted, re-run and it continues from where embeddings.f32 stops.

Usage:
    python3 scripts/embed.py --limit 500   # smoke test on 500 sentences
    python3 scripts/embed.py               # everything
"""
import argparse
import array
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "output"
MODEL = "text-embedding-3-small"
DIMS = 1536
BATCH = 500  # sentences per OpenAI request (API allows up to 2048)

public = json.loads((ROOT / "config.public.json").read_text())
secret = json.loads((ROOT / "config.secret.json").read_text())


def http_json(url: str, headers: dict, body=None, retries=5):
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                     headers=headers, method="POST" if body else "GET")
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:300]
            if e.code not in (429, 500, 502, 503) or attempt == retries:
                raise SystemExit(f"{url} -> {e.code} {detail}")
        except (TimeoutError, urllib.error.URLError):
            if attempt == retries:
                raise
        wait = 2 ** attempt
        print(f"  retry {attempt} in {wait}s")
        time.sleep(wait)


def load_sentence_rows() -> list[dict]:
    """Pull (id, talk_id, sentence) from Supabase once, then reuse the saved file so row order never changes."""
    rows_file = OUT / "sentence_rows.json"
    if rows_file.exists():
        return json.loads(rows_file.read_text())
    key = secret["SUPABASE_SERVICE_KEY"]
    headers = {"apikey": key}
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    rows, last_id = [], 0
    while True:  # keyset pagination: next page = ids greater than the last one we saw
        page = http_json(f"{public['SUPABASE_URL']}/rest/v1/sentence_embeddings"
                         f"?select=id,talk_id,sentence&id=gt.{last_id}&order=id&limit=1000", headers)
        if not page:
            break
        rows += page
        last_id = page[-1]["id"]
    rows_file.write_text(json.dumps(rows, ensure_ascii=False))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="only embed the first N sentences (smoke test)")
    args = parser.parse_args()

    rows = load_sentence_rows()
    target = min(len(rows), args.limit) if args.limit else len(rows)

    emb_file = OUT / "embeddings.f32"
    done = emb_file.stat().st_size // (DIMS * 4) if emb_file.exists() else 0
    with open(emb_file, "ab") as f:
        f.truncate(done * DIMS * 4)  # drop any half-written row from a crash
    print(f"{len(rows)} sentences in DB; embedding up to {target}; {done} already done")

    headers = {"Authorization": f"Bearer {secret['OPENAI_API_KEY']}", "Content-Type": "application/json"}
    tokens = 0
    with open(emb_file, "ab") as f:
        for start in range(done, target, BATCH):
            batch = rows[start : min(start + BATCH, target)]
            resp = http_json("https://api.openai.com/v1/embeddings", headers,
                             {"model": MODEL, "input": [r["sentence"] for r in batch]})
            data = sorted(resp["data"], key=lambda d: d["index"])
            assert len(data) == len(batch)
            vals = array.array("f")
            for d in data:
                assert len(d["embedding"]) == DIMS
                vals.extend(d["embedding"])
            vals.tofile(f)
            f.flush()
            tokens += resp["usage"]["total_tokens"]
            print(f"Embedded {start + len(batch)}/{target}  (~${tokens * 0.02 / 1e6:.4f} so far)")
    print("Done.")


if __name__ == "__main__":
    main()
