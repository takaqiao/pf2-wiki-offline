"""Phase F: build static HTML mirror from parsed JSON corpus.

Input:
  pf2wiki-scraper/out_v2/parsed/**/*.json    (one per page, from dump_parsed_v2.py)
  pf2wiki-scraper/out_v2/metadata.json       (from dump_metadata_v2.py)
  pf2wiki-scraper/out_v2/images/manifest.json (from dump_images_v2.py, optional)

Output:
  _wiki_full_v2/pages/*.html       ns=0, ns=102
  _wiki_full_v2/data/*.html        ns=3500
  _wiki_full_v2/category/*.html    ns=14
  _wiki_full_v2/project/*.html     ns=4

Run:
    .venv\\Scripts\\python.exe build_v2.py             # full
    .venv\\Scripts\\python.exe build_v2.py --limit 50  # sample
    .venv\\Scripts\\python.exe build_v2.py --ns 0      # one namespace
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString

# ----- Paths -----
ROOT = Path(__file__).resolve().parent  # _wiki_full_v2/
SCRAPER = ROOT.parent / "pf2wiki-scraper"
PARSED_DIR = SCRAPER / "out_v2" / "parsed"
META_FILE = SCRAPER / "out_v2" / "metadata.json"
MANIFEST_FILE = SCRAPER / "out_v2" / "images" / "manifest.json"
SNIPPET_TOPNAV = ROOT / "_snippets" / "topnav_sub.html"
SNIPPET_SIDEBAR = ROOT / "_snippets" / "sidebar_sub.html"

# ----- Constants -----
CACHE_VER = "v2f"

NS_TO_DIR = {
    0: "pages",
    4: "project",
    14: "category",
    102: "pages",
    3500: "data",
}

NS_TO_LABEL = {
    0: "条目",
    4: "项目页",
    14: "分类",
    102: "资源",
    3500: "数据",
}

# Title prefixes that signal namespace (used when href has no /wiki/ ns prefix)
NS_PREFIX = {
    "Category": 14, "分类": 14,
    "Data": 3500, "数据": 3500,
    "File": 6, "文件": 6,
    "Template": 10, "模板": 10,
}

# Strip MediaWiki diagnostic HTML comments and editsection spans
MW_COMMENT_RX = re.compile(
    r"<!--\s*(?:NewPP|Transclusion|Saved in parser cache|Cached time)[\s\S]*?-->",
    re.IGNORECASE,
)
EDITSECTION_RX = re.compile(r'<span class="mw-editsection">.*?</span>', re.S)

# Filename safety
SAFE_TITLE_RX = re.compile(r'[*?"<>|]')


def safe_title(t: str) -> str:
    """Sanitize a wiki title for use as a filename on Windows NTFS."""
    t = t.replace(":", "_").replace("/", "__").replace("\\", "_")
    return SAFE_TITLE_RX.sub("", t)


def mediawiki_body_class(ns: int, title: str, bare_title: str) -> str:
    """Build a body class list that mirrors pf2.huijiwiki.com's body.

    Sample real-page body classes from /wiki/战士:
      skin-huiji-dragonhide mediawiki ltr sitedir-ltr mw-hide-empty-elt
      ns-0 ns-subject page-战士 rootpage-战士 skin-HuijiDragonhide
      action-view skin--responsive

    We omit skin-* (we render our own offline chrome) but keep the
    namespace + page identity classes so wiki_native.css per-page
    rules can fire. Add `page-<safe>` for hooks.
    """
    classes = [
        "mediawiki", "ltr", "sitedir-ltr", "mw-hide-empty-elt",
        f"ns-{ns}",
        "ns-subject",
        "action-view", "skin--responsive",
    ]
    safe_page = safe_title(bare_title)
    classes.append(f"page-{safe_page}")
    classes.append(f"rootpage-{safe_page}")
    return " ".join(classes)


TEMPLATE_PLACEHOLDER_RX = re.compile(r"\{\{\{[^{}\n]{1,40}\}\}\}")
# Also matches HTML-encoded version: &#123;&#123;&#123;X&#125;&#125;&#125;
TEMPLATE_PLACEHOLDER_ENC_RX = re.compile(r"(?:&#123;){3}[^&]{0,40}?(?:&#125;){3}")


def clean_parse_text(html: str) -> str:
    html = MW_COMMENT_RX.sub("", html)
    html = EDITSECTION_RX.sub("", html)
    # Strip unrendered MediaWiki template placeholders like {{{动作}}}
    html = TEMPLATE_PLACEHOLDER_RX.sub("", html)
    html = TEMPLATE_PLACEHOLDER_ENC_RX.sub("", html)
    return html


def determine_target_dir(ns: int, title: str) -> tuple[str, str]:
    """Returns (dir_name, bare_title_after_stripping_ns_prefix)."""
    target = NS_TO_DIR.get(ns, "pages")
    bare = title
    if ":" in title:
        prefix, rest = title.split(":", 1)
        if prefix in NS_PREFIX or prefix in {"Category", "Data", "分类", "数据", "Template", "File", "Help", "User", "Project"}:
            bare = rest
    return target, bare


def rewrite_links(soup: BeautifulSoup, redirect_map: dict, title_index: dict) -> int:
    """Rewrite /wiki/X anchors → relative paths.

    title_index: dict[title_str -> (target_dir, safe_filename_without_ext)]
    """
    n = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        target_title = None

        if href.startswith("/wiki/"):
            tail = href[len("/wiki/"):]
            # Strip fragment
            frag = ""
            if "#" in tail:
                tail, frag = tail.split("#", 1)
                frag = "#" + frag
            try:
                target_title = urllib.parse.unquote(tail)
            except Exception:
                continue
        elif href.startswith("/index.php?title="):
            # Could be red link or non-canonical
            m = re.search(r"title=([^&]+)", href)
            if not m:
                continue
            try:
                target_title = urllib.parse.unquote(m.group(1))
            except Exception:
                continue
            frag = ""
        else:
            # external / mailto / etc.
            if href.startswith("http") and "huijiwiki.com" not in href:
                a["rel"] = "noopener external"
                a["target"] = "_blank"
            continue

        if not target_title:
            continue

        # Follow redirect if known
        target_title = target_title.replace("_", " ")
        resolved = redirect_map.get(target_title, target_title)

        # Look up in title_index
        entry = title_index.get(resolved) or title_index.get(target_title)
        if entry:
            target_dir, safe_fn = entry
            a["href"] = f"../{target_dir}/{urllib.parse.quote(safe_fn + '.html')}{frag if not href.startswith('/index.php') else ''}"
        else:
            # Unknown target — leave as dead-ish path
            # Use guessed namespace
            ns_guess = 0
            bare = target_title
            if ":" in target_title:
                prefix, rest = target_title.split(":", 1)
                if prefix in NS_PREFIX:
                    ns_guess = NS_PREFIX[prefix]
                    bare = rest
            target_dir = NS_TO_DIR.get(ns_guess, "pages")
            safe_fn = safe_title(bare)
            a["href"] = f"../{target_dir}/{urllib.parse.quote(safe_fn + '.html')}{frag if not href.startswith('/index.php') else ''}"
            # Keep .new class so CSS marks it as dead
            classes = a.get("class") or []
            if "new" not in classes:
                a["class"] = classes + ["new"]
        n += 1
    return n


IMAGE_URL_RX = re.compile(
    # Match pf2 wiki image URLs from huijistatic.com or local /wiki/images/ paths.
    # Captures the base filename out of `/uploads/[thumb/]<a>/<aa>/<file>[/<W>px-<file>]`
    # OR legacy `/wiki/images/...` (for fallback safety).
    r"(?:huijistatic\.com)?[^?#]*?/(?:wiki/images|uploads)/(?:thumb/)?(?:[0-9a-f]/[0-9a-f]{2}/)?([^/?#]+?)(?:/\d+px-[^/?#]+)?(?:\?[^#]*)?(?:#.*)?$"
)


def lookup_manifest(manifest: dict, filename: str) -> dict | None:
    """Try multiple key variants — manifest is keyed by 文件:<spaced-name>."""
    name_spaced = filename.replace("_", " ")
    name_underscored = filename.replace(" ", "_")
    candidates = [
        filename,
        name_spaced,
        name_underscored,
        f"File:{filename}", f"File:{name_spaced}", f"File:{name_underscored}",
        f"文件:{filename}", f"文件:{name_spaced}", f"文件:{name_underscored}",
    ]
    for k in candidates:
        e = manifest.get(k)
        if e:
            return e
    return None


def rewrite_images(soup: BeautifulSoup, manifest: dict) -> int:
    n = 0
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src:
            continue
        # Try parse filename from URL
        m = IMAGE_URL_RX.search(src)
        if not m:
            continue
        try:
            filename = urllib.parse.unquote(m.group(1))
        except Exception:
            continue
        entry = lookup_manifest(manifest, filename)
        if entry and entry.get("local"):
            img["src"] = f"../images/{entry['local']}"
            img["data-original-src"] = src
        else:
            classes = img.get("class") or []
            if "v2-missing-image" not in classes:
                img["class"] = classes + ["v2-missing-image"]
            img["data-original-src"] = src
            img["src"] = ""
            img["alt"] = img.get("alt", filename)
        n += 1
    return n


def build_breadcrumb(ns: int, bare_title: str) -> str:
    label = NS_TO_LABEL.get(ns, "条目")
    return (
        '<nav class="breadcrumb" aria-label="导航">'
        '<a href="../index.html">首页</a>'
        '<span class="sep">›</span>'
        f'<span>{html_lib.escape(label)}</span>'
        '<span class="sep">›</span>'
        f'<span class="current">{html_lib.escape(bare_title)}</span>'
        '</nav>'
    )


def build_categories_block(categories: list, redirect_map: dict, title_index: dict) -> str:
    """Render <div class='page-categories'> at page bottom from parse.categories."""
    if not categories:
        return ""
    items = []
    for c in categories:
        if not isinstance(c, dict):
            continue
        cat_name = c.get("category", "")
        if not cat_name:
            continue
        # Normalize: API returns underscored, we want pretty display
        display = cat_name.replace("_", " ")
        full_title = f"Category:{display}"
        # Look up local path
        entry = title_index.get(full_title) or title_index.get(display)
        if entry:
            d, fn = entry
            href = f"../{d}/{urllib.parse.quote(fn + '.html')}"
        else:
            href = f"../category/{urllib.parse.quote(safe_title(display) + '.html')}"
        items.append(
            f'<li><a href="{href}">{html_lib.escape(display)}</a></li>'
        )
    if not items:
        return ""
    return (
        '<div class="page-categories">'
        '<span class="label">分类</span>'
        '<ul>' + "".join(items) + '</ul>'
        '</div>'
    )


def make_meta_description(raw_html: str) -> str:
    """Extract first 160 chars of plain text for <meta description>."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:160].replace('"', "'")


