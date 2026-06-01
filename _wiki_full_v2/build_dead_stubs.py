# -*- coding: utf-8 -*-
"""
build_dead_stubs.py
===================

Generate friendly *stub* HTML files for the top dead-link targets reported by
``agent_outputs_v2/_deadlink_scan_report.json``.

Approach
--------
For each known-dead target we know is referenced many times across the wiki
(but does NOT exist on the source PF2 wiki either, or only exists as a
disambiguation / scattered category), we emit a small HTML page that:

* meta-refreshes to a reasonable substitute (search query, browse-all filter,
  or an existing page)
* shows a short notice + clickable fallback links so users who land mid-flow
  still see something useful instead of a bare 404

We do NOT regenerate the full corpus and we do NOT touch ``build_v2.py`` — this
is a small, idempotent post-processing pass. Stubs are written into:

* ``_wiki_full_v2/pages/<name>.html`` for ``pages/...`` targets
* ``_wiki_full_v2/category/<name>.html`` for ``category/...`` targets

If a stub destination already exists on disk, we leave the existing file alone
(we only fill genuine gaps).

The redirect map below is hand-tuned for the top dead targets in the v2 corpus
as of 2026-05; new entries can be appended without re-running the scanner.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(r"C:\Users\Taka\Desktop\fvtt\_wiki_full_v2")
REPORT = Path(r"C:\Users\Taka\Desktop\fvtt\agent_outputs_v2\_deadlink_scan_report.json")


# ---------------------------------------------------------------------------
# Redirect rules
# ---------------------------------------------------------------------------
#
# Each rule maps a dead target (forward-slash relative path under the wiki
# root) to a *(redirect_url, human_label)* pair. ``redirect_url`` is a relative
# path that lives one level below the wiki root (because stubs live under
# pages/ or category/), so it normally starts with ``../``.
#
# Mapping policy:
#   pages/... stubs live under _wiki_full_v2/pages/  -> use "../<thing>"
#   category/... stubs live under _wiki_full_v2/category/ -> use "../<thing>"
#
# When in doubt, redirect to search.html?q=<term> which always works.
# ---------------------------------------------------------------------------

REDIRECT_RULES: dict[str, tuple[str, str]] = {
    # --- top page-level dead targets ---
    "pages/炼金草药.html": (
        "../browse-items.html",
        "炼金草药",
    ),
    "pages/物品导航.html": (
        "../browse-items.html",
        "物品导航",
    ),
    "pages/动物看护设施.html": (
        "../search.html?q=" + quote("动物看护设施"),
        "动物看护设施",
    ),
    "pages/预言破灭之年设定集.html": (
        "../pages/预言破灭之年.html",
        "预言破灭之年设定集",
    ),
    "pages/杨柳镇.html": (
        "../search.html?q=" + quote("杨柳镇"),
        "杨柳镇",
    ),
    "pages/草原地.html": (
        "../search.html?q=" + quote("草原地"),
        "草原地",
    ),
    # NOTE: former category-level dead-stub rules (相关 / 变体（特征） /
    # 预言破灭之年（2e） / 绑定（特征）) were REMOVED — build_v2.py [4b] now generates
    # real member-list pages for every referenced category, so a 2-sec redirect
    # stub would shadow the real 2153-member archetype listing etc. Real page wins.
}


# Pages that the top-30 report flags but which look like raw image leakage
# (``foo.png.html``). We emit a stub that bounces to a search query stripped
# of the ``.png`` suffix.
def is_png_html_leak(target: str) -> bool:
    return target.endswith(".png.html")


def png_leak_rule(target: str) -> tuple[str, str]:
    name = Path(target).name  # e.g. "额外学识.png.html"
    base = re.sub(r"\.png\.html$", "", name, flags=re.IGNORECASE)
    parent = "pages" if target.startswith("pages/") else "category"
    return ("../search.html?q=" + quote(base), f"{base} [{parent}]")


# ---------------------------------------------------------------------------
# Stub template
# ---------------------------------------------------------------------------

STUB_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="2;url={redirect_url}">
<title>{label} — 跳转中 — PF2 离线百科</title>
<meta name="description" content="{label} 页面不存在，将跳转到相关浏览页或搜索。">
<link rel="stylesheet" href="../assets/style.css?v=v2h">
<link rel="stylesheet" href="../assets/topnav.css?v=v2h">
<link rel="icon" href="../assets/favicon.ico">
<script defer src="../assets/topnav.js?v=v2h"></script>
<script defer src="../assets/theme.js?v=v2h"></script>
<script defer src="../assets/external_links.js?v=v2h"></script>
<style>
body {{
  margin: 0; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei",
               "Source Han Sans SC", "Noto Sans CJK SC", sans-serif;
}}
.stub-header {{
  background: linear-gradient(180deg, var(--accent-band) 0%, var(--accent) 100%);
  color: var(--accent-on);
  border-bottom: 2px solid var(--gold, #b89248);
  padding: 28px 24px 22px;
  text-align: center;
}}
.stub-header h1 {{
  margin: 0 0 6px;
  font-family: "Source Han Serif SC", "Noto Serif CJK SC", Georgia, serif;
  font-size: 24px;
  letter-spacing: .04em;
}}
.stub-header .sub {{ margin: 0; font-size: 14px; opacity: .92; }}
.stub-main {{
  max-width: 640px; margin: 0 auto; padding: 28px 24px;
}}
.stub-card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 22px 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}}
.stub-card p {{
  margin: 8px 0; font-size: 14.5px; line-height: 1.65;
  color: var(--fg-soft, var(--fg));
}}
.stub-card a {{
  color: var(--accent); font-weight: 600;
  text-decoration: none;
}}
.stub-card a:hover {{ text-decoration: underline; }}
.stub-fallbacks {{
  display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px;
}}
.stub-fallbacks a {{
  display: inline-block;
  padding: 8px 14px;
  background: var(--card-alt, var(--card));
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--fg); font-weight: 500; font-size: 13.5px;
}}
.stub-fallbacks a:hover {{
  border-color: var(--accent);
  text-decoration: none;
}}
.stub-target {{
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12.5px;
  background: var(--bg-alt, var(--card));
  border-left: 3px solid var(--accent);
  padding: 8px 12px;
  margin: 8px 0;
  word-break: break-all;
  color: var(--fg-mute);
}}
</style>
</head>
<body class="page-stub">
<header class="stub-header">
  <h1>{label}</h1>
  <p class="sub">此页面不存在，正在为您跳转…</p>
</header>
<main class="stub-main">
  <div class="stub-card">
    <p>“<strong>{label}</strong>” 不是本离线百科收录的独立条目。
       2 秒后将自动跳转到 <a href="{redirect_url}">相关页面</a>。</p>
    <div class="stub-target">原链接：{original_path}</div>
    <p>如果跳转未发生，请点击下面的链接：</p>
    <div class="stub-fallbacks">
      <a href="{redirect_url}">前往相关页面</a>
      <a href="../search.html?q={search_term}">搜索“{label}”</a>
      <a href="../browse-all.html">浏览全部条目</a>
      <a href="../index.html">返回首页</a>
    </div>
  </div>
</main>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def write_stub(target_rel: str, redirect_url: str, label: str, overwrite: bool) -> str:
    """Write the stub file for *target_rel*. Returns one of: 'wrote',
    'skipped-exists', 'skipped-bad-target'."""
    if "/" not in target_rel or not target_rel.endswith(".html"):
        return "skipped-bad-target"
    out_path = ROOT / target_rel
    if out_path.exists() and not overwrite:
        return "skipped-exists"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = STUB_TEMPLATE.format(
        redirect_url=redirect_url,
        label=label,
        original_path=target_rel,
        search_term=quote(label),
    )
    out_path.write_text(html, encoding="utf-8")
    return "wrote"


def load_top_dead_targets() -> list[tuple[str, int]]:
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    out: list[tuple[str, int]] = []
    for item in data.get("top30_dead_targets", []):
        tgt = item.get("target")
        cnt = int(item.get("incoming", 0))
        if tgt:
            out.append((tgt, cnt))
    return out


def main() -> int:
    overwrite = "--overwrite" in sys.argv

    top = load_top_dead_targets()
    print(f"[1/3] loaded {len(top)} top dead targets from report", flush=True)

    # Build effective rule set: explicit map first, then png-leak detector for
    # anything else we recognize, plus a generic fallback for top targets that
    # have no rule (we redirect them to the search page with the basename).
    rules: list[tuple[str, str, str, int]] = []
    seen: set[str] = set()
    for tgt, cnt in top:
        if tgt in seen:
            continue
        seen.add(tgt)
        if tgt in REDIRECT_RULES:
            url, label = REDIRECT_RULES[tgt]
        elif is_png_html_leak(tgt):
            url, label = png_leak_rule(tgt)
        else:
            # generic: search for the basename without .html
            name = Path(tgt).stem
            url = "../search.html?q=" + quote(name)
            label = name
        rules.append((tgt, url, label, cnt))

    # Always also process every rule from REDIRECT_RULES even if it didn't make
    # the top-30 list (the report might have shifted slightly between runs).
    for tgt, (url, label) in REDIRECT_RULES.items():
        if tgt in seen:
            continue
        seen.add(tgt)
        rules.append((tgt, url, label, 0))

    print(f"[2/3] writing {len(rules)} stubs (overwrite={overwrite})", flush=True)

    counts = {"wrote": 0, "skipped-exists": 0, "skipped-bad-target": 0}
    written_paths: list[str] = []
    skipped_paths: list[str] = []
    for tgt, url, label, cnt in rules:
        result = write_stub(tgt, url, label, overwrite)
        counts[result] = counts.get(result, 0) + 1
        if result == "wrote":
            written_paths.append(f"  + {tgt}  ->  {url}  ({cnt:,} inbound)")
        elif result == "skipped-exists":
            skipped_paths.append(f"  = {tgt}  (already exists)")

    print(f"[3/3] done — wrote={counts['wrote']}, "
          f"skipped-existing={counts['skipped-exists']}, "
          f"bad-target={counts['skipped-bad-target']}", flush=True)

    if written_paths:
        print("\nNew stubs:")
        for line in written_paths:
            print(line)
    if skipped_paths:
        print("\nSkipped (already on disk):")
        for line in skipped_paths:
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
