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

# [RC3] ns0 子页面指针桩 (模板:物品类型数据): pure "请点击主页面" notices with no
# content of their own — excluded from the index entirely so they stop flooding
# results (5,017 pages, e.g. 治疗药水/次等治疗药水). Matches the stripped
# soup.get_text() body; build_v2.py uses the same wording anchored on raw HTML.
SUBPAGE_POINTER_TXT_RX = re.compile(
    r"^本页面是存放物品数据的子页面[，,]\s*如果您是通过搜索栏进入本页的[，,]\s*请点击主页面[：:]"
)

# [SRCH-2] ns3500 Data:*.json pages carry no parse.categories, so infer their
# type from the title prefix instead (Data:Spells-Fireball.json → spell, …).
# Applied before the stub check so short data pages are typed correctly too.
DATA_TITLE_PREFIX_RX = re.compile(r"^(?:Data|数据):([A-Za-z]+)-")
DATA_PREFIX_TYPE = {
    "Spells": "S", "Feats": "F", "Creatures": "C", "Items": "I",
    "Traits": "R", "Conditions": "N", "Backgrounds": "B",
}

# [SRCH-4] English original name: ns0 bodies typically open with
# "<中文标题> <English Name> <类别>…"; capture that leading Latin run (after
# stripping the title prefix) so search.js can boost exact English-name hits.
EN_NAME_RX = re.compile(r"^[A-Za-z][A-Za-z0-9'’ \-]{0,58}[A-Za-z0-9'’]")

# [SRCH-1] excerpt prefix for synthesized redirect-alias entries; search.js
# detects it and renders the result row as "AC → 护甲".
REDIRECT_EXCERPT_PREFIX = "重定向 → "

NS_TO_DIR = {
    0: "pages", 4: "project", 14: "category", 102: "pages", 3500: "data",
}

SKIP_TITLE_PREFIXES = (
    "Template:", "模板:", "File:", "文件:", "Module:", "模块:",
    "MediaWiki:", "Form:", "表单:",
)

# --- Type inference from parse.categories ---
# Each entry: (type_name, code_char, set_of_categories_that_signal_it).
# Order matters: first match wins. Tighter / more-specific types come first.
# Type names align with search.js TYPE_INFO labels (feat/spell/creature/...).
TYPE_RULES: list[tuple[str, str, set[str]]] = [
    # Spell: 法术 / 戏法 (cantrip). Many spells also have 'PC' but 法术 is canonical.
    ("spell", "S", {"法术", "戏法"}),
    # Feat: 专长 + variants (职业专长 / 族裔专长 / 通用专长 / 技能专长 / 通用专长).
    ("feat", "F", {"专长", "职业专长", "族裔专长", "通用专长", "技能专长"}),
    # Class: 职业 (top-level class page).
    ("class", "L", {"职业"}),
    # Ancestry: 族裔 (top-level race / lineage page).
    ("ancestry", "A", {"族裔"}),
    # Background: 背景 (character background).
    ("background", "B", {"背景"}),
    # Deity: 信仰 / 主流神祇 / 其他神祇 / 信仰和哲学.
    ("deity", "G", {"信仰", "信仰和哲学", "主流神祇", "其他神祇"}),
    # Condition: 状态.
    ("condition", "N", {"状态"}),
    # Creature: size category is the canonical bestiary marker. Real PF2 sizes are
    # 超小型/小型/中型/大型/巨型/超大型 (NOT the dead 微型/超巨型/极巨型);
    # 生物子类 catches sub-type pages too.
    ("creature", "C", {"超小型", "小型", "中型", "大型", "巨型", "超大型", "生物子类"}),
    # Item: 物品 + 物品导航 + base/variant categories + the …子页面 variant tags
    # (which hold ~6000 magic-item variants the wiki indexes under 物品导航).
    ("item", "I", {
        "物品", "物品导航", "装备", "穿戴物品", "手持物品", "辅助物品",
        "基础武器", "基础护甲",
        "物品子页面", "穿戴物品子页面", "手持物品子页面", "特殊魔法武器子页面",
    }),
    # Location: 地理 (geography / regions).
    ("location", "P", {"地理"}),
    # Action: 动作 / 基础动作 / 技能动作.
    ("action", "T", {"动作", "基础动作", "技能动作", "通用技能动作"}),
    # Trait: 特征 (top-level traits hub; individual 'X（特征）' is noise, skip).
    ("trait", "R", {"特征"}),
]