def add_lazy_loading(soup: BeautifulSoup) -> None:
    """Add loading='lazy' to all <img> tags (perf hint)."""
    for img in soup.find_all("img"):
        if not img.get("loading"):
            img["loading"] = "lazy"


def build_section_toc(sections: list, page_word_count: int) -> str:
    """Render a simple TOC for long pages from parse.sections.

    Skips for short pages (< 1500 chars). Renders only h2/h3.
    """
    if not sections or page_word_count < 1500:
        return ""
    items = []
    for s in sections:
        if not isinstance(s, dict):
            continue
        level = s.get("level", "2")
        try:
            lvl = int(level)
        except Exception:
            continue
        if lvl > 3:
            continue
        line = s.get("line", "")
        anchor = s.get("anchor", "")
        if not line or not anchor:
            continue
        # Strip HTML from heading line
        line_plain = re.sub(r"<[^>]+>", "", line).strip()
        if not line_plain:
            continue
        indent = "  " if lvl >= 3 else ""
        items.append(
            f'{indent}<li class="toclevel-{lvl}">'
            f'<a href="#{html_lib.escape(anchor)}">{html_lib.escape(line_plain)}</a></li>'
        )
    if len(items) < 3:
        return ""
    return (
        '<div class="page-toc-v2" role="navigation" aria-label="本页目录">'
        '<details open><summary><strong>本页目录</strong></summary>'
        '<ul>\n' + "\n".join(items) + '\n</ul></details></div>'
    )


