# PF2 Wiki Offline — Auto-Iteration State

> User directive (2026-05-19): self-iterate finding + fixing bugs continuously
> until told stop. Each iter writes its findings here so next iter can resume
> if context breaks. Goal: 100% fidelity restoration of pf2.huijiwiki.com.

## Current cursor

- **Active iteration**: 8 — mw-collapsible JS + sortable wikitable JS
- **Status**: in-progress
- **Latest release**: v0.3.5 (search URL auto-trigger + iter 5-7 fixes)
- **Releases shipped this auto-loop**: v0.3.3 (portable), v0.3.4 (Data h1 + TOC + dark), v0.3.5 (search URL)
- **Test url for user**: https://github.com/takaqiao/pf2-wiki-offline/releases/download/v0.3.5/pf2-wiki-offline_0.3.5_x64-portable.zip
- **User-reported issue**: v0.3.x NSIS "corrupted data" — workaround = portable ZIP (bypass NSIS)

## Iteration queue (priority order)

| # | Iteration | Status | Target |
|---|---|---|---|
| 1 | Pull fresh wiki snapshot, diff metadata vs old | in-progress | identify new/changed pages |
| 2 | Re-scrape changed pages via curl_cffi | pending | up-to-date corpus |
| 3 | Visual QA full sweep via Playwright (sample 20 page types) | pending | find render bugs |
| 4 | Fix highest-impact bugs found in #3 | pending | quality++ |
| 5 | Section TOC injection for long pages | pending | usability |
| 6 | mw-collapsible JS (foldable boxes) | pending | interactivity |
| 7 | sortable wikitable JS | pending | interactivity |
| 8 | classes hub: find remaining 11 of 25 真职业 | pending | 25/25 |
| 9 | Image regex coverage — check for missed patterns | pending | image completeness |
| 10 | pf2icon sprite — fetch + serve | pending | action icons visible |
| 11 | Build v0.3.3 with all fixes + Release | pending | ship |
| 12 | Next iteration loop | pending | continuous |

## Files modified per iter (running log)

(empty initially; each iter appends here)

## Architecture quick reference

- **Build dir**: `C:\Users\Taka\Desktop\fvtt\_wiki_full_v2\`
- **Scraper**: `C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper\` (uses `.venv` + curl_cffi)
- **Tauri**: `C:\Users\Taka\Desktop\fvtt\src-tauri\`
- **Source repo (for GitHub)**: `C:\Users\Taka\pf2-wiki-offline\`
- **Signing key**: `C:\Users\Taka\.tauri\pf2-wiki.key` (private, no password)
- **GitHub**: takaqiao/pf2-wiki-offline (PUBLIC, auto CI on push)
- **GitHub token**: stored locally in env / shell history — NOT committed (GitHub secret scanning would reject)

## Pipeline commands quick reference

```powershell
# 1. Refresh cookies
cd C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper
.\.venv\Scripts\python.exe cookie_warmup_v2.py

# 2. Re-pull metadata
.\.venv\Scripts\python.exe dump_metadata_v2.py  # ~20s

# 3. Concurrent content scrape (resumable)
.\.venv\Scripts\python.exe dump_parsed_v2_concurrent.py -c 20  # ~8 min

# 4. Images
.\.venv\Scripts\python.exe dump_images_v2_concurrent.py -c 16  # ~50s

# 5. Build
cd ..\_wiki_full_v2
..\pf2wiki-scraper\.venv\Scripts\python.exe build_v2.py --redirects
..\pf2wiki-scraper\.venv\Scripts\python.exe build_browse_v2.py
..\pf2wiki-scraper\.venv\Scripts\python.exe build_class_hubs_v2.py
..\pf2wiki-scraper\.venv\Scripts\python.exe build_browse_letters_v2.py
..\pf2wiki-scraper\.venv\Scripts\python.exe build_search_v2.py

# 6. Tauri (bash, env-var sign)
cd ..\src-tauri
& cargo tauri build  # ~10-15 min total

