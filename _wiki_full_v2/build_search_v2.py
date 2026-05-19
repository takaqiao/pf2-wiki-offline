"""Phase G: build offline full-text search index from parsed JSON.

Adapted from v1's build_search.py (lighter-weight; reads server-rendered HTML
via BeautifulSoup instead of wikitext + custom strip).

Reuses v1's sharded JSONP layout so the same search-app.js client works:
  _wiki_full_v2/index/titles.js
  _wiki_full_v2/index/shards/b_<XX>.js  (CJK bigram shards, ~64)
  _wiki_full_v2/index/shards/w_<L>.js   (Latin word shards, a-z + _)
  _wiki_full_v2/index/manifest.js

Run:
    .venv\\Scripts\\python.exe build_search_v2.py             # full
    .venv\\Scripts\\python.exe build_search_v2.py --limit 1000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent  # _wiki_full_v2/
SCRAPER_OUT = ROOT.parent / "pf2wiki-scraper" / "out_v2"
PARSED_DIR = SCRAPER_OUT / "parsed"
META_FILE = SCRAPER_OUT / "metadata.json"
INDEX_DIR = ROOT / "index"
SHARDS_DIR = INDEX_DIR / "shards"

STUB_BODY_THRESHOLD = 120

NS_TO_DIR = {
    0: "pages", 4: "project", 14: "category", 102: "pages", 3500: "data",
}

SKIP_TITLE_PREFIXES = (
    "Template:", "模板:", "File:", "文件:", "Module:", "模块:",
    "MediaWiki:", "Form:", "表单:",
)

EN_STOP = {"a", "an", "and", "or", "of", "to", "the", "in", "on", "at", "is",
           "as", "by", "for", "be", "it", "with", "from", "this", "that"}
ZH_STOP_CHARS = set("的了是在与和及或但因為为以及他她它我你们们之于而")

CJK_RANGE = (
    (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x2A6DF),
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'_-]{1,30}")
WHITESPACE_RE = re.compile(r"\s+")


def is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in CJK_RANGE)


def cjk_runs(text: str):
    runs, buf = [], []
    for ch in text:
        if is_cjk(ch):
            buf.append(ch)
        else:
            if buf:
                runs.append("".join(buf))
                buf = []
    if buf:
        runs.append("".join(buf))
    return runs


def cjk_bigrams(text: str):
    out = []
    for run in cjk_runs(text):
        if len(run) == 1:
            out.append(run)
            continue
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg[0] in ZH_STOP_CHARS and bg[1] in ZH_STOP_CHARS:
                continue
            out.append(bg)
    return out


def tokenize_latin(text: str):
    out = []
    for w in WORD_RE.findall(text):
        w = w.lower()
        if len(w) < 2 or w in EN_STOP:
            continue
        out.append(w)
    return out


def bigram_bucket(bg: str) -> str:
    h = hashlib.md5(bg.encode("utf-8")).digest()
    return f"{h[0]:02x}"


def word_bucket(w: str) -> str:
    c = w[0]
    return c if "a" <= c <= "z" else "_"


def safe_title_fn(t: str) -> str:
    t = t.replace(":", "_").replace("/", "__").replace("\\", "_")
    return re.sub(r'[*?"<>|]', "", t)


def determine_dir_and_bare(ns: int, title: str) -> tuple[str, str]:
    target = NS_TO_DIR.get(ns, "pages")
    bare = title
    if ":" in title:
        prefix, rest = title.split(":", 1)
        if prefix in {"Category", "Data", "分类", "数据", "Project", "Help", "Template", "File"}:
            bare = rest
    return target, bare


def page_href(ns: int, title: str) -> str:
    target_dir, bare = determine_dir_and_bare(ns, title)
    return f"{target_dir}/{urllib.parse.quote(safe_title_fn(bare))}.html"


def make_excerpt(text: str, max_len: int = 100) -> str:
    if not text:
        return ""
    t = text.strip()
    return t if len(t) <= max_len else t[:max_len].rstrip() + "…"


def should_skip(title: str) -> bool:
    return title.startswith(SKIP_TITLE_PREFIXES)


def iter_parsed(limit: int | None = None):
    """Yield (ns, pageid, title, body_text, excerpt) from parsed JSON."""
    n = 0
    for sub in sorted(PARSED_DIR.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_"):
            continue
        for f in sorted(sub.iterdir()):
            if not f.name.endswith(".json"):
                continue
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            title = doc.get("title", "")
            if should_skip(title):
                continue
            parse = doc.get("parse", {})
            text_html = parse.get("text", "") or ""
            if not text_html:
                continue
            # Strip HTML — fast path
            soup = BeautifulSoup(text_html, "lxml")
            # Drop scripts/styles/comments
            for tag in soup.find_all(["script", "style"]):
                tag.decompose()
            body_text = soup.get_text(" ", strip=True)
            body_text = WHITESPACE_RE.sub(" ", body_text)
            excerpt = make_excerpt(body_text, 100)
            yield doc.get("ns", 0), doc.get("pageid"), title, body_text, excerpt
            n += 1
            if limit and n >= limit:
                return


def build(out_dir: Path, limit: int | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    SHARDS_DIR.mkdir(exist_ok=True)

    titles: list[dict] = []
    bigram_posts: dict[str, list[int]] = {}
    word_posts: dict[str, list[int]] = {}

    t0 = time.time()
    seen_id = 0
    stub_count = 0

    for ns, pageid, title, body, excerpt in iter_parsed(limit=limit):
        href = page_href(ns, title)
        kind = "d" if ns == 3500 else ("c" if ns == 14 else "p")
        is_stub = len(body) < STUB_BODY_THRESHOLD
        if is_stub:
            stub_count += 1

        entry_id = seen_id
        seen_id += 1
        titles.append({"i": entry_id, "t": title, "h": href, "k": kind, "e": excerpt})

        # Index sources: title + first 600 chars of body (skip body for stubs)
        token_text = title + (" \n " + body[:600] if not is_stub else "")
        seen_words: set[str] = set()
        for w in tokenize_latin(token_text):
            if w in seen_words:
                continue
            seen_words.add(w)
            word_posts.setdefault(w, []).append(entry_id)
        seen_bg: set[str] = set()
        for bg in cjk_bigrams(token_text):
            if bg in seen_bg:
                continue
            seen_bg.add(bg)
            bigram_posts.setdefault(bg, []).append(entry_id)

        if entry_id % 2000 == 0 and entry_id > 0:
            elapsed = time.time() - t0
            print(f"  [{entry_id}] {elapsed:.1f}s, bigrams={len(bigram_posts)}, words={len(word_posts)}")

    # Bucket into shards
    bigram_shards: dict[str, dict[str, list[int]]] = {}
    for bg, ids in bigram_posts.items():
        b = bigram_bucket(bg)
        bigram_shards.setdefault(b, {})[bg] = ids
    word_shards: dict[str, dict[str, list[int]]] = {}
    for w, ids in word_posts.items():
        b = word_bucket(w)
        word_shards.setdefault(b, {})[w] = ids

    # Write titles.js (v1-compatible JSONP — search.js expects __PF2_TITLES.items)
    titles_payload = {"v": 2, "items": titles}
    titles_js = "window.__PF2_TITLES = " + json.dumps(titles_payload, ensure_ascii=False, separators=(",", ":")) + ";"
    (out_dir / "titles.js").write_text(titles_js, encoding="utf-8")

    # Write bigram shards as function-call JSONP: __PF2_SHARD_B("<hex>", {bigram: [ids]})
    bg_shard_files: list[str] = []
    for b in sorted(bigram_shards.keys()):
        fn = f"b_{b}.js"
        SHARDS_DIR.joinpath(fn).write_text(
            f'window.__PF2_SHARD_B("{b}", '
            + json.dumps(bigram_shards[b], ensure_ascii=False, separators=(",", ":")) + ");",
            encoding="utf-8",
        )
        bg_shard_files.append(b)
    # Word shards: __PF2_SHARD_W("<letter>", {word: [ids]})
    w_shard_files: list[str] = []
    for b in sorted(word_shards.keys()):
        fn = f"w_{b}.js"
        SHARDS_DIR.joinpath(fn).write_text(
            f'window.__PF2_SHARD_W("{b}", '
            + json.dumps(word_shards[b], ensure_ascii=False, separators=(",", ":")) + ");",
            encoding="utf-8",
        )
        w_shard_files.append(b)

    # Write manifest.js — v1 format
    manifest = {
        "v": 2,
        "n_pages": len(titles),
        "n_stubs": stub_count,
        "bigram_shards": bg_shard_files,
        "word_shards": w_shard_files,
    }
    (out_dir / "manifest.js").write_text(
        "window.__PF2_MANIFEST = " + json.dumps(manifest, ensure_ascii=False) + ";",
        encoding="utf-8",
    )

    elapsed = time.time() - t0
    # Summary sizes — files are named b_<bucket>.js / w_<bucket>.js
    bg_filenames = [f"b_{b}.js" for b in bg_shard_files]
    w_filenames = [f"w_{b}.js" for b in w_shard_files]
    sizes = {
        "titles.js": (out_dir / "titles.js").stat().st_size,
        "shards_total": sum(
            (SHARDS_DIR / f).stat().st_size for f in bg_filenames + w_filenames
        ),
    }
    print(f"\n[done] {len(titles)} pages, {stub_count} stubs, {len(bigram_posts)} bigrams, {len(word_posts)} words")
    print(f"       titles.js: {sizes['titles.js']/1024/1024:.1f} MB")
    print(f"       shards total: {sizes['shards_total']/1024/1024:.1f} MB ({len(bg_shard_files)}b + {len(w_shard_files)}w)")
    print(f"       built in {elapsed:.1f}s")
    return sizes


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv[1:])
    if not PARSED_DIR.exists() or not any(PARSED_DIR.iterdir()):
        print(f"ERROR: {PARSED_DIR} empty — run dump_parsed_v2_concurrent.py first")
        return 1
    build(INDEX_DIR, limit=args.limit or None)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
