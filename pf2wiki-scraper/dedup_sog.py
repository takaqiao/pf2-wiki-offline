"""Dedup glossary_sog.json against the main glossary.json.

Per user instruction 2026-04-19:
  把glossary.json有的 sog里也有的 但是主术语表glossary.json优先
  （去除sog同类项或者替换都可以）

  = when both files have an EN key, main glossary.json wins; either drop the sog
  entry or replace it with the main value. We drop it — sog should become the
  pure SoG-specific delta so loaders don't duplicate work.

Matching is case-insensitive. A timestamped backup is written before editing.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

MAIN_GLOSSARY = Path(r"C:\Users\Taka\Desktop\fvtt\glossary.json")
SOG_GLOSSARY = Path(r"C:\Users\Taka\Desktop\fvttpublish\pf2e-compendium-extra\glossary_sog.json")
REPORT = Path(__file__).resolve().parent / "out" / "dedup_sog_report.md"


def main() -> int:
    if not MAIN_GLOSSARY.exists():
        print(f"Missing: {MAIN_GLOSSARY}")
        return 1
    if not SOG_GLOSSARY.exists():
        print(f"Missing: {SOG_GLOSSARY}")
        return 1

    main = json.loads(MAIN_GLOSSARY.read_text(encoding="utf-8"))
    sog = json.loads(SOG_GLOSSARY.read_text(encoding="utf-8"))
    sog_before = len(sog)

    # Build case-insensitive lookup of main keys -> main value (may be str or list)
    main_idx = {k.lower(): v for k, v in main.items()}

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = SOG_GLOSSARY.with_suffix(f".json.bak.{ts}")
    shutil.copy2(SOG_GLOSSARY, backup)
    print(f"Backup: {backup}")

    removed_identical: list[tuple[str, str]] = []  # (en, val)
    removed_differ: list[tuple[str, str, object]] = []  # (en, sog_val, main_val)
    kept: dict[str, str] = {}

    for en, sog_val in sog.items():
        main_val = main_idx.get(en.lower())
        if main_val is None:
            kept[en] = sog_val
            continue
        # key is in both — remove from sog (main wins)
        # classify whether values matched for the report
        main_values: list[str]
        if isinstance(main_val, list):
            main_values = [str(x) for x in main_val]
        else:
            main_values = [str(main_val)]
        if sog_val in main_values:
            removed_identical.append((en, sog_val))
        else:
            removed_differ.append((en, sog_val, main_val))

    SOG_GLOSSARY.write_text(
        json.dumps(kept, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# SoG dedup report",
        "",
        f"Main:  `{MAIN_GLOSSARY}` ({len(main)} entries)",
        f"SoG:   `{SOG_GLOSSARY}` ({sog_before} -> {len(kept)} entries)",
        f"Backup: `{backup.name}`",
        "",
        "## Stats",
        "",
        f"- removed (sog == main): {len(removed_identical)}",
        f"- removed (sog differed; main wins): {len(removed_differ)}",
        f"- kept (sog-only): {len(kept)}",
    ]
    if removed_differ:
        lines += [
            "",
            "## Entries where SoG differed from main (sog dropped, main retained)",
            "",
            "| EN | sog value | main value |",
            "|---|---|---|",
        ]
        for en, sv, mv in removed_differ[:200]:
            lines.append(f"| {en} | {sv!r} | {mv!r} |")
        if len(removed_differ) > 200:
            lines.append(f"| ... | ... ({len(removed_differ) - 200} more) | |")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {REPORT}")
    print()
    print(f"SoG: {sog_before} -> {len(kept)} entries")
    print(f"  removed identical: {len(removed_identical)}")
    print(f"  removed differing: {len(removed_differ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
