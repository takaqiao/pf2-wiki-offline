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

### Iter 7 — v0.3.5 build (2026-05-19 23:35, DONE)
- ✅ v0.3.5 NSIS + portable released
- search.html URL `?q=` auto-trigger via inline JS post-buildUI

### Iter 8 — mw-collapsible JS + v0.3.6 (2026-05-20 00:15, DONE)
- ✅ `assets/mw_collapsible.js` — standard MediaWiki collapse/expand behavior
  - Auto-injects `[折叠]/[展开]` toggle into `.mw-collapsible` elements
  - Click flips `mw-collapsed` class + hides .mw-collapsible-content
  - Tested on 8发弹匣 page navbox: works ✓
- ⚠️ **CRITICAL FINDING**: makensis crashed on my dev box with:
  ```
  Internal compiler error #12345: error mmapping datablock to 98176
  ```
  Same error class as user's "corrupted data" → **NSIS upstream bug** with our 2GB bundle
  Cleared %TEMP%, retried — same failure
- → v0.3.6 shipped as **portable-only** (NSIS bundle skipped due to bug)

### Iter 9 — Try MSI bundle (2026-05-20 00:30, DONE)
- Attempted `targets: ["msi"]` to use WiX instead of NSIS
- WiX downloaded + ran `candle`, then **`light.exe` failed** without specific error
- WiX has 2 GB MSI limit — our resources ~2 GB hit that ceiling
- Conclusion: **Both NSIS and MSI struggle at ~2 GB resource bundle volume**
- Going forward: **portable ZIP is the canonical distribution**, NSIS is best-effort

### Iter 11 — Classes hub 25/25 ✓ (2026-05-20, DONE)
- ✅ Found 7 of missing 10 classes under different canonical titles:
  - 诗人 → **吟游诗人** (Bard)
  - 战斗大师 → **神卫** (Champion)
  - 侠盗 → **游荡者** (Rogue)
  - 巫师 → **法师** (Wizard)
  - 魔法师 → **魔战士** (Magus)
  - 神秘学者 → **先知** (Oracle)
  - 夜歌使 → **女巫** (Witch)
  - 动能术士 → **元素使** (Kineticist)
  - 符文师 → **奇术师** (Thaumaturge)
  - 炼魂师 → **发明家** (Inventor)
  - 锻铸者 → **魂铸者** (Animist)
- ✅ Mined wiki's master 职业 page links via parse — extracted full canonical list
- ✅ Scraped 元素使 + 魂铸者 (were in metadata but skipped during parse) via curl_cffi
- ✅ Rebuilt build_v2 + build_class_hubs_v2 → **25/25 真职业 with full class pages**
- ✅ Re-zipped v0.3.7 portable (1.22 GB unchanged) + re-uploaded to release

### Iter 10 — Final status + remaining gaps (2026-05-20, DONE)
- 10 iterations of bug-find + fix loop completed
- Releases shipped this auto-loop: v0.3.3, v0.3.4, v0.3.5, v0.3.6
- All visible UI bugs found via Playwright QA: addressed
- mw-collapsible interactive feature added
- Installer dilemma documented: NSIS/MSI fail >2GB upstream

## Summary: shipped during auto-iteration

| Release | Date | What | Status |
|---|---|---|---|
| v0.3.3 | 2026-05-19 | +106 new wiki pages + portable ZIP option | NSIS + zip |
| v0.3.4 | 2026-05-19 | Data: h1 strip, section TOC, dark mode navbox | NSIS + zip |
| v0.3.5 | 2026-05-19 | search.html URL `?q=` auto-trigger | NSIS + zip |
| v0.3.6 | 2026-05-20 | mw-collapsible JS toggles (8发弹匣 verified) | **portable-only** (NSIS bug exposed) |
| v0.3.7 | 2026-05-20 | Classes 25/25 hub fix + new 元素使/魂铸者 pages | **portable-only** |

## Pending P2/P3 (next iterations)
- pf2icon sprite (action symbols) — wiki_native.css has no `.pf2icon-X` rules; sprite is in `Template:动作/style` rendered inline → need separate fetch
- sortable wikitable JS — wiki tables don't have `.sortable` class; defer  
- 25 真职业: **25/25 ✓** (canonical wiki names mined from master 职业 page)
- Code signing cert ($300/年) to drop SmartScreen warning
- NSIS bundle solution: bigger TEMP dir? makensis flags? Inno Setup?

---

## Resume protocol

If context breaks mid-iteration:
1. Read this file
2. Look at "Active iteration" cursor
3. Continue from "Status" of that iter
4. Update cursor + status on each step
