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
CACHE_VER = "v2h"
APP_VERSION = "v0.3.10"  # bumped per release; written to _app_version.json (no longer in meta tag)

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

        # Skip image/media file links — they were /wiki/File:foo.png style and
        # get rewritten by rewrite_images() (since the wiki templates often
        # have the bare image name as both a link and an embedded src).
        # Avoids generating dead `pages/额外学识.png.html` style links.
        if re.search(r"\.(png|jpg|jpeg|gif|webp|svg|bmp|ico)$", target_title, re.IGNORECASE):
            # No matching local page; remove the broken anchor (keep label text)
            a.replace_with(a.get_text())
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


# ---- Inline wikitext rendering for Data: (ns=3500) JSON value cells ----
# Some Data:* JSON fields store raw, *unparsed* wikitext (action=parse leaves it
# literal inside <td class="mw-jsonconfig-value">). We do a lightweight pass:
#   [[A|B]]            -> link to A, label B
#   [[A]]              -> link to A, label A
#   {{浮窗|类型|文字}}  -> tooltip span showing 文字 (title=类型)
#   {{浮窗|文字}}       -> tooltip span showing 文字
# Any other {{...}} template we can't render is reduced to its visible args
# (pipe-joined) so no raw braces leak through.
WIKILINK_RX = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]*?))?\]\]")
TOOLTIP_RX = re.compile(r"\{\{\s*浮窗\s*\|([^{}]*?)\}\}")
GENERIC_TPL_RX = re.compile(r"\{\{([^{}]*?)\}\}")


def _data_link_html(target_title: str, label: str, redirect_map: dict, title_index: dict) -> str:
    """Build an <a> (relative from data/ dir) for a [[wikilink]] target."""
    frag = ""
    if "#" in target_title:
        target_title, frag = target_title.split("#", 1)
        frag = "#" + frag
    target_title = target_title.strip().replace("_", " ")
    label = (label or target_title).strip()
    if not target_title:
        return html_lib.escape(label)
    resolved = redirect_map.get(target_title, target_title)
    entry = title_index.get(resolved) or title_index.get(target_title)
    cls = ""
    if entry:
        target_dir, safe_fn = entry
    else:
        # Unknown target — guess namespace, mark as dead (.new) like rewrite_links.
        ns_guess, bare = 0, target_title
        if ":" in target_title:
            prefix, rest = target_title.split(":", 1)
            if prefix in NS_PREFIX:
                ns_guess, bare = NS_PREFIX[prefix], rest
        target_dir = NS_TO_DIR.get(ns_guess, "pages")
        safe_fn = safe_title(bare)
        cls = ' class="new"'
    href = f"../{target_dir}/{urllib.parse.quote(safe_fn + '.html')}{frag}"
    return f'<a href="{href}"{cls}>{html_lib.escape(label)}</a>'


def render_wikitext_inline(text: str, redirect_map: dict, title_index: dict) -> str:
    """Convert literal wikitext fragments to HTML. Input is plain text (not HTML)."""
    if "[[" not in text and "{{" not in text:
        return html_lib.escape(text)

    # Tokenize, escaping the plain-text gaps and replacing markup spans.
    out = []
    pos = 0
    # Process [[...]] and {{...}} in left-to-right order.
    token_rx = re.compile(r"\[\[[^\[\]]*?\]\]|\{\{[^{}]*?\}\}")
    for m in token_rx.finditer(text):
        out.append(html_lib.escape(text[pos:m.start()]))
        tok = m.group(0)
        if tok.startswith("[["):
            lm = WIKILINK_RX.match(tok)
            if lm:
                out.append(_data_link_html(lm.group(1), lm.group(2), redirect_map, title_index))
            else:
                out.append(html_lib.escape(tok[2:-2]))
        else:  # {{...}}
            tm = TOOLTIP_RX.match(tok)
            if tm:
                parts = [p.strip() for p in tm.group(1).split("|")]
                if len(parts) >= 2:
                    typ, txt = parts[0], parts[-1]
                else:
                    typ, txt = "", parts[0]
                title_attr = f' title="{html_lib.escape(typ)}"' if typ else ""
                out.append(
                    f'<span class="huiji-tt huiji-tt-rendered"{title_attr}>'
                    f'{html_lib.escape(txt)}</span>'
                )
            else:
                # Unknown template: show visible args (drop name before first |),
                # no braces. Args may themselves contain [[wikilinks]] (e.g.
                # {{quote|...[[X]]...}}), so recurse to render those too. Also
                # drop any leading key= from each pipe-separated arg.
                inner = tok[2:-2]
                args = inner.split("|")[1:] if "|" in inner else [inner]
                cleaned = []
                for arg in args:
                    # strip a leading "key=" prefix (e.g. icon=生物, 标题=...)
                    if "=" in arg:
                        k, v = arg.split("=", 1)
                        if "[[" not in k and "{{" not in k and len(k) <= 12:
                            arg = v
                    cleaned.append(arg)
                joined = " ".join(a for a in cleaned if a.strip())
                # Recurse to render any [[links]]/{{浮窗}} inside the args.
                out.append(render_wikitext_inline(joined, redirect_map, title_index))
        pos = m.end()
    out.append(html_lib.escape(text[pos:]))
    return "".join(out)


