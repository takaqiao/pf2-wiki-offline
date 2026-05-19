"""Build a merge-ready glossary supplement in the same flat {en: zh} format
used by glossary_sog.json.

Takes the intersection of:
  - glossary_wiki_confident.json   (multi-source or multi-count)
  - glossary_wiki_short_zh.json    (ZH length <= 8)
  - not already in user's glossary  (case-insensitive)
  - ZH doesn't start with common sentence-starter words

Writes:
  out/glossary_supplement.json    — {en: zh} ready to merge
  out/glossary_supplement_preview.md — human review table
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"
DEFAULT_USER = Path(r"C:\Users\Taka\Desktop\fvttpublish\pf2e-compendium-extra\glossary_sog.json")

# Heuristic: ZH that starts with any of these is probably a sentence fragment.
BAD_ZH_STARTERS = (
    "依照", "除非", "虽然", "但是", "而且", "因此", "所以", "如果", "即使",
    "这个", "那个", "这些", "那些", "一个", "一只", "一位", "一名",
    "北部", "南部", "东部", "西部", "然后", "并且",
    "它会", "他们", "她们", "我们", "你们",
    "此外", "另外", "首先", "其次", "最后",
    "是指", "代表", "表示", "指的是", "形如", "形似", "意味", "意味着",
    "来自", "生长", "位于", "专门", "可以", "应当",
    "是否", "是相对", "或说", "或以", "或脚", "不过",
    "发该", "通常", "必须", "使用", "将会",
    "当与", "当你", "当他", "当她", "当它", "当这",
    "过欺", "不过",
)


BAD_ZH_CHARS = set("|[]{}《》")
LEADING_PARTICLES = ("的", "了", "过", "着", "得", "地", "将", "被", "会", "就", "或")


def is_plausible_zh(zh: str) -> bool:
    if not zh or len(zh) > 10:
        return False
    for s in BAD_ZH_STARTERS:
        if zh.startswith(s):
            return False
    if zh[0] in LEADING_PARTICLES:
        return False
    if any(c in BAD_ZH_CHARS for c in zh):
        return False
    return True


# EN that's mostly junk — e.g. leading digits, punctuation-heavy fragments
import re
def is_plausible_en(en: str) -> bool:
    if not en:
        return False
    # leading digit + punct markers like "1、", "3、", "1e）"
    if re.match(r"^\d+[、,.\u3001\u3002\uff08\uff09a-zA-Z]?[\s\u3001\u3002\uff08\uff09,.]", en):
        return False
    if re.match(r"^\d[eE][）)]", en):
        return False
    # broken wiki link fragments like "[[ Classes"
    if "[[" in en or "]]" in en or "|" in en:
        return False
    return True


def main(argv: list[str]) -> int:
    user_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_USER
    confident = json.loads((OUT_DIR / "glossary_wiki_confident.json").read_text(encoding="utf-8"))
    short = json.loads((OUT_DIR / "glossary_wiki_short_zh.json").read_text(encoding="utf-8"))
    user = json.loads(user_path.read_text(encoding="utf-8"))
    user_ci = {k.lower().strip() for k in user}

    # Intersection: confident AND short
    candidate_ens = set(confident.keys()) & set(short.keys())

    supplement: dict[str, str] = {}
    dropped_known = 0
    dropped_sentence = 0
    dropped_en = 0
    for en in candidate_ens:
        if en.lower().strip() in user_ci:
            dropped_known += 1
            continue
        if not is_plausible_en(en):
            dropped_en += 1
            continue
        zh = confident[en]["zh"]
        if not is_plausible_zh(zh):
            dropped_sentence += 1
            continue
        supplement[en] = zh

    # Sort alphabetically, case-insensitive, to match user's glossary style
    supplement_sorted = dict(sorted(supplement.items(), key=lambda kv: kv[0].lower()))

    out_json = OUT_DIR / "glossary_supplement.json"
    out_json.write_text(json.dumps(supplement_sorted, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"User glossary:      {len(user):>6}")
    print(f"Candidates:         {len(candidate_ens):>6}  (confident ∩ short_zh)")
    print(f"  dropped (already):  {dropped_known:>6}")
    print(f"  dropped (bad EN):   {dropped_en:>6}")
    print(f"  dropped (sentence): {dropped_sentence:>6}")
    print(f"Supplement written: {len(supplement_sorted):>6}  -> {out_json.name}")

    # Preview markdown for the first 50
    lines = [
        "# Glossary supplement preview",
        "",
        f"Source: confident ∩ short_zh, minus known, minus sentence fragments.",
        f"Total new entries: **{len(supplement_sorted)}**",
        "",
        "## First 50 (alphabetical)",
        "",
        "| EN | ZH |",
        "|---|---|",
    ]
    for en, zh in list(supplement_sorted.items())[:50]:
        lines.append(f"| {en} | {zh} |")
    (OUT_DIR / "glossary_supplement_preview.md").write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
