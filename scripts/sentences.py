"""Split every talk into sentences and load them into `sentence_embeddings` (embedding left empty).

Also saves scripts/output/sentences.json so you can inspect the result.
Re-running replaces all existing sentence rows (embeddings included), so run it BEFORE the embedding steps.

Usage:
    python3 scripts/sentences.py --dry-run   # split + write sentences.json only, no database changes
    python3 scripts/sentences.py             # split and load into Supabase
"""
import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "output"
BATCH_SIZE = 500
MIN_YEAR = 2015  # must match import.py
MIN_CHARS = 20  # drops fragments like "Amen." that carry no searchable meaning

# Periods that do NOT end a sentence ("Elder M. Russell Ballard", "D&C 4:1", "Jr.")
ABBREVIATIONS = {"mr", "mrs", "ms", "dr", "jr", "sr", "st", "vs", "etc", "no", "vol", "ch", "chap", "pres", "bro", "sis"}

# Split after . ! ? (optionally followed by a closing quote/bracket) when the next sentence starts
BOUNDARY = re.compile(r"(?<=[.!?])[\"”’)\]]*\s+(?=[\"“‘(\[]*[A-Z0-9])")


def split_sentences(text: str) -> list[str]:
    pieces, start = [], 0
    for m in BOUNDARY.finditer(text):
        candidate = text[start : m.start()]
        last_word = re.findall(r"[A-Za-z]+\.?$", candidate)
        is_abbrev = last_word and last_word[0].rstrip(".").lower() in ABBREVIATIONS
        is_initial = re.search(r"(?:^|\s)[A-Z]\.$", candidate)  # "M. Russell Ballard"
        if is_abbrev or is_initial:
            continue
        pieces.append(text[start : m.end()].strip())
        start = m.end()
    pieces.append(text[start:].strip())
    return [re.sub(r"\s+", " ", p) for p in pieces if len(p) >= MIN_CHARS]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    talks = json.loads((OUT / "talks.json").read_text())
    sentences = []
    for t in talks:
        if int(t["conference"][:4]) < MIN_YEAR:
            continue
        for n, s in enumerate(split_sentences(t["text"])):
            sentences.append({"url": t["url"], "position": n, "sentence": s})
    print(f"{len(talks)} talks -> {len(sentences)} sentences ({len(sentences) / len(talks):.0f} per talk)")

    if args.dry_run:
        (OUT / "sentences.json").write_text(json.dumps(sentences, indent=2, ensure_ascii=False), encoding="utf-8")
        print("Dry run: wrote sentences.json only.")
        return

    public = json.loads((ROOT / "config.public.json").read_text())
    key = json.loads((ROOT / "config.secret.json").read_text())["SUPABASE_SERVICE_KEY"]
    base = f"{public['SUPABASE_URL']}/rest/v1"
    headers = {"apikey": key, "Content-Type": "application/json"}
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"

    def call(method: str, path: str, body=None, extra=None):
        req = urllib.request.Request(
            base + path, data=json.dumps(body).encode() if body is not None else None,
            headers={**headers, **(extra or {})}, method=method,
        )
        for attempt in range(1, 5):  # a stalled connection shouldn't hang the whole load
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read() or "null")
            except (TimeoutError, urllib.error.URLError) as e:
                if attempt == 4:
                    raise
                print(f"  retry {attempt} after {e!r}")

    # url -> talk id, so each sentence can point at its talk
    rows = call("GET", "/talks?select=id,url&limit=10000")
    talk_id = {r["url"]: r["id"] for r in rows}
    missing = {s["url"] for s in sentences} - talk_id.keys()
    if missing:
        raise SystemExit(f"{len(missing)} talks aren't in the database yet. Run import.py first.")

    records = [{"talk_id": talk_id[s["url"]], "sentence": s["sentence"]} for s in sentences]
    (OUT / "sentences.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    call("DELETE", "/sentence_embeddings?id=gt.0", extra={"Prefer": "return=minimal"})
    for i in range(0, len(records), BATCH_SIZE):
        call("POST", "/sentence_embeddings", records[i : i + BATCH_SIZE], {"Prefer": "return=minimal"})
        print(f"Loaded {min(i + BATCH_SIZE, len(records))}/{len(records)}")
    print("Done.")


if __name__ == "__main__":
    main()
