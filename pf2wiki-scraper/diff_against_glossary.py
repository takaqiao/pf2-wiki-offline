"""Compare wiki-extracted glossary against the user's existing PF2e glossary.

Outputs:
  out/new_terms.json     — EN terms in wiki but NOT in user's glossary (case-insensitive)
  out/conflicts.json     — EN present in both but ZH differs
  out/diff_report.md     — summary + samples for quick scan

Usage:
    python diff_against_glossary.py [path/to/user_glossary.json] [wiki_source]

    wiki_source: one of  full | confident | short  (default: confident)

Defaults to  C:\\Users\\Taka\\Desktop\\fvttpublish\\pf2e-compendium-extra\\glossary_sog.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"

DEFAULT_USER_GLOSSARY = Path(
    r"C:\Users\Taka\Desktop\fvttpublish\pf2e-compendium-extra\glossary_sog.json"
)


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


WIKI_SOURCES = {
    "full": "glossary_wiki.json",
    "confident": "glossary_wiki_confident.json",
    "short": "glossary_wiki_short_zh.json",
}


def main(argv: list[str]) -> int:
    user_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_USER_GLOSSARY
    source_tag = argv[2] if len(argv) > 2 else "confident"
    if source_tag not in WIKI_SOURCES:
        print(f"Unknown wiki source {source_tag!r}. Choose from: {list(WIKI_SOURCES)}")
        return 1
    wiki_path = OUT_DIR / WIKI_SOURCES[source_tag]
    print(f"Using wiki source: {source_tag} ({wiki_path.name})")

    if not user_path.exists():
        print(f"User glossary not found: {user_path}")
        return 1
    if not wiki_path.exists():
        print(f"Wiki glossary not found: {wiki_path} — run extract_terms.py first")
        return 1

    user = load_json(user_path)
    wiki = load_json(wiki_path)

    print(f"User glossary: {len(user)} entries")
    print(f"Wiki glossary: {len(wiki)} entries")

    # Build case-insensitive lookup for user glossary
    user_ci: dict[str, tuple[str, str]] = {}  # lower_en -> (original_en, zh)
    for k, v in user.items():
        user_ci[k.lower().strip()] = (k, v)

    new_terms: dict[str, dict] = {}
    conflicts: list[dict] = []

    for en, meta in wiki.items():
        key = en.lower().strip()
        wiki_zh = meta["zh"]
        if key in user_ci:
            orig_en, user_zh = user_ci[key]
            if wiki_zh != user_zh:
                conflicts.append({
                    "en_wiki": en,
                    "en_user": orig_en,
                    "zh_user": user_zh,
                    "zh_wiki": wiki_zh,
                    "count": meta["count"],
                    "sources": meta["sources"],
                    "examples": meta["examples"],
                })
        else:
            new_terms[en] = meta

    # Sort new_terms by count desc, then by EN
    new_sorted = dict(sorted(new_terms.items(), key=lambda kv: (-kv[1]["count"], kv[0].lower())))
    # Sort conflicts by count desc
    conflicts.sort(key=lambda c: -c["count"])

    suffix = f"_{source_tag}"
    new_file = OUT_DIR / f"new_terms{suffix}.json"
    conflicts_file = OUT_DIR / f"conflicts{suffix}.json"
    report_file = OUT_DIR / f"diff_report{suffix}.md"
    new_file.write_text(json.dumps(new_sorted, ensure_ascii=False, indent=2), encoding="utf-8")
    conflicts_file.write_text(json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown report
    lines = [
        "# Glossary diff report",
        "",
        f"- User glossary (`{user_path.name}`): **{len(user)}** entries",
        f"- Wiki extract: **{len(wiki)}** entries",
        f"- **New terms** (in wiki, not in user): **{len(new_sorted)}**",
        f"- **Conflicts** (same EN, different ZH): **{len(conflicts)}**",
        "",
        "## Top 40 new terms by frequency",
        "",
        "| EN | ZH | count | patterns |",
        "|---|---|---|---|",
    ]
    for en, meta in list(new_sorted.items())[:40]:
        lines.append(f"| {en} | {meta['zh']} | {meta['count']} | {','.join(meta['sources'])} |")

    lines += ["", "## Top 40 conflicts by frequency", "", "| EN | user ZH | wiki ZH | count |", "|---|---|---|---|"]
    for c in conflicts[:40]:
        lines.append(f"| {c['en_user']} | {c['zh_user']} | {c['zh_wiki']} | {c['count']} |")

    report_file.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nWrote:")
    print(f"  {new_file.relative_to(ROOT)}  ({len(new_sorted)} entries)")
    print(f"  {conflicts_file.relative_to(ROOT)}  ({len(conflicts)} entries)")
    print(f"  {report_file.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
