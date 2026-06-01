"""Classify dead pages/ links: in metadata (redirect?) vs genuinely absent."""
import re, urllib.parse, random, glob, json
from pathlib import Path
W = Path(__file__).resolve().parents[2] / "_wiki_full_v2"
files = glob.glob(str(W / "pages" / "*.html")); random.seed(7)
sample = random.sample(files, 200)
RX = re.compile(r'href="(\.\./pages/[^"#?]+?\.html)"')
dead = set()
for f in sample:
    for h in set(RX.findall(open(f, encoding="utf-8", errors="ignore").read())):
        rel = urllib.parse.unquote(h[3:])
        if not (W / rel).exists():
            dead.add(rel[len("pages/"):-5])
dead = list(dead)
meta = json.load(open(Path(__file__).resolve().parents[1] / "out_v2" / "metadata.json", encoding="utf-8"))
titles = {p["title"] for p in meta.get("pages", [])}
rm = meta.get("redirect_map", {})
redirs = set(rm.keys()) if isinstance(rm, dict) else set()
SAFE = re.compile(r'[*?"<>|]')
def safe(t):
    t = t.replace(":", "_").replace("/", "__").replace("\\", "_")
    return SAFE.sub("", t)
safe_titles = {safe(t): t for t in titles}
in_meta = [d for d in dead if d in safe_titles]
is_redir = [d for d in in_meta if safe_titles[d] in redirs]
not_in_meta = [d for d in dead if d not in safe_titles]
print("sampled dead targets:", len(dead))
print("  in metadata.pages:", len(in_meta), "(redirects:", len(is_redir), ")")
print("  NOT in metadata at all:", len(not_in_meta))
out = {"dead_n": len(dead), "in_meta": len(in_meta), "is_redirect": len(is_redir),
       "not_in_meta_n": len(not_in_meta),
       "in_meta_nonredirect_samples": [d for d in in_meta if safe_titles[d] not in redirs][:20],
       "not_in_meta_samples": not_in_meta[:20]}
json.dump(out, open(W.parent / "pf2wiki-scraper" / "out_v2" / "_cat_audit" / "_deadcheck.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote _deadcheck.json")
