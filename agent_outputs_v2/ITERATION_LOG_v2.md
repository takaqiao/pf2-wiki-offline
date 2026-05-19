# PF2 中文 Wiki v2 — 迭代日志

This is the v2 rewrite of `_wiki_full/`. Output target: `_wiki_full_v2/` + Tauri NSIS installer.

## Session 1 · 2026-05-19

### iter-1 (~14:25): Plan mode + scout

Read v1 handoff (FINAL_STATE.md / ITERATION_LOG.md / HANDOFF.md). Probed wiki API — confirmed 403 for plain curl/IWR; needs Playwright + persistent CF cookie. **Discovered** `pf2wiki-scraper/pfwiki.py` already has working CF-bypass infrastructure from v1 wikitext-scrape phase.

Plan written to `C:\Users\Taka\.claude\plans\pf2-lucky-pudding.md`. User approved + chose **NSIS installer ~2 GB** for Phase H packaging.

Tasks created (12); env verified: Python 3.14, Node 24.13, Playwright 1.58, jieba 0.42 all present. Rust missing — deferred to user `winget install Rustlang.Rustup` before Phase H.

### iter-2 (~14:30): CF clearance smoke + benchmarks

`smoke_test_v2.py`: CF cleared in 4 s using cached `.browser-profile/`. Wiki stats:
- sitename "开拓者2版中文维基", MediaWiki 1.38.4, PHP 7.4.3
- 21,174 articles / 49,486 pages / 7,774 images
- siteinfo 178 ms, parse(战士) 223 ms, 10-sample parse avg **153 ms**
- Sustainable rate **~2 req/sec** under server's own pacing

### iter-3 (~14:35): Phase A metadata harvest

