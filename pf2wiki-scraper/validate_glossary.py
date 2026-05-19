"""Systematic batch validation of glossary.json.

Produces a categorized report of suspicious entries, per-category. Runs are
read-only by default; pass --apply <category> to auto-delete entries in a
specific category. Entries that survive every check are considered good.

Detection categories (CHECK_* functions):
  T1_truncated_multi_word    Multi-word EN whose ZH equals the ZH of one of its
                             single-word component EN entries (likely captured
                             only a suffix noun).
  T2_zh_too_short_for_en     EN has N content words but ZH has < N CJK chars.
  T3_zh_is_generic_tail      ZH is a single 2-char generic tail word (能力/动作/
                             效果/地点/生物/术语) while EN has a modifier.
  F1_orphan_suffix_chars     ZH starts/ends with a suspicious particle we missed
                             (中/的/等/啊/吧 at end; 之/其 at start with >=2
                             content chars remaining).
  F2_stop_substring          ZH contains a sentence-marker string (例如, 比如,
                             注意, 警告, 译者注).
  X1_en_all_upper_short      EN is 2-4 letters all-caps (book codes: CRB, APG).
  X2_en_contains_artifact    EN contains wiki artifacts (<ref>, <!--, etc.).
  X3_zh_contains_english     ZH contains a 3+ letter English word (extractor
                             crossed a boundary).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

MAIN = Path(r"C:\Users\Taka\Desktop\fvtt\glossary.json")
OUT_DIR = Path(__file__).resolve().parent / "out"
OUT_DIR.mkdir(exist_ok=True)

CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# EN content-word detector: skip short grammatical words.
EN_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "by", "with", "from", "as", "is", "was", "be", "been",
}


def en_content_tokens(en: str) -> list[str]:
    toks = [t for t in re.split(r"[ \-]", en.strip().lower()) if t]
    return [t for t in toks if t not in EN_STOPWORDS and t.isalpha()]


def cjk_chars(zh: str) -> int:
    return sum(1 for c in zh if CJK_RE.match(c))


def check_T1(g: dict[str, object]) -> list[tuple[str, str, str]]:
    """Multi-word EN with ZH matching the ZH of a shorter-EN entry.

    e.g. "Rewrite Possibility": "可能性"  and  "Possibility": "可能性"
         -> the longer entry is a truncation.
    """
    suspicious: list[tuple[str, str, str]] = []
    # Index single-word (and 2-word short) EN -> ZH (string values only)
    by_en: dict[str, str] = {}
    for en, v in g.items():
        if isinstance(v, str):
            by_en[en.lower()] = v
    for en, v in g.items():
        if not isinstance(v, str):
            continue
        toks = en_content_tokens(en)
        if len(toks) < 2:
            continue
        # Check if any single suffix token has the same ZH
        for suffix_len in range(1, len(toks)):
            suffix = " ".join(toks[-suffix_len:])
            if suffix == en.lower().strip():
                continue
            other = by_en.get(suffix)
            if other and other == v:
                suspicious.append((en, v, f"shares ZH with '{suffix}'"))
                break
    return suspicious


def check_T2(g: dict[str, object]) -> list[tuple[str, str, str]]:
    """EN content words >= 3 but ZH CJK chars <= half of that (truncation)."""
    suspicious = []
    for en, v in g.items():
        if not isinstance(v, str):
            continue
        toks = en_content_tokens(en)
        if len(toks) < 3:
            continue
        zc = cjk_chars(v)
        if zc <= len(toks) // 2:
            suspicious.append((en, v, f"{len(toks)} EN words vs {zc} CJK chars"))
    return suspicious


GENERIC_TAILS = {
    # Very generic nouns — when EN has a modifier but ZH is only this, likely truncation.
    "能力", "动作", "效果", "地点", "生物", "术语", "法术", "技能", "状态",
    "物品", "符文", "武器", "护甲", "区域", "环境", "位置", "世界", "位面",
    "名字", "名称", "身份", "种类", "类型", "人物", "角色", "数据", "信息",
    "特征", "特性", "能力值", "点数",
    "可能性", "结果", "选择", "方式", "方法", "过程", "时间", "空间",
}


def check_T3(g: dict[str, object]) -> list[tuple[str, str, str]]:
    """EN has >=2 content words, ZH is exactly one of the generic-tail nouns."""
    suspicious = []
    for en, v in g.items():
        if not isinstance(v, str):
            continue
        toks = en_content_tokens(en)
        if len(toks) < 2:
            continue
        if v in GENERIC_TAILS:
            suspicious.append((en, v, f"generic-tail ZH for {len(toks)}-word EN"))
    return suspicious


F1_END_PARTICLES = ("中", "等", "啊", "吧", "呀", "哟", "呢", "嘛")
F1_START_FRAGS = ("之", "其", "一", "某", "此")


def check_F1(g: dict[str, object]) -> list[tuple[str, str, str]]:
    suspicious = []
    for en, v in g.items():
        if not isinstance(v, str) or len(v) < 2:
            continue
        if v.endswith(F1_END_PARTICLES) and cjk_chars(v) >= 3:
            suspicious.append((en, v, f"ends with particle {v[-1]}"))
            continue
        if v.startswith(F1_START_FRAGS):
            rest = v[1:]
            if cjk_chars(rest) >= 2:
                suspicious.append((en, v, f"starts with fragment {v[0]}"))
    return suspicious


# F2 is precision-focused: only entries that are *clearly* sentence fragments,
# not legitimate terms that happen to contain the substring (e.g. `warning` ->
# `警告` is good; `A Wary Warning` -> `警告` is a truncation but belongs in T1).
F2_PREFIX_NOISE = ("例如", "比如", "请",)
F2_CONTAINS_NOISE = ("译者注", "译注", "注：", "编按", "按：")


def check_F2(g: dict[str, object]) -> list[tuple[str, str, str]]:
    suspicious = []
    for en, v in g.items():
        if not isinstance(v, str):
            continue
        if v.startswith(F2_PREFIX_NOISE):
            suspicious.append((en, v, f"starts with '{v[:2]}'"))
            continue
        for s in F2_CONTAINS_NOISE:
            if s in v:
                suspicious.append((en, v, f"contains '{s}'"))
                break
    return suspicious


def check_X1(g: dict[str, object]) -> list[tuple[str, str, str]]:
    BOOK_CODES = {
        "CRB", "APG", "GMC", "GNG", "LOCG", "LOWG", "LOIL", "LOTGB", "LOAG",
        "LOPSG", "LOME", "LOAP", "ROE", "SOT", "AOE", "FOP", "AV", "KM",
        "AON", "DC", "PC", "HP", "XP", "AC", "TV", "EC",
    }
    suspicious = []
    for en, v in g.items():
        if not isinstance(v, str):
            continue
        compact = re.sub(r"[^A-Za-z]", "", en)
        if compact in BOOK_CODES:
            suspicious.append((en, v, "EN is a book/stat code"))
    return suspicious


X2_ARTIFACT = re.compile(r"</?\w+>|<!--|-->|&\w+;|\{\{|\}\}|\[\[|\]\]|\|\|")


def check_X2(g: dict[str, object]) -> list[tuple[str, str, str]]:
    suspicious = []
    for en, v in g.items():
        if not isinstance(v, str):
            continue
        if X2_ARTIFACT.search(en) or X2_ARTIFACT.search(v):
            suspicious.append((en, v, "contains wiki/html artifact"))
    return suspicious


def check_X3(g: dict[str, object]) -> list[tuple[str, str, str]]:
    suspicious = []
    en_word_re = re.compile(r"[A-Za-z]{3,}")
    for en, v in g.items():
        if not isinstance(v, str):
            continue
        m = en_word_re.search(v)
        if m:
            suspicious.append((en, v, f"ZH contains EN word '{m.group()}'"))
    return suspicious


CHECKS = {
    "T1_truncated_multi_word": check_T1,
    "T2_zh_too_short_for_en": check_T2,
    "T3_zh_is_generic_tail": check_T3,
    "F1_orphan_suffix_chars": check_F1,
    "F2_stop_substring": check_F2,
    "X1_en_all_upper_short": check_X1,
    "X2_en_contains_artifact": check_X2,
    "X3_zh_contains_english": check_X3,
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply-delete", action="append", default=None,
                    help="Category key to DELETE entries of (repeatable). Off by default.")
    ap.add_argument("--limit", type=int, default=40, help="Sample rows per category in report")
    args = ap.parse_args(argv)

    g = json.loads(MAIN.read_text(encoding="utf-8"))
    before = len(g)
    results: dict[str, list[tuple[str, str, str]]] = {}
    for name, fn in CHECKS.items():
        print(f"running {name}...", flush=True)
        results[name] = fn(g)
        print(f"  -> {len(results[name])} flagged", flush=True)

    # Deduplicate: same EN may trigger in multiple categories
    flagged_by_en: dict[str, set[str]] = defaultdict(set)
    for cat, items in results.items():
        for en, _v, _why in items:
            flagged_by_en[en].add(cat)

    # Deletion phase
    deletions: list[tuple[str, str, str]] = []  # (en, zh, category)
    if args.apply_delete:
        to_delete: set[str] = set()
        for cat in args.apply_delete:
            if cat not in CHECKS:
                print(f"Unknown category: {cat}")
                return 2
            for en, zh, _why in results[cat]:
                if en in g:
                    to_delete.add(en)
                    deletions.append((en, str(g[en]), cat))
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = MAIN.with_suffix(f".json.bak.{ts}")
        shutil.copy2(MAIN, backup)
        for en in to_delete:
            del g[en]
        MAIN.write_text(json.dumps(g, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nDeleted {len(to_delete)} entries. Backup: {backup.name}")
        print(f"Glossary: {before} -> {len(g)} entries")

    # Report
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = OUT_DIR / f"validate_report_{ts}.md"
    lines = [
        "# Glossary validation report",
        f"Run: {ts}",
        f"Target: `{MAIN}`",
        f"Total entries: {before}",
        "",
        "## Summary",
        "",
        "| Category | Count |",
        "|---|---|",
    ]
    for cat, items in results.items():
        lines.append(f"| `{cat}` | {len(items)} |")

    if args.apply_delete and deletions:
        lines += ["", "## Deleted entries", ""]
        lines += ["| EN | ZH | category |", "|---|---|---|"]
        for en, zh, cat in deletions[:200]:
            lines.append(f"| `{en}` | {zh!r} | {cat} |")
        if len(deletions) > 200:
            lines.append(f"| ... | ... ({len(deletions)-200} more) | |")

    for cat, items in results.items():
        lines += ["", f"## {cat} ({len(items)})", ""]
        if not items:
            continue
        lines += ["| EN | ZH | reason |", "|---|---|---|"]
        for en, zh, why in items[:args.limit]:
            lines.append(f"| `{en}` | {zh!r} | {why} |")
        if len(items) > args.limit:
            lines.append(f"| ... | ... ({len(items) - args.limit} more) | |")
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {report}")

    print("\nSummary:")
    for cat, items in results.items():
        print(f"  {cat}: {len(items)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
