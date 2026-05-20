"""Find the real categorization for creatures/archetypes (their obvious single
category is near-empty for ns=0). Two probes:
 1) live 生物 / 变体 member ns+type breakdown + subcategory titles (maybe they're
    parent cats whose members are subcats).
 2) among offline ns=0 pages matching the creature/archetype keywords, tally their
    actual parse.categories -> the dominant real categories to drive the bucket from.
Writes out_v2/_cat_audit/_anchor_investigation.json (UTF-8).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "out_v2" / "parsed"
AUD = ROOT / "out_v2" / "_cat_audit"
LIVE = AUD / "_live"


def key(n):
    return hashlib.sha1(n.encode("utf-8")).hexdigest()[:16]


def load_live(n):
    f = LIVE / f"{key(n)}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def matches(cats, title, keys):
    blob = (" ".join(cats) + " " + title).lower()
    return any(k.lower() in blob for k in keys)


def main() -> int:
    res = {}
    for anc in ["生物", "变体", "信仰", "族裔"]:
        d = load_live(anc)
        if not d:
            res[anc] = "not cached"
            continue
        ms = d.get("members", [])
        res[anc] = {
            "total": len(ms),
            "ns": dict(Counter(m.get("ns") for m in ms)),
            "type": dict(Counter(m.get("type") for m in ms)),
            "subcats": [m.get("title") for m in ms if m.get("type") == "subcat"][:50],
        }

    crea_keys = ["怪物", "creature", "monster"]
    arch_keys = ["变体", "archetype"]
    crea_cat = Counter()
    arch_cat = Counter()
    crea_n = arch_n = 0
    for pf in PARSED.rglob("*.json"):
        if pf.name.startswith("_"):
            continue
        try:
            d = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("ns") != 0:
            continue
        cats = [c.get("category", "") for c in (d.get("parse", {}) or {}).get("categories", []) if isinstance(c, dict)]
        title = d.get("title", "")
        if matches(cats, title, crea_keys):
            crea_n += 1
            for c in cats:
                crea_cat[c] += 1
        if matches(cats, title, arch_keys):
            arch_n += 1
            for c in cats:
                arch_cat[c] += 1
    res["creatures_bucket"] = {"n_pages": crea_n, "top_cats": crea_cat.most_common(25)}
    res["archetypes_bucket"] = {"n_pages": arch_n, "top_cats": arch_cat.most_common(25)}

    (AUD / "_anchor_investigation.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("done -> _anchor_investigation.json")
    print("creatures keyword pages:", crea_n, "| archetypes keyword pages:", arch_n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