def render_data_value_cells(soup: BeautifulSoup, redirect_map: dict, title_index: dict) -> int:
    """For Data: pages, render unparsed wikitext inside JSON value cells.

    Most cells are pure text, but some mix already-rendered HTML with stray
    wikitext, so we walk each cell's descendant NavigableString text nodes and
    replace any that contain [[ or {{ markup. We skip text inside <a>/<script>/
    <style> to avoid nesting links or breaking code.
    """
    n = 0
    SKIP_PARENTS = {"a", "script", "style"}
    for cell in soup.select("td.mw-jsonconfig-value"):
        if "[[" not in cell.get_text() and "{{" not in cell.get_text():
            continue
        # Collect text nodes first (mutating during iteration is unsafe).
        targets = []
        for node in cell.descendants:
            if not isinstance(node, NavigableString):
                continue
            s = str(node)
            if "[[" not in s and "{{" not in s:
                continue
            parent = node.parent
            if parent is not None and parent.name in SKIP_PARENTS:
                continue
            targets.append(node)
        for node in targets:
            rendered = render_wikitext_inline(str(node), redirect_map, title_index)
            frag = BeautifulSoup(rendered, "html.parser")
            node.replace_with(*list(frag.contents))
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
        # Drop srcset — its high-DPI variants point at remote CDN we don't mirror,
        # and browsers prefer srcset over src. Single src is sufficient offline.
        if img.has_attr("srcset"):
            del img["srcset"]
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


def render_category_members(cat_title: str, members: list[tuple[str, int, str]],
                            title_index: dict) -> str:
    """Render member list for a Category page (ns=14).

    members: list of (sortkey, ns, member_title) tuples. Grouped by first
    char (CJK / A-Z / other) and laid out as multi-column lists matching
    MediaWiki's standard mw-category appearance.
    """
    if not members:
        return ""
    # Group by first character bucket
    from collections import defaultdict
    buckets: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for sortkey, ns, mt in members:
        key = (sortkey or mt).strip()
        if not key:
            buckets["_"].append((sortkey, ns, mt))
            continue
        c = key[0]
        if "a" <= c.lower() <= "z":
            buckets[c.upper()].append((sortkey, ns, mt))
        else:
            cp = ord(c)
            if (0x3400 <= cp <= 0x4DBF) or (0x4E00 <= cp <= 0x9FFF):
                # Use first CJK char as bucket
                buckets[c].append((sortkey, ns, mt))
            else:
                buckets["_"].append((sortkey, ns, mt))

    # Sort buckets: A-Z first, then CJK by codepoint, then _
    def bucket_key(b):
        if len(b) == 1 and "A" <= b <= "Z":
            return (0, ord(b))
        if b == "_":
            return (2, 0)
        return (1, ord(b[0]))

    out = [f'<div class="mw-category">']
    out.append(f'<p>该分类共有 <strong>{len(members)}</strong> 个页面。</p>')
    for b in sorted(buckets.keys(), key=bucket_key):
        out.append('<div class="mw-category-group">')
        out.append(f'<h3>{html_lib.escape(b)}</h3>')
        out.append('<ul>')
        for sortkey, ns, mt in sorted(buckets[b], key=lambda x: (x[0] or x[2]).lower()):
            entry = title_index.get(mt)
            if entry:
                td, sfn = entry
                href = f"../{td}/{urllib.parse.quote(sfn + '.html')}"
            else:
                href = f"../pages/{urllib.parse.quote(safe_title(mt) + '.html')}"
            out.append(f'<li><a href="{href}">{html_lib.escape(mt)}</a></li>')
        out.append('</ul></div>')
    out.append('</div>')
    return "\n".join(out)