def render_page_html(doc: dict, topnav: str, sidebar: str, redirect_map: dict, title_index: dict, manifest: dict) -> tuple[str, str, str]:
    """Returns (target_dir, safe_filename_with_ext, full_html)."""
    parse = doc.get("parse", {})
    ns = doc.get("ns", 0)
    title = doc.get("title", "")
    target_dir, bare_title = determine_target_dir(ns, title)

    # Resolve final HTML body content
    raw_text = parse.get("text", "") or ""
    raw_text = clean_parse_text(raw_text)
    soup = BeautifulSoup(raw_text, "lxml")

    # If lxml wrapped in <html><body>, drill down to body's children
    body_tag = soup.body
    if body_tag is not None:
        inner = "".join(str(c) for c in body_tag.children)
        soup = BeautifulSoup(inner, "html.parser")

    rewrite_links(soup, redirect_map, title_index)
    rewrite_images(soup, manifest)
    add_lazy_loading(soup)

    content_html = str(soup)
    # Ensure mw-parser-output wrapper present
    if 'class="mw-parser-output"' not in content_html:
        content_html = f'<div class="mw-parser-output">{content_html}</div>'

    cats = parse.get("categories", []) or []
    body_class = mediawiki_body_class(ns, title, bare_title)
    display_title = parse.get("displaytitle") or bare_title
    # Strip HTML from displaytitle for use in <title> + <h1>
    display_plain = re.sub(r"<[^>]+>", "", display_title)
    # For Data: namespace, strip "Data:" prefix and ".json" suffix so h1 reads cleaner
    if ns == 3500:
        if display_plain.startswith("Data:"):
            display_plain = display_plain[5:]
        if display_plain.endswith(".json"):
            display_plain = display_plain[:-5]
    meta_desc = make_meta_description(parse.get("text", ""))

    breadcrumb_html = build_breadcrumb(ns, bare_title)
    categories_html = build_categories_block(cats, redirect_map, title_index)
    # Section TOC for long pages
    sections = parse.get("sections", []) or []
    page_text_len = len(re.sub(r"<[^>]+>", "", parse.get("text", "") or ""))
    toc_html = build_section_toc(sections, page_text_len)
    safe_fn = safe_title(bare_title)

    full_html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-Hans">\n'
        '<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<meta name="description" content="{html_lib.escape(meta_desc)}">\n'
        f'<link rel="canonical" href="https://pf2.huijiwiki.com/wiki/{urllib.parse.quote(title)}">\n'
        f'<title>{html_lib.escape(display_plain)} — PF2 离线百科</title>\n'
        f'<link rel="stylesheet" href="../assets/style.css?v={CACHE_VER}">\n'
        f'<link rel="icon" href="../assets/favicon.ico">\n'
        f'<script defer src="../assets/topnav.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="../assets/theme.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="../assets/huiji_tt.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="../assets/external_links.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="../assets/updater_ui.js?v={CACHE_VER}"></script>\n'
        f'<script defer src="../assets/mw_collapsible.js?v={CACHE_VER}"></script>\n'
        '</head>\n'
        f'<body class="{body_class}">\n'
        '<a class="skip-link" href="#main-content">跳到主要内容</a>\n'
        f'{topnav}\n'
        '<header class="page-head">\n'
        f'  <h1>{html_lib.escape(display_plain)}</h1>\n'
        '</header>\n'
        f'{breadcrumb_html}\n'
        '<div class="layout">\n'
        f'{sidebar}\n'
        '<main class="page-body" id="main-content">\n'
        '<div id="mw-content-text" class="mw-body-content mw-content-ltr">\n'
        f'{toc_html}\n'
        f'{content_html}\n'
        f'{categories_html}\n'
        '</div>\n'
        '</main>\n'
        '</div>\n'
        '<footer class="page-foot">\n'
        '  <small>本页内容来自 <a href="https://pf2.huijiwiki.com" rel="external">pf2.huijiwiki.com</a>，'
        '采用 <a href="https://creativecommons.org/licenses/by-sa/4.0/" rel="external">CC BY-SA 4.0</a> 协议。</small>\n'
        '</footer>\n'
        '</body>\n'
        '</html>\n'
    )

    return target_dir, f"{safe_fn}.html", full_html