DEFAULT_TYPE = ("other", "O")

# Legend embedded in types.js so search.js does not need to keep the map in
# sync — single source of truth.
TYPE_LEGEND: dict[str, str] = {
    "F": "feat", "S": "spell", "C": "creature", "I": "item",
    "G": "deity", "B": "background", "L": "class", "A": "ancestry",
    "P": "location", "N": "condition", "T": "action", "R": "trait",
    "U": "stub", "O": "other",
}


def infer_type(categories: list, is_stub: bool = False) -> str:
    """Return single-char type code based on parse.categories list.

    `categories` is the raw list from parsed JSON: [{'category': '...'}, ...].
    Stubs always map to 'U' regardless of categories so the UI can group them
    separately.
    """
    if is_stub:
        return "U"
    cat_set = {c.get("category", "") for c in categories if isinstance(c, dict)}
    for _name, code, signals in TYPE_RULES:
        if cat_set & signals:
            return code
    return DEFAULT_TYPE[1]

EN_STOP = {"a", "an", "and", "or", "of", "to", "the", "in", "on", "at", "is",
           "as", "by", "for", "be", "it", "with", "from", "this", "that"}
ZH_STOP_CHARS = set("的了是在与和及或但因為为以及他她它我你们们之于而")

CJK_RANGE = (
    (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x2A6DF),
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'_-]{1,30}")
WHITESPACE_RE = re.compile(r"\s+")
# ns=3500 Data pages start with a doc-stub preamble; drop it from excerpts.
DATA_DOC_RE = re.compile(r"^此数据的文档可以在.*?创建\s*")


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
    """Yield (ns, pageid, title, body_text, excerpt, categories, links) from parsed JSON."""
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
            # Drop the license/attribution boxes that otherwise dominate ~40% of
            # excerpts ("本条目内容来自《...》规则内容版权为PAZIO所有...社区使用政策").
            # ONLY the .well.quote-success / .quote-primary callouts are pure
            # license boilerplate — bare .well holds legitimate content, leave it.
            for tag in soup.select(".well.quote-success, .quote-primary"):
                tag.decompose()
            # [SRCH-3] Drop the '规则导航' navigation template — a top-level
            # <div class="hidden-sm hidden-xs"> of ~2,200 chars that otherwise
            # swallows the whole body[:600] index window AND the excerpt on 87
            # core rules pages (伤害类型/护甲/遭遇模式…). Only divs whose text
            # *starts* with 规则导航 are removed; the responsive classes alone
            # are NOT a safe signal (they can wrap real content elsewhere).
            for tag in soup.select("div.hidden-sm.hidden-xs"):
                if tag.get_text(strip=True).startswith("规则导航"):
                    tag.decompose()
            body_text = soup.get_text(" ", strip=True)
            body_text = WHITESPACE_RE.sub(" ", body_text)
            # Strip the ns=3500 data-page doc preamble ("此数据的文档可以在…创建").
            body_text = DATA_DOC_RE.sub("", body_text).strip()
            # Wider window so search.js can anchor the excerpt on the query term.
            excerpt = make_excerpt(body_text, 200)
            categories = parse.get("categories", []) or []
            links = parse.get("links", []) or []
            yield doc.get("ns", 0), doc.get("pageid"), title, body_text, excerpt, categories, links
            n += 1
            if limit and n >= limit:
                return


def compute_inlinks(limit: int | None = None) -> dict[str, int]:
    """Pass 1: scan all parsed JSON and tally how often each title is linked-to.

    Uses parse.links (MediaWiki's resolved internal-link list) so anchors,
    redirects, and templated links all count. Only links with exists=True
    in indexable namespaces (0/14/102/3500) are counted; template/file links
    are ignored. The returned dict maps page title -> inbound-link count.
    """
    counts: dict[str, int] = {}
    allowed_ns = {0, 14, 102, 3500}
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
            if should_skip(doc.get("title", "")):
                continue
            parse = doc.get("parse", {})
            for link in parse.get("links", []) or []:
                if not isinstance(link, dict):
                    continue
                if not link.get("exists"):
                    continue
                if link.get("ns") not in allowed_ns:
                    continue
                t = link.get("title", "")
                if not t or should_skip(t):
                    continue
                counts[t] = counts.get(t, 0) + 1
            n += 1
            if limit and n >= limit:
                return counts
    return counts


def build(out_dir: Path, limit: int | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    SHARDS_DIR.mkdir(exist_ok=True)

    # Pass 1: inbound-link tally so popularity is available before titles are
    # written. Each page contributes its parse.links targets once per occurrence;
    # the resulting count approximates "how many other wiki pages reference me",
    # which we use as a tiebreaker when two results share a relevance score.
    print("[1/2] computing inbound-link popularity …")
    t_pop = time.time()
    inlinks = compute_inlinks(limit=limit)
    print(f"      {len(inlinks)} distinct titles linked, {time.time()-t_pop:.1f}s")

    titles: list[dict] = []
    bigram_posts: dict[str, list[int]] = {}
    word_posts: dict[str, list[int]] = {}
    type_codes: list[str] = []  # one char per title, aligned to titles[i]
    popularity: list[int] = []  # inbound-link count, aligned to titles[i]

    t0 = time.time()
    seen_id = 0
    stub_count = 0
    pointer_skipped = 0   # [RC3] subpage pointer stubs dropped
    en_named = 0          # [SRCH-4] entries that got an English-name field
    title_to_idx: dict[str, int] = {}  # title -> entry id (== array index)
    print("[2/2] tokenising titles + bodies …")

    for ns, pageid, title, body, excerpt, categories, _links in iter_parsed(limit=limit):
        # [RC3] 物品数据 subpage pointer stubs: pure "click through to parent"
        # notices — keep them out of the index entirely (the parent page is
        # the real result; build_v2.py meta-refreshes the stub HTML to it).
        if ns == 0 and SUBPAGE_POINTER_TXT_RX.match(body):
            pointer_skipped += 1
            continue
        href = page_href(ns, title)
        kind = "d" if ns == 3500 else ("c" if ns == 14 else "p")
        is_stub = len(body) < STUB_BODY_THRESHOLD
        if is_stub:
            stub_count += 1

        # [SRCH-2] ns3500 data pages: type from title prefix (before the stub
        # fallback, so short data pages are typed too); else category-based.
        type_code = None
        if ns == 3500:
            m = DATA_TITLE_PREFIX_RX.match(title)
            if m:
                type_code = DATA_PREFIX_TYPE.get(m.group(1))
        if type_code is None:
            type_code = infer_type(categories, is_stub=is_stub)

        # [SRCH-4] English original name — body head is "<标题> <English> …".
        en_name = ""
        if kind == "p" and body.startswith(title):
            m = EN_NAME_RX.match(body[len(title):].lstrip())
            if m:
                en_name = m.group(0).strip(" -")

        entry_id = seen_id
        seen_id += 1
        entry = {"i": entry_id, "t": title, "h": href, "k": kind, "e": excerpt}
        if len(en_name) >= 2:
            entry["n"] = en_name
            en_named += 1
        titles.append(entry)
        type_codes.append(type_code)
        popularity.append(inlinks.get(title, 0))
        if title not in title_to_idx:
            title_to_idx[title] = entry_id

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

    # ------------------------------------------------------------------
    # [SRCH-1] Synthesize index entries for redirect aliases (AC→护甲,
    # 巨龙→龙, 挥砍→伤害类型 …). redirect_map values are '' for terminal
    # targets, so chains (alias→alias→page) are collapsed by following
    # non-empty hops only; aliases that shadow a real indexed title, or
    # whose terminal target is not indexed, are skipped. Entries reuse the
    # target's href/type/popularity; the alias title itself is tokenised
    # into the inverted index. Alias ids are appended after all page ids in
    # ascending order, so posting lists stay sorted (search.js intersects
    # sorted arrays).
    # ------------------------------------------------------------------
    alias_added = 0
    alias_skipped = 0
    redirect_map: dict[str, str] = {}
    try:
        meta = json.loads(META_FILE.read_text(encoding="utf-8"))
        redirect_map = meta.get("redirect_map", {}) or {}
    except Exception as e:
        print(f"      WARNING: cannot load redirect_map from {META_FILE}: {e}")

    def _terminal_target(t: str) -> str:
        seen: set[str] = set()
        while t and redirect_map.get(t) and t not in seen and len(seen) < 10:
            seen.add(t)
            t = redirect_map[t]
        return t

    for alias in sorted(redirect_map.keys()):
        if not alias or should_skip(alias) or alias in title_to_idx:
            continue  # empty, non-indexable, or shadows a real page title
        final = _terminal_target(redirect_map.get(alias, ""))
        tgt_idx = title_to_idx.get(final) if final else None
        if tgt_idx is None:
            alias_skipped += 1  # empty target or terminal target not indexed
            continue
        entry_id = seen_id
        seen_id += 1
        titles.append({
            "i": entry_id, "t": alias, "h": titles[tgt_idx]["h"], "k": "p",
            "e": REDIRECT_EXCERPT_PREFIX + final,
        })
        type_codes.append(type_codes[tgt_idx])
        popularity.append(popularity[tgt_idx])
        for w in set(tokenize_latin(alias)):
            word_posts.setdefault(w, []).append(entry_id)
        for bg in set(cjk_bigrams(alias)):
            bigram_posts.setdefault(bg, []).append(entry_id)
        alias_added += 1
    print(f"      [SRCH-1] redirect aliases: +{alias_added} entries, "
          f"{alias_skipped} skipped (empty/unindexed target); "
          f"[RC3] pointer stubs dropped: {pointer_skipped}; "
          f"[SRCH-4] en-name fields: {en_named}")

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
    # `pop` is a parallel array of inbound-link counts (one int per item, same
    # ordering as items[i]); search.js consults it as a secondary sort key when
    # multiple results share a relevance score, so "战士" beats "战士专长(2e)"
    # because the bare class page is linked to far more often.
    titles_payload = {"v": 2, "items": titles, "pop": popularity}
    titles_js = "window.__PF2_TITLES = " + json.dumps(titles_payload, ensure_ascii=False, separators=(",", ":")) + ";"
    (out_dir / "titles.js").write_text(titles_js, encoding="utf-8")

    # Write types.js — single string of type codes aligned 1:1 to titles[i].
    # search.js reads window.__PF2_TYPES.{codes, legend} and renders type badges.
    types_payload = {
        "v": 2,
        "n": len(type_codes),
        "codes": "".join(type_codes),
        "legend": TYPE_LEGEND,
    }
    (out_dir / "types.js").write_text(
        "window.__PF2_TYPES = "
        + json.dumps(types_payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )

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
        "n_aliases": alias_added,             # [SRCH-1] synthesized redirect entries
        "n_pointer_skipped": pointer_skipped,  # [RC3] subpage pointer stubs dropped
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
    # Type distribution (code -> count) for quick inference QA.
    type_dist: dict[str, int] = {}
    for c in type_codes:
        type_dist[c] = type_dist.get(c, 0) + 1
    dist_pretty = ", ".join(
        f"{TYPE_LEGEND.get(c, c)}={n}"
        for c, n in sorted(type_dist.items(), key=lambda x: -x[1])
    )

    # Popularity stats — useful sanity check that inbound-link counts landed.
    pop_max = max(popularity) if popularity else 0
    pop_nz = sum(1 for p in popularity if p > 0)
    top_pop = sorted(
        ((p, titles[i]["t"]) for i, p in enumerate(popularity) if p > 0),
        reverse=True,
    )[:5]
    top_pop_str = ", ".join(f"{t}({p})" for p, t in top_pop) if top_pop else "(none)"

    print(f"\n[done] {len(titles)} entries ({alias_added} aliases, {pointer_skipped} pointer stubs dropped), "
          f"{stub_count} stubs, {len(bigram_posts)} bigrams, {len(word_posts)} words")
    print(f"       titles.js: {sizes['titles.js']/1024/1024:.1f} MB")
    print(f"       shards total: {sizes['shards_total']/1024/1024:.1f} MB ({len(bg_shard_files)}b + {len(w_shard_files)}w)")
    print(f"       types.js distribution: {dist_pretty}")
    print(f"       popularity: {pop_nz}/{len(titles)} pages linked-to, max={pop_max}; top: {top_pop_str}")
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
