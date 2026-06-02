"""Audit every nav/home/sidebar internal link target: is it a real wiki article,
a (correct) redirect stub, one of OUR synthetic hubs, a browse list, or missing?
Flags the 出版物 class of problem: nav pointing to a worse synthetic stub when a
real, complete wiki page exists."""
import re, urllib.parse, json
from pathlib import Path
W = Path(__file__).resolve().parents[2] / "_wiki_full_v2"
SCR = Path(__file__).resolve().parents[1]
meta = json.loads((SCR / "out_v2" / "metadata.json").read_text(encoding="utf-8"))
real_titles = {p["title"]: p for p in meta.get("pages", []) if not p.get("is_redirect") and p.get("ns") == 0}

SRCS = ["index.html", "_snippets/topnav_sub.html", "_snippets/sidebar_sub.html"]
HREF_RX = re.compile(r'href="((?:\.\./)?(?:pages|data|category|source|classes|browse|index)[^"#?]*?\.html)"')
SYNTH = {"source/index.html", "classes/index.html", "index.html"}

def classify(rel):
    p = W / rel
    if not p.exists():
        return "MISSING"
    if rel in SYNTH or rel.startswith("browse"):
        return "synthetic/list"
    s = p.read_text(encoding="utf-8", errors="ignore")
    if "http-equiv=\"refresh\"" in s and "redirectMsg" not in s and len(s) < 1200:
        m = re.search(r"url=([^\"]+)", s)
        return "redirect-stub -> " + urllib.parse.unquote(m.group(1)) if m else "redirect-stub"
    return "real-article (%dKB)" % (len(s) // 1024)

seen = set(); rows = []
for src in SRCS:
    txt = (W / src).read_text(encoding="utf-8")
    for h in HREF_RX.findall(txt):
        rel = h[3:] if h.startswith("../") else h
        rel = urllib.parse.unquote(rel)
        if rel in seen: continue
        seen.add(rel)
        cls = classify(rel)
        # bare title for synthetic-hub real-page check
        bare = rel.split("/")[-1][:-5]
        flag = ""
        if rel in ("source/index.html",):
            flag = " <-- STUB; real page 出版物索引 exists" if "出版物索引" in real_titles else ""
        if rel == "classes/index.html":
            flag = " <-- hub; real 职业 article exists" if "职业" in real_titles else ""
        rows.append((src.split("/")[-1], rel, cls, flag))

rows.sort()
print(f"{'source':<16}{'target':<40}{'class':<32}flag")
for s, rel, cls, flag in rows:
    print(f"{s:<16}{rel:<40}{cls:<32}{flag}")
(SCR / "out_v2" / "_cat_audit" / "_nav_target_audit.json").write_text(
    json.dumps([{"src": s, "target": rel, "class": c, "flag": f} for s, rel, c, f in rows], ensure_ascii=False, indent=1), encoding="utf-8")