def render_page_html(doc: dict, topnav: str, sidebar: str, redirect_map: dict, title_index: dict, manifest: dict, category_members: dict | None = None) -> tuple[str, str, str]:
    """Returns (target_dir, safe_filename_with_ext, full_html)."""
    parse = doc.get("parse", {})
    ns = doc.get("ns", 0)
    title = doc.get("title", "")
    target_dir, bare_title = determine_target_dir(ns, title)

    # Resolve final HTML body content.
    # IMPORTANT: use html.parser, NOT lxml. lxml silently DROPS the value of any
    # attribute whose NAME contains non-ASCII chars (e.g. the wiki's CustomFilter
    # widgets emit data-filter-环级="法术1"). That breaks every filterable list
    # page (法术列表 / 生物总表 / etc.) — rows render but filters have no values.
    # html.parser preserves these attributes and (bonus) doesn't wrap fragments
    # in <html><body>, so no drill-down is needed.
    raw_text = parse.get("text", "") or ""
    raw_text = clean_parse_text(raw_text)
    soup = BeautifulSoup(raw_text, "html.parser")

    rewrite_links(soup, redirect_map, title_index)
    rewrite_images(soup, manifest)
    add_lazy_loading(soup)

    # Data: pages store some fields as literal, unparsed wikitext inside JSON
    # value cells. Convert [[links]] and {{浮窗}} tooltips to HTML so they
    # render instead of showing raw markup.
    if ns == 3500:
        render_data_value_cells(soup, redirect_map, title_index)

    # For Category: pages (ns=14), inject auto-generated member list because
    # action=parse doesn't include MediaWiki's dynamic categorymembers listing.
    if ns == 14 and category_members:
        # Title in metadata is e.g. "Category:法术" or "分类:法术"
        cat_name = title
        for prefix in ("Category:", "分类:"):
            if cat_name.startswith(prefix):
                cat_name = cat_name[len(prefix):]
                break
        members = category_members.get(cat_name, [])
        if members:
            members_html = render_category_members(cat_name, members, title_index)
            # Append to soup at end of mw-parser-output
            from bs4 import BeautifulSoup as _BS
            extra = _BS(members_html, "html.parser")
            container = soup.find(class_="mw-parser-output")
            if container:
                container.append(extra)
            else:
                # No parser-output wrapper — append at top level
                for el in extra.contents:
                    soup.append(el)

    # If this page is just a redirect notice (parse.text = <div class="redirectMsg">...</div>),
    # extract the target href and emit a meta-refresh so users land at content immediately.
    redirect_meta_html = ""
    redirect_msg_a = soup.select_one(".redirectMsg a[href]")
    if redirect_msg_a:
        redirect_target = redirect_msg_a.get("href", "").strip()
        # Don't auto-refresh to a non-existent target: rewrite_links marks unknown
        # pages with class="new"; refreshing there would 404 with no fallback, so
        # leave the redirect notice visible instead.
        a_classes = redirect_msg_a.get("class") or []
        is_dead = "new" in a_classes
        if redirect_target and not redirect_target.startswith("http") and not is_dead:
            redirect_meta_html = (
                f'<meta http-equiv="refresh" content="0; url={html_lib.escape(redirect_target)}">\n'
            )

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
        '<script>/* pre-paint theme to avoid FOUC */(function(){try{var t=localStorage.getItem(\'theme\');if(t===\'dark\'||(t!==\'light\'&&window.matchMedia&&matchMedia(\'(prefers-color-scheme:dark)\').matches))document.documentElement.classList.add(\'dark\');}catch(e){}})();</script>\n'
        f'<meta name="description" content="{html_lib.escape(meta_desc)}">\n'
        f'{redirect_meta_html}'
        f'<link rel="canonical" href="https://pf2.huijiwiki.com/wiki/{urllib.parse.quote(title)}">\n'
        f'<title>{html_lib.escape(display_plain)} — PF2 离线百科</title>\n'
        '<link rel="stylesheet" href="../assets/style.css">\n'
        '<link rel="icon" href="../assets/favicon.ico">\n'
        '<script defer src="../assets/topnav.js"></script>\n'
        '<script defer src="../assets/theme.js"></script>\n'
        '<script defer src="../assets/huiji_tt.js"></script>\n'
        '<script defer src="../assets/external_links.js"></script>\n'
        '<script defer src="../assets/updater_ui.js"></script>\n'
        '<script defer src="../assets/mw_collapsible.js"></script>\n'
        '<script defer src="../assets/wikitable_sort.js"></script>\n'
        '<script defer src="../assets/wikitable_paginate.js"></script>\n'
        '<script defer src="../assets/image_lightbox.js"></script>\n'
        '<script defer src="../assets/bookmark.js"></script>\n'
        '<script defer src="../assets/keybindings.js"></script>\n'
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


