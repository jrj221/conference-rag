"""Scrape General Conference talks (2010-2019) into scripts/output/talks.json.

Flow: decade index -> 20 conference pages -> every talk page -> {title, speaker, url, text}.
Pages are cached on disk, so re-running (or resuming after a failure) doesn't re-download.

Usage:
    python3 scripts/scrape.py              # everything
    python3 scripts/scrape.py --limit 3    # first 3 talks per conference (quick test)
"""
import argparse
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://beta.churchofjesuschrist.org"
INDEX_URL = f"{BASE}/study/general-conference/20102019?lang=eng"
DELAY_SECONDS = 0.5  # be polite to the server

OUT_DIR = Path(__file__).resolve().parent / "output"
CACHE_DIR = OUT_DIR / "cache"

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (CS452 class project RAG scraper)"


def fetch(url: str) -> str:
    """GET a page, using the on-disk cache when we've seen it before."""
    cache_file = CACHE_DIR / (re.sub(r"[^a-zA-Z0-9]+", "_", url) + ".html")
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    cache_file.write_text(resp.text, encoding="utf-8")
    time.sleep(DELAY_SECONDS)
    return resp.text


def conference_urls(index_html: str) -> list[str]:
    """Links like /study/general-conference/2019/10?lang=eng (one per conference)."""
    paths = set(re.findall(r'href="(/study/general-conference/\d{4}/(?:04|10)\?lang=eng)"', index_html))
    return [BASE + p for p in sorted(paths)]


def talk_urls(conference_html: str) -> list[str]:
    """Talk links look like .../2019/10/12vinson or .../2015/04/choose-to-believe.
    Session index pages ('saturday-morning-session', 'womens-session') are filtered out."""
    paths = re.findall(r'href="(/study/general-conference/\d{4}/(?:04|10)/[^"/?]+\?lang=eng)"', conference_html)
    paths = [p for p in paths if "-session" not in p]
    return [BASE + p for p in dict.fromkeys(paths)]  # de-dupe, keep page order


def tidy(text: str) -> str:
    """get_text(" ") puts spaces around inline links/italics; remove the ones around punctuation."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([(\[“‘]) ", r"\1", text)       # "( 1 Nephi" -> "(1 Nephi"
    text = re.sub(r" ([)\]”’,.;:!?])", r"\1", text)  # "11:17 ;" -> "11:17;"
    return text.strip()


def parse_talk(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("h1")
    body = soup.select_one("div.body-block")
    if not title or not body:
        return None

    # Footnote markers are noise in the text
    for ref in body.select("a.note-ref, sup"):
        ref.decompose()

    paragraphs = [tidy(p.get_text(" ", strip=True)) for p in body.find_all("p")]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return None

    # No author => not a real talk (e.g. auditing report, sustaining of officers)
    author = soup.select_one("p.author-name")
    if not author:
        return None
    speaker = re.sub(r"^By\s+", "", author.get_text(" ", strip=True))

    year, month = re.search(r"/(\d{4})/(04|10)/", url).groups()
    return {
        "title": title.get_text(" ", strip=True),
        "speaker": speaker,
        "conference": f"{year}-{month}",
        "url": url.split("?")[0],
        "text": "\n\n".join(paragraphs),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="max talks per conference (for testing)")
    args = parser.parse_args()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    conferences = conference_urls(fetch(INDEX_URL))
    print(f"Found {len(conferences)} conferences")

    talks, skipped = [], []
    for conf_url in conferences:
        urls = talk_urls(fetch(conf_url))
        if args.limit:
            urls = urls[: args.limit]
        print(f"{conf_url.split('/')[-2]}/{conf_url.split('/')[-1].split('?')[0]}: {len(urls)} talks")
        for url in urls:
            try:
                talk = parse_talk(fetch(url), url)
            except requests.RequestException as e:
                print(f"  ! {url}: {e}")
                skipped.append(url)
                continue
            if talk:
                talks.append(talk)
            else:
                skipped.append(url)

    out_file = OUT_DIR / "talks.json"
    out_file.write_text(json.dumps(talks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(talks)} talks to {out_file}")
    if skipped:
        print(f"Skipped {len(skipped)} pages with no talk body:")
        for u in skipped:
            print("  ", u)


if __name__ == "__main__":
    main()
