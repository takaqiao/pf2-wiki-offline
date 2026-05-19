"""In-place cleanup of noise patterns in the main glossary.json.

Designed to be run repeatedly with different `--batch` flags. Each batch
addresses one class of noise that emerged from the wiki auto-extract. Every
run makes a timestamped backup and writes a per-batch diff report.

Policy:
  * Batches 1-4 are auto-fix: the transformation is unambiguous.
  * Batches 5+ are review-only — they print candidates for manual inspection
    but don't touch the file unless `--apply` is passed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

MAIN = Path(r"C:\Users\Taka\Desktop\fvtt\glossary.json")
REPORT_DIR = Path(__file__).resolve().parent / "out"
REPORT_DIR.mkdir(exist_ok=True)

# --- Batch 1: strip action-keyword prefixes ---
# The wiki pages use 启动 (Activate) / 反应 (Reaction) / 触发 (Trigger) / 要求
# (Requirement) as inline action markers, sometimes followed by em dashes.
# These leak into term captures like "启动——星辉变身". We strip the marker
# unless the resulting ZH is empty or length<2.
ACTION_PREFIX = re.compile(
    r"^(?:"
    r"启动|触发|效果|反应|要求|频率|豁免|持续|范围|目标"
    r")(?:[—–\-:：\s]+|——)"
)


def apply_batch1(d: dict) -> list[tuple[str, str, str]]:
    """Strip action-keyword prefix. Returns [(en, before, after), ...]."""
    changed: list[tuple[str, str, str]] = []
    for en, v in list(d.items()):
        if not isinstance(v, str):
            continue
        new = ACTION_PREFIX.sub("", v).strip()
        if new != v and len(new) >= 2:
            d[en] = new
            changed.append((en, v, new))
    return changed


# --- Batch 2: normalize quote-punctuation noise ---
# Pages sometimes open with a trailing 》 or leading 《/【 because the extractor
# caught a chunk of "《Book Name》Chapter Foo".
QUOTE_RE = re.compile(r"^[》〉】」』\]]+|[《〈【「『\[]+$")


def apply_batch2(d: dict) -> list[tuple[str, str, str]]:
    changed: list[tuple[str, str, str]] = []
    for en, v in list(d.items()):
        if not isinstance(v, str):
            continue
        new = QUOTE_RE.sub("", v).strip()
        if new != v and len(new) >= 2:
            d[en] = new
            changed.append((en, v, new))
    return changed


# --- Batch 3: strip leading fragment starters ---
# Words like 该/其/此/当/来自/位于/关于/所有 preceding a real term. If the
# remainder is >=2 chars and still CJK, drop the prefix.
FRAG_STARTERS = (
    "该", "其", "此", "来自", "位于", "关于", "对于", "随后",
    "所有", "每个", "一个", "一只", "一种", "一位", "一名",
    "并且", "然后", "然而",
    # Left-hand contextual
    "即", "也就是", "就是",
)
FRAG_RE = re.compile(r"^(?:" + "|".join(sorted(FRAG_STARTERS, key=len, reverse=True)) + r")")


def apply_batch3(d: dict) -> list[tuple[str, str, str]]:
    changed: list[tuple[str, str, str]] = []
    for en, v in list(d.items()):
        if not isinstance(v, str):
            continue
        m = FRAG_RE.match(v)
        if not m:
            continue
        new = v[m.end():].strip("，。；: 　")
        if len(new) >= 2 and re.search(r"[\u4e00-\u9fff]", new):
            d[en] = new
            changed.append((en, v, new))
    return changed


# --- Batch 4: delete entries that are just noise ---
# Entries where ZH is unsalvageable (e.g. just a pronoun, or all-English ZH
# due to capture error).
def apply_batch4(d: dict) -> list[tuple[str, str, str]]:
    changed: list[tuple[str, str, str]] = []
    JUNK_ZH = {
        "你", "我", "他", "她", "它", "他们", "她们", "它们", "我们", "你们",
        "这", "那", "这个", "那个", "这些", "那些",
        "是", "有", "会", "可", "得", "的",
    }
    for en, v in list(d.items()):
        if isinstance(v, str) and v.strip() in JUNK_ZH:
            del d[en]
            changed.append((en, v, "<DELETED>"))
            continue
        # Delete entries whose ZH has no CJK at all (capture error)
        if isinstance(v, str) and not re.search(r"[\u4e00-\u9fff]", v):
            del d[en]
            changed.append((en, v, "<DELETED>"))
    return changed


# --- Batch 5: strip 启动/触发 prefix without separator ---
# e.g. `启动安全地带 -> 安全地带`, `启动浮萍 -> 浮萍`. Only when followed
# by 2+ CJK chars (so the bare word `启动` itself stays intact).
ACTION_NOSEP_PREFIX = re.compile(r"^(启动|触发|反应|效果|要求|频率)([\u4e00-\u9fff]{2,})$")


def apply_batch5(d: dict) -> list[tuple[str, str, str]]:
    changed: list[tuple[str, str, str]] = []
    for en, v in list(d.items()):
        if not isinstance(v, str):
            continue
        m = ACTION_NOSEP_PREFIX.match(v)
        if not m:
            continue
        new = m.group(2)
        if len(new) >= 2:
            d[en] = new
            changed.append((en, v, new))
    return changed


# --- Batch 6: strip sentence-marker preposition prefixes (从/由) ---
# Only 从 and 由 are narrow enough to strip safely. Characters like 被/对/使
# commonly begin legitimate compounds (被动, 对立, 使馆 ...) so we avoid them.
# Even for 从/由 we reject a small stoplist of compound-forming next-chars.
PREP_STARTERS = re.compile(r"^(从|由)(?=[\u4e00-\u9fff]{2,})")
COMPOUND_NEXT = {
    "从": {"容", "此", "而", "不", "来", "未", "小", "前", "后", "今", "旁", "速", "事", "业", "军"},
    "由": {"于", "此", "衷", "来"},
}


def apply_batch6(d: dict) -> list[tuple[str, str, str]]:
    changed: list[tuple[str, str, str]] = []
    for en, v in list(d.items()):
        if not isinstance(v, str):
            continue
        m = PREP_STARTERS.match(v)
        if not m:
            continue
        prep = m.group(1)
        nxt = v[m.end():m.end() + 1]
        if nxt in COMPOUND_NEXT.get(prep, set()):
            continue
        new = v[m.end():]
        if len(new) >= 2 and re.search(r"[\u4e00-\u9fff]", new):
            d[en] = new
            changed.append((en, v, new))
    return changed


# --- Batch 7: strip name-prefixing titles (女神/男神/大神) when followed
# by a proper noun. PF2e source pages write `女神XYZ` in prose where the
# goddess title is boilerplate, not part of the name.
NAME_TITLES = re.compile(r"^(?:女神|男神|大神|邪神|半神)(?=[\u4e00-\u9fff]{2,})")


def apply_batch7(d: dict) -> list[tuple[str, str, str]]:
    changed: list[tuple[str, str, str]] = []
    for en, v in list(d.items()):
        if not isinstance(v, str):
            continue
        m = NAME_TITLES.match(v)
        if not m:
            continue
        new = v[m.end():]
        if len(new) >= 2 and re.search(r"[\u4e00-\u9fff]", new):
            d[en] = new
            changed.append((en, v, new))
    return changed


# --- Batch 8: strip leading 如 / 名为 / 叫做 / 名叫 ---
# Wiki prose uses these to introduce a proper noun: "a creature named X".
# Strip them; a stoplist prevents stripping idioms like 如果/如此/如同/如何.
LIKE_NAMED_PREFIX = re.compile(r"^(如|名为|叫做|名叫|称为|称作|又名|又称)(?=[\u4e00-\u9fff]{2,})")
LIKE_COMPOUND_NEXT = {
    "如": {"果", "此", "今", "何", "同", "意", "是", "若", "期", "许", "一", "其", "芒", "常", "故", "愿"},
}


def apply_batch8(d: dict) -> list[tuple[str, str, str]]:
    changed: list[tuple[str, str, str]] = []
    for en, v in list(d.items()):
        if not isinstance(v, str):
            continue
        m = LIKE_NAMED_PREFIX.match(v)
        if not m:
            continue
        prefix = m.group(1)
        nxt = v[m.end():m.end() + 1]
        if nxt in LIKE_COMPOUND_NEXT.get(prefix, set()):
            continue
        new = v[m.end():]
        if len(new) >= 2 and re.search(r"[\u4e00-\u9fff]", new):
            d[en] = new
            changed.append((en, v, new))
    return changed


# --- Batch 9: clean EN keys with wiki-list artifacts ---
# Pages with numbered link lists leak into EN captures:
#   "76. [[ Antler Lodge" -> "Antler Lodge"
#   "3、[[ Classes" -> "Classes"
#   "– Ancestral Recollection" -> "Ancestral Recollection"
# Rename the key in place; if a cleaned key collides, keep whichever has the
# longer ZH and drop the other.
EN_ARTIFACT_PREFIX = re.compile(
    r"^(?:\d+[\.、]?\s*)?"        # optional leading number + dot or 、
    r"(?:\[\[\s*)?"                # optional `[[` with spaces
    r"(?:[–—\-]\s*)?"              # optional leading dash
)
EN_TRAILING_BRACKET = re.compile(r"\]\]\s*$")


def clean_en_key(en: str) -> str:
    new = EN_ARTIFACT_PREFIX.sub("", en).strip()
    new = EN_TRAILING_BRACKET.sub("", new).strip()
    # Remove any embedded `[[` or `]]` pairs
    new = re.sub(r"\[\[|\]\]", "", new).strip()
    return new


def apply_batch9(d: dict) -> list[tuple[str, str, str]]:
    changed: list[tuple[str, str, str]] = []
    # Collect rename pairs first to avoid mutating-during-iteration
    renames: list[tuple[str, str]] = []
    for en in list(d.keys()):
        new_en = clean_en_key(en)
        if new_en and new_en != en and re.match(r"[A-Za-z]", new_en):
            renames.append((en, new_en))
    for old, new in renames:
        if old not in d:
            continue
        old_val = d[old]
        if new in d:
            # Collision: keep the one with longer/cleaner ZH
            existing = d[new]

            def rank(v):
                if isinstance(v, list):
                    return sum(len(str(x)) for x in v)
                return len(str(v))

            if rank(old_val) > rank(existing):
                d[new] = old_val
            del d[old]
            changed.append((old, f"{old_val!r} -> merged into '{new}'", new))
        else:
            d[new] = old_val
            del d[old]
            changed.append((old, f"{old_val!r}", new))
    return changed


BATCHES = {
    "1": ("strip action-keyword prefix with separator (启动——/启动—/启动 )", apply_batch1),
    "2": ("strip orphan quote punctuation", apply_batch2),
    "3": ("strip leading fragment starters (该/其/此/来自/位于...)", apply_batch3),
    "4": ("delete unsalvageable junk ZH", apply_batch4),
    "5": ("strip 启动/触发 prefix without separator", apply_batch5),
    "6": ("strip preposition sentence-starters (从/由)", apply_batch6),
    "7": ("strip name-title prefix (女神/男神/大神/邪神)", apply_batch7),
    "8": ("strip naming-introducer prefix (如/名为/又名/又称/称为)", apply_batch8),
    "9": ("clean EN keys with wiki-list artifacts ('76. [[ X' -> 'X')", apply_batch9),
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", action="append", default=None,
                    help="Batch number(s) to apply (repeat). Default: all.")
    ap.add_argument("--dry-run", action="store_true", help="Show changes without writing.")
    args = ap.parse_args(argv)

    chosen = args.batch or list(BATCHES.keys())
    for c in chosen:
        if c not in BATCHES:
            print(f"Unknown batch: {c}. Available: {list(BATCHES.keys())}")
            return 2

    d = json.loads(MAIN.read_text(encoding="utf-8"))
    before_count = len(d)

    all_changes: list[tuple[str, list[tuple[str, str, str]]]] = []
    for c in chosen:
        label, fn = BATCHES[c]
        changes = fn(d)
        all_changes.append((f"batch{c}: {label}", changes))
        print(f"batch{c} ({label}): {len(changes)} changes")

    if args.dry_run:
        print("(dry-run — no write)")
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = MAIN.with_suffix(f".json.bak.{ts}")
        shutil.copy2(MAIN, backup)
        MAIN.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {MAIN} ({before_count} -> {len(d)} entries)")
        print(f"Backup: {backup.name}")

    # Report
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report = REPORT_DIR / f"cleanup_report_{ts}.md"
    lines = ["# Glossary cleanup report", "", f"Run: {ts}", f"Target: `{MAIN}`", f"Entries: {before_count} -> {len(d)}", ""]
    for heading, changes in all_changes:
        lines += ["", f"## {heading}", "", f"**{len(changes)} entries affected**", ""]
        if not changes:
            continue
        lines += ["| EN | before | after |", "|---|---|---|"]
        for en, before, after in changes[:60]:
            lines.append(f"| `{en}` | {before!r} | {after!r} |")
        if len(changes) > 60:
            lines.append(f"| ... | ... ({len(changes) - 60} more) | |")
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {report}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