# Redirect-source disambiguator-suffix matcher.
# Handles aliases like "偏转（特征）" → base "偏转", "Cleric (class)" → base "Cleric".
REDIRECT_SUFFIX_RX = re.compile(
    r"^(?P<base>.+?)"
    r"(?:（(?:特征|trait|德鲁伊聚能|聚能|动作|action|法术|spell|羁绊|印记|伙伴|companion|"
    r"传承|heritage|背景|background|职业|class|阵营|deity|神祇|遗物|relic|奇物|wondrous|装备|"
    r"item|武器|weapon|护甲|armor|盾牌|shield|区域|region|地点|location|组织|organization|"
    r"势力|faction|国家|nation|城市|city|术语|term)）"
    r"|\s*\((?:trait|action|spell|class|deity|item|weapon|armor|shield|location|region|"
    r"organization|term|companion|heritage|background)\))$"
)
BRACKET_TRAILING_RX = re.compile(r"[（(][^（()）]*[)）]\s*$")


def _resolve_redirect_target(
    src_title: str,
    target_title: str,
    redirect_map: dict,
    title_index: dict,
) -> str | None:
    """Find the canonical wiki title a redirect source should land on.

    Strategy:
      1. Follow target chain through redirect_map (handles A→B→C).
      2. If the chain produces a non-empty title that exists in title_index, use it.
      3. Empty/unresolvable target → try heuristic fallbacks based on src_title:
         a. Strip parenthetical disambiguator suffix (e.g. "X（特征）" → try "X",
            "X特征", "X 特征", and a handful of common kind tags).
         b. For slash titles ("A/B"), try left segment, right segment, joined.
         c. Strip any trailing parenthetical block as a generic fallback.
      4. Identity check: if a candidate equals src_title itself, skip — a self
         redirect is useless (the source page already lives at that filename).
    """
    seen: set[str] = set()
    cur = (target_title or "").strip()
    while cur and cur in redirect_map and cur not in seen:
        seen.add(cur)
        nxt = redirect_map[cur]
        if not nxt:
            break
        cur = nxt

    candidates: list[str] = []
    if cur:
        candidates.append(cur)
        if "_" in cur:
            candidates.append(cur.replace("_", " "))

    m = REDIRECT_SUFFIX_RX.match(src_title)
    if m:
        base = m.group("base").strip()
        if base:
            candidates.append(base)
            for kind in ("特征", "动作", "法术", "传承", "背景", "职业", "区域", "地点", "组织", "聚能"):
                candidates.append(f"{base}{kind}")
                candidates.append(f"{base} {kind}")

    if "/" in src_title:
        left, _, right = src_title.partition("/")
        left, right = left.strip(), right.strip()
        if left:
            candidates.append(left)
        if right:
            candidates.append(right)
        if left and right:
            candidates.append(f"{left}{right}")
            candidates.append(f"{left} {right}")

    bare = BRACKET_TRAILING_RX.sub("", src_title).strip()
    if bare and bare != src_title:
        candidates.append(bare)

    seen_c: set[str] = set()
    for c in candidates:
        if not c or c == src_title or c in seen_c:
            continue
        seen_c.add(c)
        if c in title_index:
            return c
        spaced = c.replace("_", " ")
        if spaced != c and spaced in title_index:
            return spaced
    return None


