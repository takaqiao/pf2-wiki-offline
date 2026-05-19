"""Merge wiki-extracted terms into the main translator glossary.

Target:  C:\\Users\\Taka\\Desktop\\fvtt\\glossary.json
Source:  out/glossary_wiki_short_zh.json  (short ZH subset, intersected with a
         quality gate so single-hit sentence fragments don't leak in)

Policy (per user instruction 2026-04-19):
  * Wiki content wins.
  * ZH candidates are sorted by count desc (most-frequent translation first).
  * Errata (single wiki candidate): store as scalar string — overwrites any
    existing main-glossary value.
  * Polysemy (multiple comparable wiki candidates): store as a JSON list,
    ordered by count desc. If the pre-existing main value isn't in the wiki
    candidate set, it is appended to the list (user's hand-curated variant
    preserved at the tail).
  * Matching is case-insensitive against the existing main glossary keys;
    when we hit, the original-case key is kept.

A timestamped backup of glossary.json is written before any change.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WIKI_SRC = ROOT / "out" / "glossary_wiki_short_zh.json"
# Main glossary lives at the fvtt workspace root, one level above `fvttpublish`.
MAIN_GLOSSARY = Path(r"C:\Users\Taka\Desktop\fvtt\glossary.json")

# Quality gate for which wiki entries to import.
#
# Two tiers:
#   * NEW entries (EN not in main glossary): accept count>=1 — most count=1
#     hits are legitimate rare terms (one-off spells, NPC names, locations).
#     The fragment heuristic + short-ZH filter + EN sanity is enough.
#   * OVERWRITES of existing curated entries: require strong signal — user's
#     hand translation shouldn't be replaced by a low-confidence wiki hit.
STRONG_TAGS = {"A_title_field", "E_infobox_field"}
ADD_MIN_COUNT = 1
OVERWRITE_MIN_COUNT = 8
MAX_ZH_LEN = 8
MIN_ZH_LEN = 2

# Polysemy threshold: alternative ZH survives only if its count is at least
# this fraction of the best count (and meets MIN_ALT_ABSOLUTE absolute).
ALT_RATIO = 0.40
MIN_ALT_ABSOLUTE = 3

# ZH tokens that almost always indicate a sentence fragment, not a clean term
# — either leading connectives/particles, or trailing verb-glue words.
FRAGMENT_PREFIXES = (
    "和", "或", "与", "的", "在", "就", "并", "也", "还",
    "如同", "就是", "是", "为", "被", "将", "已", "要",
    "如果", "即使", "但", "而",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
)
FRAGMENT_SUFFIXES = (
    "的", "地", "得", "了", "着", "过", "而", "与", "和", "或",
    "之", "上", "下", "中", "内", "外", "时", "后", "前",
    "为", "是", "有", "会",
)
# Characters that reveal a ZH is mid-sentence: pronouns / determiners
SENTENCE_MARKERS = re.compile(r"[你我他她它们这那某][^\u4e00-\u9fff]*|^这个|^那个")


def looks_like_fragment(zh: str) -> bool:
    """Heuristic: strings that start or end with stopword connectives or contain
    sentence-level markers are almost certainly not clean terms."""
    if zh.startswith(FRAGMENT_PREFIXES):
        return True
    if zh.endswith(FRAGMENT_SUFFIXES):
        return True
    if SENTENCE_MARKERS.search(zh):
        return True
    return False


def is_add_quality(meta: dict) -> bool:
    """Accept standard for NEW entries (EN not already in main glossary)."""
    return meta["count"] >= ADD_MIN_COUNT


def is_overwrite_quality(meta: dict) -> bool:
    """Higher bar for replacing an existing hand-curated main entry."""
    if meta["count"] >= OVERWRITE_MIN_COUNT:
        return True
    if set(meta["sources"]) & STRONG_TAGS and meta["count"] >= 3:
        return True
    return False


# EN sanity: drop strings that look like HTML residue or sentence fragments
EN_BAD_SUBSTR = re.compile(r"</?\w+>|<!--|-->|&\w+;")
EN_SENTENCE_WORDS = (
    "using ", "when ", "while ", "during ", "after ", "before ",
    "how to ", "what ", "where ",
)


def is_en_candidate(en: str) -> bool:
    if EN_BAD_SUBSTR.search(en):
        return False
    low = en.lower()
    if low.startswith(EN_SENTENCE_WORDS):
        return False
    # Drop very long sentence-like EN (>10 words) — wiki captures a whole phrase
    if en.count(" ") > 10:
        return False
    return True


def is_zh_candidate(zh: str, en: str = "") -> bool:
    if not zh:
        return False
    if len(zh) < MIN_ZH_LEN or len(zh) > MAX_ZH_LEN:
        return False
    if re.search(r"[，。；：、！？]", zh):
        return False
    if not re.search(r"[\u4e00-\u9fff]", zh):
        return False
    if looks_like_fragment(zh):
        return False
    # Truncation check: if EN has 4+ words, ZH shouldn't be 2 chars (e.g. "Lady
    # Seleenae of House Damaq" -> "莱迪" means we caught only "Lady")
    if en and en.count(" ") >= 4 and len(zh) <= 2:
        return False
    return True


def build_candidates(meta: dict, en: str = "") -> list[tuple[str, int]]:
    """Return [(zh, count), ...] sorted by count desc, filtered for quality."""
    best_zh = meta["zh"]
    best_count = meta["count"]
    if not is_zh_candidate(best_zh, en):
        return []
    cands: list[tuple[str, int]] = [(best_zh, best_count)]
    alts = meta.get("alternatives") or {}
    for alt_zh, alt_count in alts.items():
        if not is_zh_candidate(alt_zh, en):
            continue
        if alt_count < MIN_ALT_ABSOLUTE:
            continue
        if alt_count < best_count * ALT_RATIO:
            continue
        cands.append((alt_zh, alt_count))
    # Sort desc by count, stable so first (best) wins on ties
    cands.sort(key=lambda kv: -kv[1])
    # Dedup while preserving order
    seen = set()
    uniq: list[tuple[str, int]] = []
    for zh, c in cands:
        if zh in seen:
            continue
        seen.add(zh)
        uniq.append((zh, c))
    return uniq


def case_insensitive_index(d: dict[str, object]) -> dict[str, str]:
    """Lowercase-normalized EN -> original-case key."""
    idx: dict[str, str] = {}
    for k in d:
        idx.setdefault(k.lower(), k)
    return idx


def main() -> int:
    if not WIKI_SRC.exists():
        print(f"Missing wiki source: {WIKI_SRC}")
        return 1
    if not MAIN_GLOSSARY.exists():
        print(f"Missing main glossary: {MAIN_GLOSSARY}")
        return 1

    wiki = json.loads(WIKI_SRC.read_text(encoding="utf-8"))
    main = json.loads(MAIN_GLOSSARY.read_text(encoding="utf-8"))
    original_count = len(main)

    idx = case_insensitive_index(main)

    # Backup before writing anything.
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = MAIN_GLOSSARY.with_suffix(f".json.bak.{ts}")
    shutil.copy2(MAIN_GLOSSARY, backup)
    print(f"Backup: {backup}")

    stats = {
        "inspected": 0,
        "skipped_bad_en": 0,
        "skipped_bad_zh": 0,
        "skipped_low_quality_for_overwrite": 0,
        "overwrote_errata": 0,
        "made_polysemy": 0,
        "no_op_match": 0,
        "added_new_scalar": 0,
        "added_new_list": 0,
    }
    errata_samples: list[tuple[str, object, str]] = []  # (en, before, after)
    polysemy_samples: list[tuple[str, object, object]] = []
    new_samples: list[tuple[str, object]] = []

    for en, meta in wiki.items():
        stats["inspected"] += 1
        if not is_en_candidate(en):
            stats["skipped_bad_en"] += 1
            continue
        cands = build_candidates(meta, en)
        if not cands:
            stats["skipped_bad_zh"] += 1
            continue

        existing_key = idx.get(en.lower())
        if existing_key is not None:
            existing = main[existing_key]
            existing_set: set[str]
            if isinstance(existing, list):
                existing_set = {str(x) for x in existing}
            else:
                existing_set = {str(existing)}

            # Check if wiki agrees with existing — if any candidate matches, no-op.
            cand_set = {zh for zh, _ in cands}
            if existing_set & cand_set:
                stats["no_op_match"] += 1
                continue

            # Higher bar to overwrite a curated entry.
            if not is_overwrite_quality(meta):
                stats["skipped_low_quality_for_overwrite"] += 1
                continue

            if len(cands) == 1:
                new_zh = cands[0][0]
                main[existing_key] = new_zh
                stats["overwrote_errata"] += 1
                if len(errata_samples) < 30:
                    errata_samples.append((existing_key, existing, new_zh))
            else:
                # polysemy: list, wiki candidates first, append existing if missing
                zh_list = [zh for zh, _ in cands]
                for ez in existing_set:
                    if ez not in zh_list:
                        zh_list.append(ez)
                new_val: object = zh_list if len(zh_list) > 1 else zh_list[0]
                main[existing_key] = new_val
                stats["made_polysemy"] += 1
                if len(polysemy_samples) < 30:
                    polysemy_samples.append((existing_key, existing, new_val))
        else:
            if len(cands) == 1:
                main[en] = cands[0][0]
                stats["added_new_scalar"] += 1
                if len(new_samples) < 10:
                    new_samples.append((en, cands[0][0]))
            else:
                zh_list = [zh for zh, _ in cands]
                main[en] = zh_list
                stats["added_new_list"] += 1
                if len(new_samples) < 10:
                    new_samples.append((en, zh_list))
            # Keep index current so subsequent case-variants collide correctly
            idx[en.lower()] = en

    # Write back with stable sort: keep original order for existing keys, append new keys.
    MAIN_GLOSSARY.write_text(
        json.dumps(main, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_lines = [
        "# Merge report",
        "",
        f"Source: `{WIKI_SRC.name}` ({len(wiki)} entries)",
        f"Target: `{MAIN_GLOSSARY}` ({original_count} -> {len(main)} entries)",
        f"Backup: `{backup.name}`",
        "",
        "## Stats",
        "",
    ]
    for k, v in stats.items():
        report_lines.append(f"- **{k}**: {v}")
    if errata_samples:
        report_lines += ["", "## Errata samples (overwrote existing)", "", "| EN | before | after |", "|---|---|---|"]
        for en, before, after in errata_samples:
            report_lines.append(f"| {en} | {before!r} | {after!r} |")
    if polysemy_samples:
        report_lines += ["", "## Polysemy samples", "", "| EN | before | after |", "|---|---|---|"]
        for en, before, after in polysemy_samples:
            report_lines.append(f"| {en} | {before!r} | {after!r} |")
    if new_samples:
        report_lines += ["", "## Newly added samples", "", "| EN | value |", "|---|---|"]
        for en, val in new_samples:
            report_lines.append(f"| {en} | {val!r} |")
    report = ROOT / "out" / "merge_report.md"
    report.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"Report: {report}")

    print("\nStats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"\nGlossary size: {original_count} -> {len(main)} entries")

    return 0


if __name__ == "__main__":
    sys.exit(main())
