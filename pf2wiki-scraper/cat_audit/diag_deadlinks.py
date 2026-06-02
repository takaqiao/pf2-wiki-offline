"""Diagnose the true nature of content-page dead links (gap is 0, so what are they?)."""
import re, urllib.parse, random, glob, json, hashlib
from pathlib import Path
SCR = Path(__file__).resolve().parents[1]
W = SCR.parent / "_wiki_full_v2"
meta = json.loads((SCR / "out_v2" / "metadata.json").read_text(encoding="utf-8"))
PARSED = SCR / "out_v2" / "parsed"

# title -> page record
by_title = {p["title"]: p for p in meta.get("pages", [])}
rm = meta.get("redirect_map", {})
print("redirect_map type:", type(rm).__name__, "size:", len(rm) if hasattr(rm, "__len__") else "?")
redir_keys = set(rm.keys()) if isinstance(rm, dict) else set()

SAFE = re.compile(r'[*?"<>|]')
def safe(t):
    t = t.replace(":", "_").replace("/", "__").replace("\\", "_")
    return SAFE.sub("", t)
def sha_path(pid):
    h = hashlib.sha1(str(pid).encode()).hexdigest()
    return PARSED / h[:2] / f"{h[2:]}.json"

# reverse safe->title map (bare titles)
safe2title = {}
for p in meta.get("pages", []):
    t = p["title"]
    bare = t.split(":", 1)[1] if ":" in t and t.split(":",1)[0] in {"Category","分类","Data","数据","Project","Help","Template","File"} else t
    safe2title.setdefault(safe(bare), t)

files = glob.glob(str(W / "pages" / "*.html")); random.seed(7); sample = random.sample(files, 300)
RX = re.compile(r'href="(\.\./pages/[^"#?]+?\.html)"')
cats = {"redirect": 0, "not_in_meta": 0, "in_meta_has_parsed": 0, "in_meta_no_parsed": 0}
ex = {"redirect": [], "not_in_meta": [], "in_meta_has_parsed": [], "in_meta_no_parsed": []}
for f in sample:
    for h in set(RX.findall(open(f, encoding="utf-8", errors="ignore").read())):
        rel = urllib.parse.unquote(h[3:])
        if (W / rel).exists():
            continue
        safebare = rel[len("pages/"):-5]
        title = safe2title.get(safebare)
        if title is None:
            cats["not_in_meta"] += 1
            if len(ex["not_in_meta"]) < 12: ex["not_in_meta"].append(safebare)
        elif title in redir_keys:
            cats["redirect"] += 1
            if len(ex["redirect"]) < 12: ex["redirect"].append(title)
        else:
            p = by_title[title]
            if sha_path(p["pageid"]).exists():
                cats["in_meta_has_parsed"] += 1
                if len(ex["in_meta_has_parsed"]) < 12: ex["in_meta_has_parsed"].append(title)
            else:
                cats["in_meta_no_parsed"] += 1
                if len(ex["in_meta_no_parsed"]) < 12: ex["in_meta_no_parsed"].append(title)
print("dead-link categories:", cats)
(SCR / "out_v2" / "_cat_audit" / "_deadlink_diag.json").write_text(
    json.dumps({"cats": cats, "examples": ex}, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote _deadlink_diag.json")