# 7. Sign + Release
cd target\release\bundle\nsis
& cargo tauri signer sign --private-key-path "$env:USERPROFILE\.tauri\pf2-wiki.key" --password "" "PF2 离线百科_*_x64-setup.exe"
# Then gh release create ...
```

## Iteration history (appended each loop)

### Iter 0 — baseline (before this auto-loop)
- v0.3.0 → v0.3.1 → v0.3.2 released
- Image bug fix, auto-updater UI, race fix, classes 25 strict, placeholder strip
- User reports v0.3.0 corruption, testing v0.3.2

### Iter 1 — fresh metadata pull + LZMA hypothesis rejected (2026-05-19 22:30)
- **User confirms v0.3.2 (zlib) ALSO fails with "corrupted data"** → NOT LZMA bug
- Fresh metadata: **40,736 pages** (was 40,630 → +106 new pages since first scrape)
- 2,231 redirects (was 2,229)
- 106 new = **55 Data:Items.json (新装备) + 50 主页 + 1 分类**
- 龙息枪.html exists at normal path length (~57 chars total install path) — NOT MAX_PATH
- **Theory updated**: Most likely **Defender 启发式针对 v0.3+ EXE pattern**:
  - v0.3.0+ introduced rewritten `<img>` HTML attributes (`data-original-src` + URL patterns)
  - Plus signed binary section (tauri-plugin-updater code signatures)
  - Defender heuristic may flag these specific binary patterns
  - Mid-extract Defender quarantines one file → NSIS reports "corrupted data"
- **Mitigations to ship**:
  - **Portable ZIP** (7z SFX or zip): manual extract, bypass NSIS entirely → bypass Defender hook
  - Long-term: code signing cert ($50-300/年)

### Iter 2 — scrape 106 new pages + portable ZIP + v0.3.3 release (2026-05-19 22:50, DONE)
- ✅ 2.1: scraped 104/106 new pages (2 redirects) at 82 req/sec
- ✅ 2.2: rebuilt build_v2 (incl. 5 redirect stubs for the new pages)
- ✅ 2.3: built portable ZIP (1211 MB) via `make_portable_zip.ps1` — 2030 MB folder zipped with 7z mx=3
- ✅ 2.4: signed NSIS + uploaded both NSIS + portable + sig + latest.json to v0.3.3 Release
- Release URL: https://github.com/takaqiao/pf2-wiki-offline/releases/tag/v0.3.3

### Iter 3 — Visual QA via Playwright (2026-05-19 22:55-23:10, DONE)
QA findings + fixes (all in v0.3.4 source):

| Page tested | Result | Fix landed |
|---|---|---|
| 战士.html (class) | ✓ good, has 31 sections | TOC now injected (3+ items, page > 1500 chars) |
| Data:Conditions-Blinded | h1 = `Data:Conditions-Blinded.json` ❌ ugly | Strip `Data:` + `.json` → h1 = `Conditions-Blinded` ✓ |
| 500蟾蜍 (creature + huiji-tt) | ✓ 3 tooltips rendered, 4 imgs OK | — |
| 8发弹匣 (navbox 94 links) | ✓ light mode OK | Dark mode navbox needed override — done in iter-3 |
| 法术列表 (1 MB long page) | TOC = 0 because parse.sections is empty (pure table page, no headings) | won't fix — not a section TOC candidate |
| dark mode | ✓ navbox now flips to dark | _v2_compat.css body.dark .navbox + 10 more selectors |

Bug fixes in v0.3.4 build:
- build_v2.py: Data: namespace h1 strip prefix/suffix
- build_v2.py: section TOC injection (h2/h3 anchors for pages >1500 chars w/ 3+ headings)
- _v2_compat.css: page-toc-v2 styling (collapsible details, brand brown-red border-left)
- _v2_compat.css: body.dark overrides for quote-block / statblock / navbox / infobox /
  wikitable / toc / thumb / page-categories (12 selectors)

### Iter 4 — v0.3.4 build (2026-05-19 23:15, DONE)
- ✅ v0.3.4 NSIS + portable released
- URL: https://github.com/takaqiao/pf2-wiki-offline/releases/tag/v0.3.4

### Iter 5 — Comprehensive QA: search/index/browse (2026-05-19 23:20, DONE)
- ✅ search.html: 50 results in 4.3 ms for query "战士" — BUT URL `?q=` 不自动触发
  - Fix: inline JS in search.html that reads `?q=` after buildUI, populates input + dispatches input event
- ✅ index.html: renders OK with stats cards + topnav + sidebar
- ✅ classes/index.html: 14/25 真职业 (with placeholders for 11 不在 corpus)

### Iter 6 — Redirect stubs + mobile + image-heavy (2026-05-19 23:25, DONE)
- ✅ Redirect stub: 敏捷.html → 属性.html via meta refresh ✓
- ✅ Mobile responsive 375px: topnav 折叠为 hamburger ☰, 图响应式全宽
- ✅ Image lazy loading: 11 imgs on 帕格凯德 page, all load after scroll
- ✅ Gallery / thumb pages: rendered correctly

### Iter 7 — v0.3.5 build (2026-05-19 23:35, in-progress)
- search.html URL auto-trigger fix
- bump 0.3.4 → 0.3.5
- cargo tauri build kicked off

---

## Resume protocol

If context breaks mid-iteration:
1. Read this file
2. Look at "Active iteration" cursor
3. Continue from "Status" of that iter
4. Update cursor + status on each step