def build_redirect_stub(src_title: str, target_title: str, redirect_map: dict, title_index: dict) -> tuple[str, str, str] | None:
    """Build a tiny HTML redirect stub. Returns (dir, filename, html) or None."""
    # Resolve final target through any chain
    seen = set()
    cur = target_title
    while cur in redirect_map and cur not in seen:
        seen.add(cur)
        nxt = redirect_map[cur]
        if not nxt:
            break
        cur = nxt
    final = cur or target_title
    if not final:
        return None
    entry = title_index.get(final) or title_index.get(final.replace("_", " "))
    if not entry:
        return None
    target_dir, safe_fn = entry
    # Redirect stub lives in same dir as source ns
    src_safe = safe_title(src_title)
    # Heuristic: stubs go in pages/ (most aliases are ns=0)
    stub_dir = "pages"
    redirect_url = f"../{target_dir}/{urllib.parse.quote(safe_fn + '.html')}"
    html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-Hans">\n<head>\n'
        '<meta charset="utf-8">\n'
        f'<meta http-equiv="refresh" content="0; url={redirect_url}">\n'
        f'<link rel="canonical" href="{redirect_url}">\n'
        f'<title>{html_lib.escape(src_title)} — 跳转至 {html_lib.escape(final)}</title>\n'
        '</head>\n<body>\n'
        f'<p>正在跳转到 <a href="{redirect_url}">{html_lib.escape(final)}</a>...</p>\n'
        '</body>\n</html>\n'
    )
    return stub_dir, f"{src_safe}.html", html


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ns", type=int, default=-1)
    ap.add_argument("--redirects", action="store_true", help="also build redirect stubs")
    args = ap.parse_args(argv[1:])

    print("[1/4] load metadata + manifest + topnav")
    if not META_FILE.exists():
        print(f"ERROR: {META_FILE} missing")
        return 1
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    redirect_map = meta.get("redirect_map", {}) or {}
    manifest = {}
    if MANIFEST_FILE.exists():
        manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    topnav = SNIPPET_TOPNAV.read_text(encoding="utf-8")
    sidebar = SNIPPET_SIDEBAR.read_text(encoding="utf-8") if SNIPPET_SIDEBAR.exists() else '<nav class="wiki-sidebar" aria-label="百科导航"></nav>'

    # Build title index: title -> (target_dir, safe_fn)
    title_index: dict[str, tuple[str, str]] = {}
    for p in meta.get("pages", []):
        ns = p.get("ns", 0)
        t = p.get("title", "")
        target_dir, bare = determine_target_dir(ns, t)
        title_index[t] = (target_dir, safe_title(bare))
        # also index without ns prefix for short refs
        if bare != t:
            title_index[bare] = (target_dir, safe_title(bare))

    print(f"  meta: {len(meta.get('pages', []))} pages, {len(redirect_map)} redirects, manifest {len(manifest)}, topnav {len(topnav)} chars")

    print("[2/4] enumerate parsed JSON files")
    parsed_files = [p for p in PARSED_DIR.rglob("*.json") if not p.name.startswith("_")]
    if args.ns >= 0:
        # filter by ns later when reading file
        pass
    if args.limit:
        parsed_files = parsed_files[: args.limit]
    print(f"  found {len(parsed_files)} parsed JSON files")

    print("[3/4] render pages")
    t0 = time.time()
    n_ok = 0
    n_fail = 0
    by_dir: dict[str, int] = {}
    for i, pf in enumerate(parsed_files):
        try:
            doc = json.loads(pf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [{i}] read fail {pf.name}: {e}")
            n_fail += 1
            continue
        if args.ns >= 0 and doc.get("ns") != args.ns:
            continue
        try:
            target_dir, fname, html = render_page_html(doc, topnav, sidebar, redirect_map, title_index, manifest)
        except Exception as e:
            title = doc.get("title", "?")
            print(f"  [{i}] render fail '{title.encode('ascii','replace').decode()[:40]}': {type(e).__name__}: {e}")
            n_fail += 1
            continue
        out_path = ROOT / target_dir / fname
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        by_dir[target_dir] = by_dir.get(target_dir, 0) + 1
        n_ok += 1
        if (n_ok + n_fail) % 500 == 0:
            elapsed = time.time() - t0
            print(f"  [{n_ok + n_fail}/{len(parsed_files)}] ok={n_ok} fail={n_fail} rate={n_ok/max(elapsed,0.001):.0f}/s")

    print(f"\n[4/4] done: rendered {n_ok}, failed {n_fail} in {time.time()-t0:.1f}s")
    for d, c in sorted(by_dir.items()):
        print(f"    {d}/: {c}")

    if args.redirects:
        print("\n[5/5] redirect stubs")
        n_redir = 0
        for src, tgt in redirect_map.items():
            if not tgt:
                continue
            stub = build_redirect_stub(src, tgt, redirect_map, title_index)
            if not stub:
                continue
            sd, sf, sh = stub
            (ROOT / sd / sf).write_text(sh, encoding="utf-8")
            n_redir += 1
        print(f"    +{n_redir} redirect stubs")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