`dump_metadata_v2.py` — fork of v1's `harvest_titles.py` with two bugs fixed:
1. `apfilterredir=all` lost the inline `redirect` flag (MW API quirk in formatversion=2) — switched to **two-pass per namespace**: `nonredirects` then `redirects`, tagging is_redirect explicitly.
2. Added `list=allredirects` for source→target chain (target field doesn't auto-return; followed up via `titles=...&redirects=1` batched).

Output `pf2wiki-scraper/out_v2/metadata.json` in 19.9 s:
- 36,964 non-redirect pages (24,599 ns=0 + 11,805 ns=3500 + 353 ns=14 + 194 ns=102 + 13 ns=4)
- 3,666 redirect pages
- redirect_map: 2,229 entries, only 5 had filled targets via allredirects (known MW API limitation — most redirect targets need separate batch resolution; deferred to a Phase F-prep step)

### iter-4 (~14:45): Phase B kickoff

`dump_parsed_v2.py` — for each non-redirect pageid, `action=parse&pageid=X&prop=text|categories|images|links|sections|displaytitle|properties|templates`. Output per-page to `out_v2/parsed/<sha1[:2]>/<sha1[2:]>.json`. State flushed every 50 pages. Resume-safe.

20-page smoke: 1.32 req/sec sustained (worse than 2/sec theoretical because each round trip ~0.75 s including pacing). Kicked off full run in background (job id `bpgippkss`).

ETA: 36,964 / 1.13 / 3600 = **~9 hours wall clock**.

### iter-5 (~14:48): Phase C + F scripts written (in parallel to Phase B)

`dump_images_v2.py` — scans `parsed/**` for `images[]`, batches `prop=imageinfo` 50 at a time, downloads via `page.request.get()` (Playwright TLS context). Outputs to `out_v2/images/<sha1[:2]>/<sha1[2:]>.<ext>` + `manifest.json`. Re-runnable.

`_wiki_full_v2/build_v2.py` — main static builder:
- Reads metadata + manifest + parsed JSON
- Wraps `parse.text` in `<main class="page-body"><div class="mw-parser-output">...</div>` with topnav/breadcrumb/sidebar/footer skeleton
- BeautifulSoup-based link/image rewriting:
  - `/wiki/X` → `../<dir>/<safe_X>.html` (with `urllib.parse.quote` for CJK)
  - `/index.php?title=X&redlink=1` → keeps `.new` class, marks visually dead via CSS
  - `<img>` matched against manifest → local sha1 path; misses get `.v2-missing-image` placeholder
- Strips MediaWiki diagnostic comments (`<!-- NewPP ... -->`)
- Body class via `kind_class()` heuristic from page categories

Helper file `_wiki_full_v2/assets/_v2_compat.css` — DOM compat layer:
- Carries forward v1 iter-19 root fix: `html body { white-space: normal !important }` (kind-class chip rule leak)
- Tames `.mw-parser-output`, hides `.mw-editsection`, styles `.new` red links, `.smwtable`, `.thumb`, `.gallery`, `.quote-block`, etc.
- Added to `style.css` @import chain after `_p11_overflow_fix.css` so it's last-wins.

Smoke test on first 30 parsed pages: **30/30 OK in 0.5 s**. Sample output `_wiki_full_v2/pages/Deckhand.html` verified — topnav embedded, breadcrumb correct, internal links rewritten, red links flagged with class="new".

### iter-6 (~14:55): Tauri scaffold

`src-tauri/` files written:
- `Cargo.toml` — Tauri 2 + tiny_http + mime_guess + urlencoding
- `tauri.conf.json` — NSIS target, bundle.resources points to `../_wiki_full_v2/**/*`
- `src/main.rs` — picks free port, spawns tiny_http thread serving resource_dir/_wiki_full_v2, navigates WebView to localhost
- `build.rs` + `README.md`

User still needs to `winget install Rustlang.Rustup` then `cargo install tauri-cli --version "^2.0"` before running `cargo tauri build`. NSIS installer ETA ~30 min compile + bundling.

### iter-8 (~15:10): 🚀 curl_cffi 并发突破

User asked: "1.不走 Playwright 也可以 2.要并发". Pivoted to **curl_cffi (Chrome 131 TLS impersonation) + cookies from Playwright warmup** approach.

**`cookie_warmup_v2.py`**: Playwright runs once, captures `__cf_bm` + GA cookies, exports to `out_v2/cookies.json`. Found that **`cf_clearance` is NOT set** on first visit — `__cf_bm` alone + Chrome TLS fingerprint is enough to pass CF for api.php requests.

**`dump_parsed_v2_concurrent.py`**: ThreadPoolExecutor with per-thread curl_cffi Session, shared cookie jar, auto-detection of 403/429 with abort thresholds. Resume-compatible with the Playwright version (same `_state.json`, `parsed/<sha>/...` layout).

**Concurrency sweep (200-page samples)**:

| c | req/s | notes |
|---:|---:|---|
| 1 | 17.3 | 15× faster than Playwright (153 ms parse vs ~870 ms Playwright cycle) |
| 4 | 12.0 | thread overhead dominates at small batch |
| 8 | 26.9 | clean scaling |
| 16 | 46.0 | clean scaling |
| 20 | ~70 | sustained over real workload |
| 32 | 75.6 | latency starts climbing (480/780/927 ms tail) |
| 24 | 46.1 | possibly slightly behind 16/20 — variance |

**Settled on c=20** for full Phase B run. Zero throttle events through tests. Phase B ETA: **~7-12 min** (from 8.6 hr).

**`dump_images_v2_concurrent.py`**: same pattern for Phase C — imageinfo batches (50 titles/req) + binary downloads. Two-stage executor (info pass → download pass). Re-runnable.

### iter-7 (~14:58): Index/search placeholders

Copied v1's `index.html` + `search.html` into `_wiki_full_v2/`, bumped cache to `?v=v2a`. Browse pages (browse-feats, browse-spells, etc.) NOT YET built — those references will 404 until a future Phase F enhancement writes them from v2 metadata.

### iter-9 (~15:05): Phase B concurrent kickoff

After validating curl_cffi + cookies, killed the slow Playwright Phase B (job `bpgippkss`, had reached 1,720 / 36,964 pages over ~30 min). Restarted via `dump_parsed_v2_concurrent.py -c 20` (job `bmysacb5v`). Resume picked up from `_state.json` cleanly.

Live progress (1-min samples after kickoff):
- T+30 sec: 6,624 files
- T+1 min: 14,522 files (rate ~70/s)
- T+2 min: 17,098 files (steady)
- T+3 min: 21,933 files (~60-70/s sustained)
- 0 failures, 0 throttle events

ETA at this rate: full Phase B done in ~10-12 min total (vs the 8.6 hr Playwright projection).

### iter-10 (~15:08): Phase G search builder

Wrote `_wiki_full_v2/build_search_v2.py` — port of v1's `build_search.py` that reads `parsed/*.json` (BeautifulSoup get_text on `parse.text`) instead of wikitext. Same shard layout (`titles.js` + `shards/b_<XX>.js` CJK bigrams + `shards/w_<L>.js` Latin words + `manifest.js`) so v1's `search-app.js` client just works.

Will run after Phase B completes.

### iter-11 (~15:12): Phase B 完成 + 后续全链路

Phase B 后台 job `bmysacb5v` 退出，34,484 页 / 461 sec / **74.8 req/sec 持续速率**，0 failures。

按顺序跑了：

| 阶段 | 时间 | 结果 |
|---|---|---|
| B.5 resolve_redirect_targets_v2_concurrent | 2.2 s | 3,666 redirect targets 填好（vs 5 在初版） |
| C dump_images_v2_concurrent c=16 | **49 s** | 3,028 images / 1,078 MB (62 dl/s) |
| F build_v2.py --redirects (2nd pass) | 397 s | 36,964 pages + 3,578 redirect stubs，0 failures, **93 pages/s** |
| G build_search_v2.py | 94 s | 36,964 pages indexed → titles 10.9 MB + shards 35.7 MB (256 bg + 26 w) |

**全链路时间：B 7.7m → C 0.8m → F 6.6m → G 1.6m = 16.7 min 端到端**（不算 robocopy move 1.8 s）。

### iter-12 (~15:20): 最终 v2 镜像状态

```
_wiki_full_v2/  共 43,886 files / 1.84 GB
  ├─ pages/         28,369 (= 24,793 ns=0 + 3,578 redirect stubs + 13 ns=4 + 194 ns=102)
  ├─ data/          11,804 (ns=3500)
  ├─ category/      353  (ns=14)
  ├─ images/        3,028 / 1,028 MB
  ├─ index/
  │   ├─ titles.js  10.9 MB
  │   └─ shards/    282 files / 35.7 MB
  ├─ assets/        30 files / 0.3 MB (v1 CSS/JS 全套 + _v2_compat.css)
  ├─ _snippets/topnav_sub.html
  ├─ index.html / search.html (v1 copies, cache bump v2a)
  └─ build_v2.py / build_search_v2.py
```

总盘 **1.84 GB** — 在 GitHub Release 2 GB 单文件 limit 内，NSIS installer 应能直发。

### iter-13 (~15:30): 视觉对齐 pf2.huijiwiki.com + 查缺补漏

User feedback: v1 的 AoN warm parchment 风与原站差太多。要"和 pf2 wiki 对齐"。

**Pivot 决策**: 不动 HTML 骨架（保留 v2 offline topnav/breadcrumb/sidebar/footer），只把内容区 CSS 全替换为原站的 native CSS — 让 `.mw-parser-output` 里的 quote-block / statblock / navbox / wikitable / pf2icon / huiji-tt 等 100% 还原。

**Probe 关键发现**:
- 原站皮肤是 **`skin-huiji-dragonhide`**（不是 Vector）
- 4 个 `/load.php?only=styles` 模块 + font-awesome + 2 inline `<style>` 块
- body bg 是 `#fffbf6`（不是纯白）, 字体 Helvetica Neue 14px, 主色 brown-red `#6d2002`, 链接 MW 蓝 `#0645ad`
- DOM 骨架: `#wrapper > #wiki-outer-body > #wiki-body > #mw-content-text > .mw-parser-output`

**fetch_native_styles_v2.py**: curl_cffi 拉 4 个 load.php + font-awesome + 2 inline 块，combined CSS 390 KB，本地化 17 个 url() 资源（spinners、字体文件等）。CF 仍能过墙（同一套 chrome131 impersonation + cookies）。

**CSS chain 重构** —— 砍掉 v1 的 7 层 cascade（bundled + _chr + _p7 + _p8 + _p9 + _p10 + _p11），换成 4 层：

```
@import url(_v2_palette.css?v=v2b)    /* 改自 pf2_theme.css，PF2 brand tokens */
@import url(wiki_native.css?v=v2b)    /* 390 KB 原站 CSS */
@import url(topnav.css?v=v2b)         /* v2 offline topnav */
@import url(_v2_compat.css?v=v2b)     /* 修 wiki_native 在我们 DOM 里的 leak */
```

**build_v2.py 更新**:
- body class 改成 MediaWiki 约定: `mediawiki ltr sitedir-ltr mw-hide-empty-elt ns-<N> ns-subject action-view skin--responsive page-<safe> rootpage-<safe>`（drop kind-class 启发式）
- 内容包在 `<div id="mw-content-text" class="mw-body-content mw-content-ltr">` 让 wiki_native 的内容选择器生效
- 加 `<a class="skip-link" href="#main-content">跳到主要内容</a>`（继承 v1 iter-14 a11y）
- 加 `<div class="page-categories">` 在内容底部（消费 parse.categories）
- 加 `<meta name="description">`（首 160 chars 内容）
- 加 `<link rel="canonical" href="...原站">` （SEO + 引用）
- 加 `<link rel="icon">` 指向 favicon.ico（从原站抓 av.huijiwiki.com/site_avatar_pf2_l 转换）
- 所有 `<img>` 加 `loading="lazy"`
- 缓存版本 v2a → v2b

**全 Rebuild + Playwright Visual QA**:
- 397 s rebuild, 40,542 files, 0 failures
- 战士 页 vs 原站 战士 截图侧立对比: body bg / quote-block / section heads / 链接色 / statblock 全部一致 ✓
- topnav 是 v2 自己的（brand brown-red mega-menu）vs 原站 dragonhide 黑色 chrome — 是预期的差异

**伴随完成**:
- 从原站 fetch favicon (site_avatar_pf2_l.webp, 173x173) → Pillow 转 favicon.ico/png + Tauri icons 全套 (32/128/128@2x/256/512.png + icon.ico)
- Phase H 现在可以 `cargo tauri build` 不再因缺图标 fail

### iter-15 (~16:00): P0/P1 巩固 + Rust 工具链

User: "继续优化 Rust 你帮我安装就行 其他 P0-P3 继续做"

**Rust 安装**: `winget install --id Rustlang.Rustup --silent` → rustup 1.29.0 + rustc 1.95.0 + cargo 1.95.0 已就绪。`cargo install tauri-cli --version "^2.0" --locked` → tauri-cli 2.11.2 已就绪。

**P0 完成**:

| 项 | 工具/产出 |
|---|---|
| Browse 页 (12 buckets + browse-all) | `build_browse_v2.py` — 33,954 pages 分类成 13 个 browse-*.html，每页含 AoN-style sortable 表 + 客户端 filter |
| `classes/index.html` | `build_class_hubs_v2.py` — 25 真职业 hub（10 个抓到，其他 placeholder） |
| `source/index.html` | 14 known PF2 publications 列表 |
| Wiki sidebar | `_snippets/sidebar_sub.html` 7 个 collapsible group：玩家选项 / 装备 / 法术 / 怪物 / 规则 / 设定 / 其他，含 home link + 嵌入式搜索框 |
| page-head bg fix | `_v2_compat.css` 加 `!important` — 现在 `rgb(109, 32, 2)` brand brown-red 正确显示，h1 cream 配色，金色 underline |

**P1 完成**:

| 项 | 工具 |
|---|---|
| huiji-tt tooltip JS | `huiji_tt.js` — 扫 `.huiji-tt`，组合 `data-template` + `data-params` 成 `title` 浏览器 tooltip，加 dotted-underline 视觉提示 |
| huiji-tt CSS hint | `_v2_compat.css` group 4b — `border-bottom: 1px dotted` |
| `<script>` 注入 build_v2.py | 头部加 `huiji_tt.js` defer |
| sidebar 详细 CSS | 7 个新 selector：sb-home / sb-search / details.sb-group summary/ul/li/a |
| Phase F 全 rebuild | 全 40,541 文件按新模板重新生成（含 sidebar + categories + skip-link + meta description + canonical + favicon + lazy loading + huiji_tt） |

**P1 弃做**:
- pf2icon sprite — 多数页面里 `.pf2icon-{{{动作}}}` 是 unrendered 模板占位（服务端未替换），真实 `.pf2icon-R` 极少。投入产出比低，文档化作未来 TODO。
- 4,746 张未下载图 — 这部分在 Template:/File: ns 引用，对 ns=0 阅读者无影响。

**Phase H 完成**:

| 步骤 | 状态 |
|---|---|
| Rust toolchain | winget rustup → rustc 1.95.0 + cargo 1.95.0 + tauri-cli 2.11.2 |
| 重试 #1 失败 | `bundle.windows.nsis.installMode` schema validation 不过 |
| 重试 #2 失败 | "can't find library `pf2_wiki_lib`" — lib.rs split 后 metadata corrupted |
| 重试 #3 失败 | 同样 metadata corrupted（cdylib + staticlib + rlib triplet 冲突） |
| 重试 #4 成功 | 删除 lib.rs，binary-only Cargo.toml → 编译 3m 55s，exe **1.17 GB**（含 frontendDist embed）|
| 发现 NSIS bundle 失败 | 双重 embed（frontendDist 进 exe + bundle.resources 进 NSIS） → makensis mmap error |
| 重试 #5 成功 | frontendDist 改为最小 `_tauri_placeholder/`，resources 通过 bundle.resources → exe **10.6 MB** + NSIS 1015 MB |

**最终产物**: `src-tauri/target/release/bundle/nsis/PF2 离线百科_0.1.0_x64-setup.exe` — **1015.3 MB (0.99 GB)**，在 GitHub Release 2 GB 单文件上限内。

### iter-14 (~15:45): http.server 替换为 ThreadingHTTPServer

Single-threaded `python -m http.server 7891` 与 36k 文件 rebuild 并行时 ERR_EMPTY_RESPONSE。换成 `_wiki_full_v2/serve.py` (ThreadingHTTPServer)，curl 全 200 OK。

## Known gaps for future iterations

### 🔴 P0 阻断
1. **Browse 页全 404** — topnav 30+ `browse-*.html` 链接没建。需要 `build_browse_v2.py`（按字母/分类/子分类聚合 metadata.pages 输出）。
2. **`classes/index.html`** — 25 真职业 hub，topnav "职业" 入口。
3. **`source/index.html`** — 出版物索引，topnav "规则" 下入口。
4. **`<nav class="wiki-sidebar">` 空** — 看起来像 placeholder。需要按 ns 聚合的左侧导航（如 AoN style category tree）。

### 🟡 P1 重要
5. **`.huiji-tt` tooltip JS 缺** — 很多页面有 `<span class="huiji-tt" data-template="X" data-params="Y">`，纯静态显示 raw `{{{1}}}` 占位。需要 minimal JS 把 data-params 渲染为 tooltip 文本。
6. **`.pf2icon` sprite 缺** — 例如 `<span class="pf2icon pf2icon-动作">` 应显示「⬢」单动作图标。原站用 sprite sheet — 没下载到。
7. **header.page-head bg 未应用** — 应该是 brand brown-red，目前 transparent。需要 `_v2_compat.css` 加 `!important`。
8. **search.html 客户端兼容性** — copied from v1，没验证对 v2 index/shards/ 是否兼容。
9. **缺失 4,746 张图** — 我们只下载了 ns=0 页面引用的 3,028 张。Template:/File: 引用的 4,746 还在远端。可能影响 navbox 装饰。

### 🟢 P2 锦上添花
10. **section TOC** — parse.sections 有数据但没注入。长文章应该有 TOC 浮窗。
11. **search-app.js 验证 + 重新写客户端** — v1 的可能不兼容。
12. **Tauri 代码签名** — 避免 Windows SmartScreen 警告。
13. **暗黑模式验证** — 暗黑切换在新 CSS 链下没测过。

### 🔵 P3 远期
14. **MediaWiki 协议 collapsibles** — `.mw-collapsible` JS 支持。
15. **Update mechanism** — 未来 wiki 更新怎么 deliver patch。

## Current state at session end

- **Phase A** ✅ DONE — metadata.json, scout_report.md
- **Phase B** ✅ DONE — 36,964 non-redirect pages parsed (concurrent curl_cffi c=20, 7.7 min, 0 failures)
- **Phase B.5** ✅ DONE — 3,666 redirect targets resolved
- **Phase C** ✅ DONE — 3,028 images downloaded / 1,028 MB (concurrent c=16, 49 s, 1 skip, 0 fail)
- **Phase F** ✅ DONE — 36,964 pages + 3,578 redirect stubs built (build_v2.py 397 s, 93 pages/s, 0 fail)
- **Phase G** ✅ DONE — search index 10.9 MB titles.js + 35.7 MB shards
- **Phase H** ⏸️ AWAITING — `winget install Rustlang.Rustup`, `rustup default stable`, `cargo install tauri-cli`, then `cd src-tauri && cargo tauri build`

## Resume instructions for next session

### If Phase B died (likely if session ended):

```powershell
cd C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper
.\.venv\Scripts\python.exe dump_parsed_v2.py
# resume picks up automatically from _state.json
```

### After Phase B completes:

```powershell
# Phase C — images (~1 hr)
cd C:\Users\Taka\Desktop\fvtt\pf2wiki-scraper
.\.venv\Scripts\python.exe dump_images_v2.py

# Phase F — full build (~1 hr)
cd ..\_wiki_full_v2
..\pf2wiki-scraper\.venv\Scripts\python.exe build_v2.py
# add --redirects flag if you want redirect stubs

# Phase G — search index (~10 min) — TODO: write build_search_v2.py wrapper
# Or: copy _wiki_full/search-index.json as stopgap then rebuild

# Phase H — Tauri (after user installs Rust)
cd ..\src-tauri
cargo tauri build
```

## Known gaps / TODO before "100% complete"

1. **Redirect target resolution** — `redirect_map` only has 5/2,229 filled. Write a script that batches `titles=A|B|C&redirects=1` to fill targets, then run during Phase F to enable proper redirect stubs.
2. **Browse pages** — v1 had ~200 `browse-*.html` letter/category/subcategory listings. v2 hasn't built them. After Phase B completes, write a `build_browse_v2.py` that consumes metadata.json + parsed pages to generate these.
3. **Wiki sidebar content** — current build_v2.py leaves `<nav class="wiki-sidebar">` empty as placeholder. v1 has a complex collapsible category nav. Port over or replace with simpler design.
4. **Search index v2** — `build_search.py` currently reads `_wiki_full/`; needs a `--root` flag or copy/modify for v2.
5. **Phase C imageinfo URL bug risk** — `dump_images_v2.py` uses `prop=imageinfo&iiprop=...` without `redirects=1`. Some image titles in `parse.images[]` may be redirects themselves; need to verify and add `redirects=1` if needed.
6. **NSIS license file** — `src-tauri/tauri.conf.json` references `../LICENSE`. Need to create or remove that field.
7. **Tauri icon set** — `src-tauri/icons/` empty. User must `cargo tauri icon <source.png>` before first build, or `cargo tauri build` will fail.

## Critical gotchas (carried from v1)

| # | Gotcha | Mitigation in v2 |
|---|---|---|
| 1 | PowerShell mojibake CJK | All scripts use `open(..., encoding='utf-8')`; progress logs ASCII-only via `.encode('ascii', 'replace')` |
| 2 | CSS @import must be before all rules | `_v2_compat.css` added at top of `style.css` @import block |
| 3 | Chrome HTML cache aggressive | Cache buster `?v=v2a` on all v2 HTML; bump to `?v=v2b` when CSS/JS changes |
| 4 | `.kind-class` selector collision | `_v2_compat.css` line 33: `html body { white-space: normal !important }` |
| 5 | CF clearance expiry | `pfwiki._wait_clear` 60 s timeout; user may need to solve interactive challenge once |
| 6 | Long scrape Ctrl-C | All scripts flush state every 50 entries; safe interruption |
| 7 | NTFS filename restrictions | `safe_title()` replaces `:` → `_`, `/` → `__`, strips `*?"<>|` |

## Files added in session 1

### Scripts
- `pf2wiki-scraper/smoke_test_v2.py`
- `pf2wiki-scraper/dump_metadata_v2.py`
- `pf2wiki-scraper/dump_parsed_v2.py`
- `pf2wiki-scraper/dump_images_v2.py`
- `_wiki_full_v2/build_v2.py`

### Data
- `pf2wiki-scraper/out_v2/metadata.json` (40,630 pages)
- `pf2wiki-scraper/out_v2/smoke_result.json`
- `pf2wiki-scraper/out_v2/parsed/**/*.json` (~850+ as of session end, growing)

### Static
- `_wiki_full_v2/assets/*` (copied from v1)
- `_wiki_full_v2/assets/_v2_compat.css` (new)
- `_wiki_full_v2/assets/style.css` (@import bumped)
- `_wiki_full_v2/_snippets/topnav_sub.html`
- `_wiki_full_v2/index.html`, `search.html` (copied from v1 + cache-bumped)

### Tauri
- `src-tauri/Cargo.toml`
- `src-tauri/tauri.conf.json`
- `src-tauri/src/main.rs`
- `src-tauri/build.rs`
- `src-tauri/README.md`

### Docs
- `agent_outputs_v2/scout_report.md`
- `agent_outputs_v2/ITERATION_LOG_v2.md` (this file)
- `C:\Users\Taka\.claude\plans\pf2-lucky-pudding.md` (approved plan)
