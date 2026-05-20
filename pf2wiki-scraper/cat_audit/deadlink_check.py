"""Dead-link check for the regenerated browse-*.html (buckets + sub-zones).

Each row links to pages/<...>.html (or data/category/...). The href is
urllib.parse.quote()'d; files on disk use raw (decoded) names. We url-decode each
internal href and check the target file exists under _wiki_full_v2/. Reports any
missing targets per page — these would be the user's "指向不对/死链".
"""
from __future__ import annotations

import re
import urllib.parse
from collections import Counter
from pathlib import Path

WIKI = Path(__file__).resolve().parents[2] / "_wiki_full_v2"
HREF_RX = re.compile(r'href="((?:pages|data|category|project)/[^"]+\.html)"')


def main() -> int:
    pages = sorted(WIKI.glob("browse-*.html"))
    total_links = 0
    missing = Counter()
    missing_samples = {}
    for p in pages:
        html = p.read_text(encoding="utf-8")
        for href in HREF_RX.findall(html):
            total_links += 1
            # url-decode to raw filename on disk
            rel = urllib.parse.unquote(href)
            target = WIKI / rel
            if not target.exists():
                missing[p.name] += 1
                missing_samples.setdefault(p.name, []).append(rel)

    print(f"checked {len(pages)} browse pages, {total_links:,} internal links")
    if not missing:
        print("RESULT: 0 dead links — all targets resolve. ✓")
    else:
        print(f"RESULT: dead links in {len(missing)} pages:")
        for name, n in missing.most_common():
            print(f"  {name}: {n} missing  e.g. {missing_samples[name][:2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