def build_redirect_stub(
    src_title: str,
    target_title: str,
    redirect_map: dict,
    title_index: dict,
    existing_titles: set | None = None,
) -> tuple[str, str, str] | None:
    """Build a tiny HTML redirect stub. Returns (dir, filename, html) or None.

    Skip cases:
      - src_title is itself a rendered page (would clobber real content).
      - No target resolvable (no chain target + no heuristic match).
      - Target resolves to the source itself (self-redirect is useless).
    """
    if existing_titles is not None and src_title in existing_titles:
        return None

    final = _resolve_redirect_target(src_title, target_title, redirect_map, title_index)
    if not final:
        return None
    entry = title_index.get(final) or title_index.get(final.replace("_", " "))
    if not entry:
        return None
    target_dir, safe_fn = entry
    src_safe = safe_title(src_title)
    # Self-referential stub (same dir + same filename) → skip
    if target_dir == "pages" and safe_fn == src_safe:
        return None
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
    # The full ns-prefixed title key (t) is unique. The bare key (without ns
    # prefix) can COLLIDE — e.g. article "《核心规则书》" (ns0) and category
    # "Category:《核心规则书》" (ns14) both reduce to "《核心规则书》". A naive
    # last-write-wins made [[《核心规则书》]] resolve to the category listing.
    # Resolve by namespace priority: articles (ns 0/102) beat project/category.
    NS_BARE_PRIORITY = {0: 0, 102: 1, 3500: 2, 4: 3, 14: 4}
    title_index: dict[str, tuple[str, str]] = {}
    bare_owner_prio: dict[str, int] = {}
    for p in meta.get("pages", []):
        ns = p.get("ns", 0)
        t = p.get("title", "")
        target_dir, bare = determine_target_dir(ns, t)
        title_index[t] = (target_dir, safe_title(bare))
        # also index without ns prefix for short refs (non-clobbering, ns-prioritized)
        if bare != t:
            prio = NS_BARE_PRIORITY.get(ns, 9)
            if bare not in bare_owner_prio or prio < bare_owner_prio[bare]:
                title_index[bare] = (target_dir, safe_title(bare))
                bare_owner_prio[bare] = prio

    print(f"  meta: {len(meta.get('pages', []))} pages, {len(redirect_map)} redirects, manifest {len(manifest)}, topnav {len(topnav)} chars")

    # Pre-pass: scan all parsed JSON to build reverse-index of category members.
    # MediaWiki's action=parse doesn't include the dynamic categorymembers list
    # for ns=14 pages, but every page's parse.categories tells us which
    # categories it belongs to. So we invert that to populate category pages.
    print("[2/4] build category reverse-index")
    category_members: dict[str, list[tuple[str, int, str]]] = {}
    tcat0 = time.time()
    cat_scan_files = sorted(PARSED_DIR.rglob("*.json"))  # sorted: deterministic scan order
    for pf in cat_scan_files:
        if pf.name.startswith("_"):
            continue
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        page_title = d.get("title", "")
        page_ns = d.get("ns", 0)
        if not page_title:
            continue
        for c in (d.get("parse", {}) or {}).get("categories", []) or []:
            if not isinstance(c, dict):
                continue
            cat = c.get("category", "")
            sortkey = c.get("sortkey", "") or page_title
            if not cat:
                continue
            cat = cat.replace("_", " ")
            category_members.setdefault(cat, []).append((sortkey, page_ns, page_title))
    print(f"  scanned {len(cat_scan_files)} parsed files in {time.time()-tcat0:.1f}s, "
          f"populated {len(category_members)} categories")

    print("[3/4] enumerate parsed JSON files")
    parsed_files = [p for p in sorted(PARSED_DIR.rglob("*.json")) if not p.name.startswith("_")]
    if args.ns >= 0:
        # filter by ns later when reading file
        pass
    if args.limit:
        parsed_files = parsed_files[: args.limit]
    print(f"  found {len(parsed_files)} parsed JSON files")

    # NOTE: deliberately NO blanket clean of pages/ here. The parsed corpus
    # (~37k) is smaller than metadata (~40k) — ~1.4k non-redirect wiki pages that
    # exist on the wiki simply weren't in the last parse run. Those pages were
    # rendered by earlier, more-complete scrapes and persist on disk; a blanket
    # rmtree deletes that valid content and spikes content-page dead links from
    # ~1.7% to ~10.5% (measured). Orphan removal for genuinely-deleted wiki pages
    # is deferred to a smarter title-set diff once the scrape corpus is complete.
    print("[4/4] render pages")
    t0 = time.time()
    n_ok = 0
    n_fail = 0
    by_dir: dict[str, int] = {}
    rendered_cat_names: set[str] = set()   # bare names of ns=14 cats already written
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
            target_dir, fname, html = render_page_html(doc, topnav, sidebar, redirect_map, title_index, manifest, category_members)
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
        if doc.get("ns") == 14:
            _ct = doc.get("title", "")
            for _p in ("Category:", "分类:"):
                if _ct.startswith(_p):
                    _ct = _ct[len(_p):]
                    break
            rendered_cat_names.add(_ct)
        if (n_ok + n_fail) % 500 == 0:
            elapsed = time.time() - t0
            print(f"  [{n_ok + n_fail}/{len(parsed_files)}] ok={n_ok} fail={n_fail} rate={n_ok/max(elapsed,0.001):.0f}/s")

    print(f"\n[4/4] done: rendered {n_ok}, failed {n_fail} in {time.time()-t0:.1f}s")
    for d, c in sorted(by_dir.items()):
        print(f"    {d}/: {c}")

    # [4b] Category pages for referenced-but-un-scraped categories. Content pages
    # link to every category they belong to, but only scraped ns=14 ones had pages
    # -> ~3% of content links were dead (mostly trait categories). MediaWiki shows
    # member lists even for description-less categories; we do the same by
    # synthesizing a minimal Category doc and letting render_page_html inject the
    # member list from the inverted index.
    # Gate on FULL builds only — a --ns/--limit sample shouldn't write the whole
    # ~3600-page category tree.
    if args.ns >= 0 or args.limit:
        print("\n[4b/4] skipped (sample build: --ns/--limit set)")
        n_xcat = 0
    else:
        print("\n[4b/4] category pages for referenced (un-scraped) categories")
        t4b = time.time()
        n_xcat = 0
        for cat in sorted(category_members.keys()):
            # rendered_cat_names already holds every scraped ns=14 page we wrote, so
            # we never shadow a real category page. We DO (re)write synthesized ones
            # unconditionally (no exists() skip) so member counts/lists stay fresh on
            # every rebuild (overwrites the prior synthesized page with current data).
            if cat in rendered_cat_names or not category_members.get(cat):
                continue
            fake = {
                "ns": 14, "pageid": 0, "title": f"Category:{cat}",
                "parse": {"title": f"Category:{cat}",
                          "text": '<div class="mw-parser-output"></div>', "categories": []},
            }
            try:
                td, fname, html = render_page_html(fake, topnav, sidebar, redirect_map,
                                                   title_index, manifest, category_members)
            except Exception:
                continue
            out_path = ROOT / td / fname
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(html, encoding="utf-8")
            n_xcat += 1
        print(f"    +{n_xcat} extra category pages in {time.time()-t4b:.1f}s "
              f"(category/ now resolves referenced categories)")

    if args.redirects:
        print("\n[5/5] redirect stubs")
        # Titles that were rendered as real pages — never overwrite them with a stub.
        existing_titles: set[str] = {p.get("title", "") for p in meta.get("pages", [])}
        n_redir = 0
        n_skipped_real = 0
        n_unresolved = 0
        n_self = 0
        for src, tgt in redirect_map.items():
            # Source-as-real-page already serves the redirect target; counts as covered.
            if src in existing_titles:
                n_skipped_real += 1
                continue
            stub = build_redirect_stub(src, tgt, redirect_map, title_index, existing_titles)
            if not stub:
                # Either no resolvable target or self-referential
                final = _resolve_redirect_target(src, tgt, redirect_map, title_index)
                if final is None:
                    n_unresolved += 1
                else:
                    n_self += 1
                continue
            sd, sf, sh = stub
            out_path = ROOT / sd / sf
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(sh, encoding="utf-8")
            n_redir += 1
        covered = n_redir + n_skipped_real
        total = len(redirect_map)
        pct = (covered / total * 100.0) if total else 0.0
        print(f"    +{n_redir} redirect stubs written")
        print(f"    {n_skipped_real} sources already exist as full pages (no stub needed)")
        print(f"    {n_self} sources are self-referential (target == source)")
        print(f"    {n_unresolved} sources could not be resolved")
        print(f"    coverage: {covered}/{total} = {pct:.2f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
