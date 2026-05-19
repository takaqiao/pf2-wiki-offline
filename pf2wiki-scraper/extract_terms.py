"""Extract EN<->ZH term pairs from dumped wikitext JSONL files.

Reads every out/wikitext/*.jsonl and emits:
  out/glossary_wiki.json    — { "<english>": { "zh": "...", "count": N, "sources": ["pattern", ...], "examples": [title, ...] } }
  out/glossary_wiki.csv     — flat CSV for quick review
  out/extract_report.md     — per-pattern hit counts

Patterns (applied independently; duplicates merged):
  A. Template `|title=` field with ZH<sp>EN or EN<sp>ZH
  B. Bolded prose pair: `'''ZH EN'''` or `'''EN ZH'''`
  C. HTML bold/small: `<b>ZH EN</b>`, `<small>EN</small>` next to ZH
  D. Parenthetical: `ZH（EN）` or `ZH (EN)` — full-width or half-width
  E. Infobox English-name fields: `|英文名=` / `|eng=` / `|english_name=` / `|original=`
  F. `{{lang|en|EN}}` templates next to a ZH neighbor

The output is advisory — you'll want to review before merging into your real
glossary. Low-confidence single-hit entries get flagged separately.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parent
DUMP_DIR = ROOT / "out" / "wikitext"
OUT_DIR = ROOT / "out"

# Force unbuffered stdout so progress prints are visible live.
sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

# jieba for ZH segmentation. Lazy-init the dictionary on first call.
import jieba
import jieba.posseg as _pseg
jieba.setLogLevel(60)  # silence jieba prints
# Trigger init eagerly so the multi-line dict-load message shows up before our progress prints
jieba.initialize()

# jieba POS classes:
#   CONTENT = real-meaning tokens that can be part of a term
#       n=名词 nr=人名 ns=地名 nt=机构 nz=专名 nl=名词短语 ng=名素
#       v=动词 vn=动名词 vd=副动词 vi=不及物动 a=形容词 ad=副形 an=形名 ag=形素
#       eng=外文 j=简称 l=习语 i=成语 b=区别词
#   FUNCTIONAL = words that mark a phrase boundary (we stop here walking right→left)
#       p=介词 c=连词 r=代词 d=副词 t=时间 ud/uj=助词
#   TRAILING = words that may dangle at the end (skip them when finding the tail)
#       u=助词 uj=的 y=语气 k=后缀 h=前缀 q=量词 m=数词 f=方位 mq=数量
# Strict CONTENT: nouns and noun-like words only. Plain `v` (verb) is excluded
# because most term captures we care about end in a noun phrase. Verb-derived
# nouns (`vn`) are allowed.
_CONTENT_FLAGS = frozenset({
    "n", "nr", "ns", "nt", "nz", "nl", "ng",  # nouns
    "a", "ad", "an", "ag",                     # adjectives (often modifiers)
    "vn",                                      # verb-noun
    "eng", "j", "l", "i", "b", "z",            # foreign / abbrev / idiom / distinguish / state
})
FUNC_HEADS = ("p", "c", "r", "d", "t", "v")  # treat v as boundary too
TRAIL_HEADS = ("u", "y", "k", "h", "q", "m", "f", "x")


def _is_content(flag: str) -> bool:
    return flag in _CONTENT_FLAGS


def _is_func(flag: str) -> bool:
    return bool(flag) and flag[0] in FUNC_HEADS


def trim_zh_to_trailing_phrase(zh: str) -> str:
    """If `zh` is short (<=4 chars), return as-is. Otherwise jieba-segment and
    return only the trailing noun/verb phrase, skipping trailing particles
    like 中/的/着. Pulls a real term out of '环境中有强风' -> '强风',
    '你将被困在这个结界中' -> '结界'."""
    if len(zh) <= 4:
        return zh
    tokens = [(t.word, t.flag.lower()) for t in _pseg.cut(zh) if t.word.strip()]
    if not tokens:
        return zh
    # Walk right→left:
    #   1) skip dangling TRAIL particles
    #   2) collect CONTENT tokens
    #   3) stop on FUNC token
    i = len(tokens) - 1
    # Skip trailing particles
    while i >= 0 and tokens[i][1] and tokens[i][1][0] in TRAIL_HEADS:
        i -= 1
    if i < 0:
        return zh
    # Collect content tokens from i backward; stop on the first non-CONTENT token
    end = i  # last content index (inclusive)
    while i >= 0:
        _, flag = tokens[i]
        if _is_content(flag):
            i -= 1
            continue
        break
    start = i + 1
    if start > end:
        return zh
    trimmed = "".join(w for w, _ in tokens[start:end + 1])
    if len(trimmed) < 2:
        return zh
    return trimmed

# Regex helpers. Keep these atomic to avoid catastrophic backtracking.
CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
# EN phrase: 2..80 chars of letters/digits/spaces/hyphens/apostrophes (incl curly), ending on alnum
EN_PHRASE = r"[A-Za-z][A-Za-z0-9'\u2019 \-]{1,78}[A-Za-z0-9]"

# Noisy EN matches to drop: book/source codes, DC/PC/stat lines, single all-caps 3-letter tags
NOISE_EN = re.compile(
    r"^(?:AON|DC|PC|HP|XP|AC|CRB|APG|GMC|GNG|LOCG|LOWG|LOIL|LOTGB|LOAG|LOPSG|LOME|LOAP|ROE|SOT|KM|TV|EC|AoA|FoP|AV)\b"
    r"|^DC\s*\d+$"
    r"|^\d+$"
)

# HTML tags to strip before line-level parsing
HTML_JUNK = re.compile(r"</?(?:big|small|sup|sub|u|i|b|br|font|span|div)(?:\s[^>]*)?/?>|<!--.*?-->", re.IGNORECASE | re.DOTALL)
# wiki file/image links — drop whole `[[File:...|...]]` chunks
FILE_LINK = re.compile(r"\[\[(?:File|文件|图像|Image):[^\]]*\]\]", re.IGNORECASE)
# external links `[http://... label]` — keep only label
EXT_LINK = re.compile(r"\[https?://\S+\s+([^\]]+)\]")


def preclean(wt: str) -> str:
    wt = FILE_LINK.sub("", wt)
    wt = EXT_LINK.sub(r"\1", wt)
    wt = HTML_JUNK.sub(" ", wt)
    return wt


def iter_jsonl(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


# ---------- patterns ----------

# A. |title=ZH EN  or  |title=EN ZH   (one line)
# We look for Statblock-style titles where value is on same line as |title=
RE_TITLE_FIELD = re.compile(
    rf"\|\s*title\s*=\s*([^\n|]+)",
    re.IGNORECASE,
)

# B. '''ZH EN''' or '''EN ZH'''
RE_TRIPLE_BOLD = re.compile(r"'''([^'\n]{2,120})'''")

# C. <b>ZH EN</b> or <b>EN</b> near ZH
RE_HTML_BOLD = re.compile(r"<b>([^<\n]{2,120})</b>", re.IGNORECASE)

# D. parenthetical:  ZH (EN)  or  ZH（EN）
# Anchored so we require ZH chars immediately before the paren. Tight bound
# (2..12 CJK chars) — longer captures tend to grab whole clauses.
RE_PAREN = re.compile(
    rf"({CJK}{{2,12}})\s*[（(]\s*({EN_PHRASE})\s*[)）]"
)
# Inverse: EN (ZH)  e.g.  fireball（火球术）
RE_PAREN_INV = re.compile(
    rf"({EN_PHRASE})\s*[（(]\s*({CJK}{{2,12}})\s*[)）]"
)

# E. English-name infobox fields
RE_ENG_FIELD = re.compile(
    r"\|\s*(?:英文名|英文|eng|english[_ ]?name|orig(?:inal)?[_ ]?name|en[_ ]?name)\s*=\s*([^\n|]+)",
    re.IGNORECASE,
)
RE_ZH_FIELD = re.compile(
    r"\|\s*(?:中文名|name|名称|中文)\s*=\s*([^\n|]+)",
    re.IGNORECASE,
)

# F. {{lang|en|Foo}}
RE_LANG_EN = re.compile(r"\{\{\s*lang\s*\|\s*en\s*\|\s*([^}|]+)\}\}", re.IGNORECASE)


# ---------- helpers ----------

def split_mixed_line(s: str) -> tuple[str, str] | None:
    """Given a string that contains both ZH and EN spans, split into (zh, en).

    Handles:  'Rokoa的技艺 Rokoan Arts'  -> ('Rokoa的技艺', 'Rokoan Arts')
              'Aeon Stone 光阴石'         -> ('光阴石', 'Aeon Stone')
              '记住第一条规则 REMEMBER THE FIRST RULE' -> (...)
    Returns None if the line is not cleanly mixed.
    """
    s = s.strip()
    # Strip template markers like  {{action|R}}  AND any unclosed `{{...` fragments
    # (the outer regex that captures until `\n|` may cut through an open brace)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"\{\{.*$", "", s)
    s = s.strip()
    if not s:
        return None
    has_zh = re.search(CJK, s)
    has_en = re.search(r"[A-Za-z]{3,}", s)
    if not (has_zh and has_en):
        return None
    # Greedy split at first transition ZH->EN or EN->ZH
    # Walk chars; record runs
    runs: list[tuple[str, str]] = []
    buf = []
    kind = None
    def flush():
        if buf:
            runs.append((kind, "".join(buf).strip()))
    for ch in s:
        if re.match(CJK, ch):
            k = "zh"
        elif ch.isascii() and (ch.isalnum() or ch in " '-"):
            k = "en"
        else:
            k = "x"  # punctuation / other — don't switch groups
        if k == "x":
            buf.append(ch)
            continue
        if kind is None:
            kind = k
            buf.append(ch)
        elif kind == k:
            buf.append(ch)
        else:
            flush()
            kind = k
            buf = [ch]
    flush()
    # Merge: collect all ZH runs, all EN runs
    zh_parts = [t for (k, t) in runs if k == "zh" and t]
    en_parts = [t for (k, t) in runs if k == "en" and t]
    if not zh_parts or not en_parts:
        return None
    zh = " ".join(zh_parts).strip(" ，,。.·")
    en = " ".join(en_parts).strip(" ,.'-")
    # Drop if EN too short or numeric-only, or has unusual chars
    if len(en) < 3 or not re.search(r"[A-Za-z]{3,}", en):
        return None
    # Drop if EN is clearly a rarity tag like "GMC", "CRB" etc. — allow only if has 2+ tokens or looks like a real word
    if len(en) < 4 and en.isupper():
        return None
    return zh, en


# ---------- extraction core ----------

def extract_from_page(rec: dict) -> Iterator[tuple[str, str, str]]:
    """Yield (en, zh, pattern_tag)."""
    title = rec["title"]
    wt = preclean(rec["wikitext"] or "")

    # A. |title= field
    for m in RE_TITLE_FIELD.finditer(wt):
        pair = split_mixed_line(m.group(1))
        if pair:
            zh, en = pair
            yield en, zh, "A_title_field"

    # B. '''...''' bold pairs
    for m in RE_TRIPLE_BOLD.finditer(wt):
        pair = split_mixed_line(m.group(1))
        if pair:
            zh, en = pair
            yield en, zh, "B_triple_bold"

    # C. <b>...</b>
    for m in RE_HTML_BOLD.finditer(wt):
        pair = split_mixed_line(m.group(1))
        if pair:
            zh, en = pair
            yield en, zh, "C_html_bold"

    # D. ZH (EN) / ZH（EN）
    for m in RE_PAREN.finditer(wt):
        zh, en = m.group(1).strip(), m.group(2).strip()
        if len(en) >= 3:
            yield en, zh, "D_paren_ZHopenEN"
    # D'. EN (ZH)
    for m in RE_PAREN_INV.finditer(wt):
        en, zh = m.group(1).strip(), m.group(2).strip()
        if len(en) >= 3:
            yield en, zh, "D_paren_ENopenZH"

    # E. infobox: pair `|英文名=` with `|中文名=` / page title as fallback
    eng_vals = [m.group(1).strip() for m in RE_ENG_FIELD.finditer(wt)]
    zh_vals = [m.group(1).strip() for m in RE_ZH_FIELD.finditer(wt)]
    if eng_vals:
        zh_pick = zh_vals[0] if zh_vals else title
        # Clean link brackets
        zh_pick = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]", r"\1", zh_pick).strip()
        for en in eng_vals:
            en_clean = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]", r"\1", en).strip()
            if re.search(CJK, zh_pick) and re.search(r"[A-Za-z]{3,}", en_clean):
                yield en_clean, zh_pick, "E_infobox_field"

    # F. {{lang|en|Foo}} — attempt to pair with closest preceding ZH noun
    for m in RE_LANG_EN.finditer(wt):
        en = m.group(1).strip()
        # Look back up to 30 chars for a CJK chunk
        preceding = wt[max(0, m.start() - 30): m.start()]
        zh_m = re.search(rf"({CJK}{{2,15}})\s*$", preceding)
        if zh_m and len(en) >= 3:
            yield en, zh_m.group(1), "F_lang_template"


_PUNCT_STRIP = " \t\"'`’‘“”「」《》『』()（）[]{}：:；;,，.。·•*～~—-_/\\"


def norm_en(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    # Normalize curly apostrophe to ASCII
    s = s.replace("\u2019", "'")
    s = s.strip(_PUNCT_STRIP)
    return s


def norm_zh(s: str) -> str:
    s = re.sub(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]", r"\1", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(_PUNCT_STRIP)
    # Strip leading/trailing wiki bold markers
    s = re.sub(r"^'+|'+$", "", s).strip()
    return s


def is_noise_en(s: str) -> bool:
    if len(s) < 3:
        return True
    if not re.search(r"[A-Za-z]{3,}", s):
        return True
    if NOISE_EN.search(s):
        return True
    # Drop things that are mostly digits + short tag
    if re.fullmatch(r"[A-Z]{2,5}\s*\d+", s):
        return True
    return False


def is_noise_zh(s: str) -> bool:
    if len(s) < 1:
        return True
    # If the candidate ZH is really a sentence (>= 8 chars AND has stop marks), treat as noise
    if len(s) >= 10 and re.search(r"[，。；：、！？]", s):
        return True
    return False


# Common ZH leading tokens that signal we captured a sentence fragment rather than a term.
LEADING_NOISE_ZH = (
    "依照", "除非", "虽然", "但是", "而且", "因此", "所以", "如果", "即使",
    "这个", "那个", "这些", "那些", "一个", "一只", "一位", "一名",
    "北部", "南部", "东部", "西部", "然后", "并且",
    "它会", "他们", "她们", "我们", "你们",
    "此外", "另外", "首先", "其次", "最后",
)

def trim_leading_zh_noise(zh: str) -> str:
    """Strip a small set of common sentence-starter words from the front."""
    for prefix in LEADING_NOISE_ZH:
        if zh.startswith(prefix) and len(zh) > len(prefix) + 1:
            zh = zh[len(prefix):]
            break
    return zh


def main(argv: list[str]) -> int:
    files = sorted(DUMP_DIR.glob("*.jsonl"))
    if not files:
        print(f"No dump files in {DUMP_DIR}. Run dump_wikitext.py first.")
        return 1

    # en -> { zh_norm -> {count, sources, examples} }
    terms: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"count": 0, "sources": set(), "examples": []}))
    per_pattern = defaultdict(int)
    pages_scanned = 0

    for f in files:
        file_start = pages_scanned
        for rec in iter_jsonl(f):
            pages_scanned += 1
            if pages_scanned % 2000 == 0:
                print(f"  ... {pages_scanned} pages, {len(terms)} EN terms")
            for en, zh, tag in extract_from_page(rec):
                en_n = norm_en(en)
                zh_n = trim_leading_zh_noise(norm_zh(zh))
                # jieba pass: pull trailing noun phrase out of long captures
                zh_n = trim_zh_to_trailing_phrase(zh_n)
                if is_noise_en(en_n) or is_noise_zh(zh_n):
                    continue
                bucket = terms[en_n][zh_n]
                bucket["count"] += 1
                bucket["sources"].add(tag)
                if len(bucket["examples"]) < 3:
                    bucket["examples"].append(rec["title"])
                per_pattern[tag] += 1
        print(f"  scanned {f.name}: {pages_scanned} pages cumulative, {len(terms)} unique EN so far")

    # Collapse per-EN to the highest-count ZH
    glossary: dict[str, dict] = {}
    for en, zh_map in terms.items():
        best_zh, best_meta = max(zh_map.items(), key=lambda kv: kv[1]["count"])
        alternatives = {zh: m["count"] for zh, m in zh_map.items() if zh != best_zh}
        glossary[en] = {
            "zh": best_zh,
            "count": best_meta["count"],
            "sources": sorted(best_meta["sources"]),
            "examples": best_meta["examples"],
            "alternatives": alternatives or None,
        }

    # Sort by count desc
    glossary_sorted = dict(sorted(glossary.items(), key=lambda kv: -kv[1]["count"]))

    out_json = OUT_DIR / "glossary_wiki.json"
    out_json.write_text(json.dumps(glossary_sorted, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out_json}  ({len(glossary_sorted)} unique EN)")

    # Confident subset: multi-source, or multi-count, or backed by A/E patterns.
    # These are the entries worth glancing at first.
    STRONG_TAGS = {"A_title_field", "E_infobox_field"}
    confident: dict[str, dict] = {}
    for en, meta in glossary_sorted.items():
        sources = set(meta["sources"])
        if meta["count"] >= 2 or len(sources) >= 2 or (sources & STRONG_TAGS):
            confident[en] = meta
    out_conf = OUT_DIR / "glossary_wiki_confident.json"
    out_conf.write_text(json.dumps(confident, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_conf}  ({len(confident)} confident EN)")

    # Short-ZH subset (zh length <= 8): entries whose ZH looks like a compact term
    # rather than a sentence. Best for merging into a translator glossary.
    short_only = {en: m for en, m in glossary_sorted.items() if len(m["zh"]) <= 8}
    out_short = OUT_DIR / "glossary_wiki_short_zh.json"
    out_short.write_text(json.dumps(short_only, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_short}  ({len(short_only)} short-ZH EN)")

    out_csv = OUT_DIR / "glossary_wiki.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["english", "chinese", "count", "patterns", "alt_chinese", "example_titles"])
        for en, meta in glossary_sorted.items():
            alts = "; ".join(f"{k}({v})" for k, v in (meta.get("alternatives") or {}).items())
            w.writerow([
                en, meta["zh"], meta["count"], ",".join(meta["sources"]),
                alts, "; ".join(meta["examples"]),
            ])
    print(f"Wrote {out_csv}")

    report = OUT_DIR / "extract_report.md"
    lines = ["# Wiki glossary extraction report", "", f"Pages scanned: {pages_scanned}", f"Unique EN terms: {len(glossary_sorted)}", "", "## Hits per pattern", ""]
    for k, v in sorted(per_pattern.items()):
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Top 40 by frequency", "", "| EN | ZH | count | patterns |", "|---|---|---|---|"]
    for en, meta in list(glossary_sorted.items())[:40]:
        lines.append(f"| {en} | {meta['zh']} | {meta['count']} | {','.join(meta['sources'])} |")
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {report}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
