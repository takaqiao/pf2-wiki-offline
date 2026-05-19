# Phase A · Scout Report (2026-05-19)

## TL;DR

- **Wiki**: 开拓者2版中文维基 (pf2.huijiwiki.com)
- **MediaWiki**: 1.38.4 / PHP 7.4.3
- **CF bypass**: Cached `.browser-profile/` still valid — clears in **4 s** with no manual challenge.
- **API rate**: 10-sample avg **153 ms** per `action=parse`; sustainable **~2 req/sec**.
- **Scope**:
  - 36,964 non-redirect articles to fetch (Phase B)
  - 3,666 redirect entries (recorded in metadata, no separate fetch needed)
  - 7,774 images (Phase C)
- **ETA total**: **~7 hr** wall-clock (Phase B 5 hr + Phase C 1 hr + Phase F 1 hr + Phase G 10 min + Phase H 30 min)

## Live API probe results (2026-05-19)

| Metric | Value |
|---|---|
| siteinfo round-trip | 178 ms |
| Single parse (战士, 55 KB HTML) | 223 ms |
| 10-sample avg parse | 153 ms |
| **Sustainable rate** | **~2 req/sec** |
| CF clearance cold start | 4.0 s |

## Page counts by namespace (from `apfilterredir=nonredirects` + `=redirects` two-pass)

| ns | name | non-redirect | redirect | total |
|---|---|---:|---:|---:|
| 0 | (Main) | 24,599 | 3,663 | 28,262 |
| 4 | 开拓者2版中文维基: (Project) | 13 | 0 | 13 |
| 14 | Category | 353 | 0 | 353 |
| 102 | (PF2 custom) | 194 | 3 | 197 |
| 3500 | Data: | 11,805 | 0 | 11,805 |
| **total** | | **36,964** | **3,666** | **40,630** |

Note: siteinfo reports articles=21,174 — that's "pages with at least one inbound link in ns=0" by MediaWiki's narrow definition. We're using the broader 24,599 non-redirect ns=0 + 11,805 Data: + 353 Category + ... = 36,964 actual page count.

## Image scope

- Wiki total images per siteinfo: **7,774**
- Phase C strategy: scan all parsed JSON for `images[]` field → batch imageinfo (50 titles/req) → download originalurl + 3 thumb sizes
- Disk: at avg 200 KB original + 3×50 KB thumbs = ~350 KB / image × 7774 = **~2.7 GB raw** (likely 1.5-2 GB after dedup)

## Wall-clock estimates (refined from smoke-test rate)

| Phase | Work | Time |
|---|---|---|
| A · metadata | already DONE | 19.9 s (vs 1-hr estimate) |
| B · parsed scrape | 36,964 pages × 0.5 s (incl. throttle) | **~5.1 hr** |
| C · image scrape | 7,774 imageinfo batched + downloads | **~1 hr** |
| F · static build | local CPU; bs4 DOM rewrite + helper inject | **~1 hr** |
| G · search index | jieba CJK + EN | ~10 min |
| H · Tauri build | cargo build + NSIS bundle | ~30 min |
| **TOTAL** | | **~7-8 hr** |

## Differences from v1

| Item | v1 | v2 |
|---|---|---|
| Render | wikitext + local 600 template handlers | server-side `action=parse` |
| Redirect coverage | `apfilterredir=nonredirects` (lost ~120) | both passes, full coverage |
| Image fetch | none (666 placeholders) | imageinfo + originalurl + thumbs |
| SMW queries | stripped | included (server-rendered in parse output) |
| Output | 36,358 HTML / 1071.9 MB | est. ~37k HTML + ~2 GB images |

## Phase B kickoff command

```powershell
cd C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper
.\.venv\Scripts\python.exe dump_parsed_v2.py
# resumable; flushes state every 50 pages
# Ctrl-C safe (re-run continues where it stopped)
```

## Phase B mid-flight QA (planned)

After 1k pages parsed, sample 10 random pages and visually compare against `https://pf2.huijiwiki.com/wiki/<title>` to ensure render fidelity.

## Outstanding open questions (for after Phase B)

1. Should `_wiki_full_v2/` include browse pages (alphabetic / by category)? Probably yes, reusing v1's `build_index.py` logic.
2. How to handle `Special:` and other ns we skipped? Probably leave 404s for those (rare).
3. Category page generation — v2 will inherit `<a href="/wiki/Category:X">` from parse output; need a builder for `category/<safe>.html` listing pages.
