# PF2 离线百科 — UI/UX/分类/交互 全面研究报告 (2026-06-02)

> 方法:8 维度多 agent 设计研究(113 agents / 104 提案 / 104 全部通过对抗式批判与事实核对)。
> 基于**真实渲染截图**(首页明/暗、生物 statblock、browse、search)+ 真实 CSS/HTML + live wiki 结构。
> 这是研究/提案交付物;实施需用户授权。批判者已纠正多处事实错误(见末尾 CORRECTIONS)。

## 设计方向(统一愿景):一个声音 · 一套分类 · 一个招牌组件
Make the offline wiki feel like a single, confident, published PF2 reference — not three competing nav systems wrapped around a raw wiki dump. The unifying idea is "one voice, one taxonomy, one signature component." (1) ONE VOICE: a real design-token system (type scale, spacing, radius, elevation, an accent ramp, warmed borders, repaired dark mode) so every surface speaks the same brand language — white page, dark-grey text, the brown-red #6d2002 band crowned with a gold rule, CJK-first fonts. (2) ONE TAXONOMY: a canonical label dictionary (生物/族裔/状况/穿戴物品/信仰/地理) applied to topnav + sidebar + browse + search, with the home center-grid as the single visual category map; the topnav is its compact persistent form; the left rail stops duplicating it and becomes a personal/utility dashboard (recent, bookmarks, letters). (3) ONE SIGNATURE COMPONENT: the PF2 statblock finally gets its real red header band + gold rule + bold accent labels + bordered trait chips, so the most-viewed page type reads as an authentic Pathfinder statblock instead of run-on grey text. Around that, two cross-cutting wins: kill the copyright/license boilerplate that currently buries every search excerpt and opens every content page, and add the missing interaction/a11y floor (focus rings, reduced-motion, a shared toast, keyboard search nav, back-to-top, fixed mobile drawer). The feeling target: a calm, scannable, "real book" reference where the brand red is a deliberate accent (statblock crowns, section ticks, focus rings) rather than absent — coherent in both light and dark, fast because it's local disk, and never fighting its wiki-mirror nature.

## 速赢清单(高影响 / 低成本,建议先做)
1. Strip license/copyright boilerplate at build time (only .well.quote-success / .quote-primary, plus the 此数据的文档… preamble) before excerpt + index generation — fixes 40.3% of indexed entries (14,948/37,097); the single highest-impact change, ~8 lines in build_search_v2.py iter_parsed()
2. Give the statblock its real red header band + gold rule + bold accent labels (CSS-only in _v2_compat.css, targets existing span.name / .statblock b; ~30 lines) — transforms every creature/spell/feat/item page
3. Canonical-label sweep of the three highest-visibility splits: 怪物→生物, 祖先→族裔, 戴持物品→穿戴物品 across topnav_sub.html / sidebar_sub.html / index.html / search.js (string swaps + one BUCKET_LABELS key)
4. Add a global :focus-visible ring via :where() (0-specificity) as the last block in _fmt_mobile.css, gold in dark mode — keyboard accessibility floor for the whole app
5. Add the global prefers-reduced-motion gate to _fmt_mobile.css (only home page is covered today) — covers all ~24k generated pages with one media block
6. Demote the opening license box on content pages via CSS (.mw-parser-output > div.well.quote-success:first-child { opacity:.55; font-size:.75em }) — zero rebuild, instant across all pages
7. Warm + lighten the border tokens (--border #dddddd→#e7e3dd, --border-strong→#c9c2b8) and lift --fg-mute to clear WCAG AA (light #6a6a6a, dark #a0a0a0) — one-token edits that propagate everywhere
8. Fix the updater banner z-index/stacking so it never amputates the topnav, with role=status (S, fixes a real usability bug)
9. Promote trait rows to bordered PF2 chips + cap prose measure at ~74ch (two small CSS blocks, high readability payoff)
10. Wire the existing recent/bookmark localStorage into a live '继续阅读/我的收藏' home rail widget (~40 lines vanilla JS; bookmark.js already does the hard part)

## 分阶段路线图
### Phase 1 — 基础(设计令牌 + 低成本高影响修正)
Lay the token + correctness foundation everything else builds on. DESIGN TOKENS (in _v2_palette.css): add a modular type scale (--fs-* / --lh-* / --fw-*) and fix BOTH hardcoded font sizes (palette line 118 + _v2_compat.css body) to use --fs-md; reorder --font-sans CJK-first; add spacing/radius/elevation scales (--sp-*, --r-*, --e-* aliasing existing --shadow-sm/md); add the accent ramp + tint surfaces (--surface-accent via color-mix); warm the border tokens; lift --fg-mute to AA in both modes; repair dark mode (wider luminance steps, warm coral accent in the same hue family as #6d2002 instead of scarlet, visible shadows); re-enable --font-display as serif. CHEAP HIGH-IMPACT FIXES (parallel, mostly CSS/JS, no token dependency): build-time license-boilerplate strip (search excerpts + index + content-page CSS demotion); the canonical-label dictionary + the 3 priority relabels (生物/族裔/穿戴物品) and 状况; global :focus-visible ring; global reduced-motion gate; updater-banner stacking fix; shared pf2Toast + aria-live primitive (foundation for all later action feedback). Establish _components.css (.card/.section-h/.chip/.badge) and move the search per-kind color tokens into the global palette so browse/home/content can all color-code consistently.

### Phase 2 — 四大核心页面重设计
Redesign the four main screens on top of the Phase-1 system. STATBLOCK / CONTENT PAGE: red header band + gold rule + bold accent stat labels + bordered trait chips + ~74ch prose measure + serif heading rhythm + fixed action-icon baseline/empty-suffix; collapse the redundant left sidebar to a real page-context rail (home + inline search + bookmark/recent + optional '同类条目' siblings block), keeping the right-rail TOC. HOME: fold search into a taller welcoming hero with a one-line onboarding link + a dismissible 3-step '从这里开始' onramp; replace the four tiny link-tile grids with one row of larger visual category cards (icon + count + blurb via an inline SVG sprite, NOT pf2icon.ttf); slim the left rail to letters + the live recent/bookmark widget (remove the duplicate category groups); tighten the 8-cell stat panel into one confident data strip; give the hero a red-crown top bar matching page-head. BROWSE: kill the dead 类型 column; make columns bucket-aware from the joined Data record (feats: 等级/特征/分类/来源; spells: 环级/根源; creatures: 等级/体型/稀有度; items: 物品分类/稀有度/价格); render rarity/size/trait as colored pills; wire the existing filter.js facet rail + per-bucket subzone chip bar + sticky header; convert the 25k-row browse-all + browse-CJK mega-tables into a type+letter matrix hub. SEARCH: anchor excerpt window on the query term + <mark> highlights; add a per-result meta strip (level/traits/rarity/source from build); full keyboard nav (↑↓/Enter/Esc) + whole-row click target; recent-searches + useful empty/initial state + did-you-mean recovery; live/truncation count badges. IA: collapse the 规则 grab-bag menu, promote 出版物 to top-level and de-stub source/index.html, demote 分类页面 to footer/About.

### Phase 3 — 交互 / 移动 / 无障碍打磨
Interaction, micro-UX, mobile, a11y delight. INTERACTION: confirm+undo on bookmark toggle + a real bookmarks.html page; keyboard-shortcut discoverability ('?' hint button + first-run nudge + accurate cheat-sheet); back-to-top button + reading-progress bar on long pages (with G keybind); copy-link ¶ anchors on headings (reusing the shared toast); lightbox caption + don't-dismiss-on-image-click; tooltip fade-out + loading min-height; sticky-scroll-spy TOC highlight; auto-collapse the green provenance boxes into a one-line source banner; labeled accent-band <hr> dividers; unify overlay Esc dismissal + focus trap/restore for modal & lightbox. MOBILE/A11Y: fix the off-canvas drawer (Esc-close, inert focus suppression, aria-expanded, resize reaction) and the mirror TOC-rail resize bug; touch-guard the mega-menu hover; bigger collapsible/TOC touch targets; wide-table scroll affordance + keyboard region; mobile search-mini button; kill the topnav search-input width jump; skip-link on home. DESIGN-SYSTEM POLISH: redesign the dated section-header double-rule into the left-tick idiom; cohere the colored callout boxes (+dark-mode gap); trait/rarity chip token system; masthead refinement (topnav band + quiet page-head sub-head). DEFER: theme crossfade, URL-addressable facet state, instant topnav search dropdown, the !important dark-mode refactor, the editorial 本期推荐 spotlight.

# 分维度提案(各维度 top 确认项)
## design-system
- [好看/正确/人性化][S/high] Statblock red header bar — turn span.name into a filled --accent-band band with gold border-bottom + bold accent stat labels (`.statblock b`); the signature component, CSS-only, no generator change
- [好看/合理][M/high] Extend the accent into a real ramp + tint surfaces (--accent-700/600, --surface-accent/-2 via color-mix) applied to specific hover/section surfaces — escapes border-only hierarchy
- [好看][S/high] Soften + warm the global border tokens (#dddddd→#e7e3dd) and adopt fill-over-hairline (transparent border + shadow-sm) on home cards/stat boxes/rail panels
- [好看/合理/人性化][M/high] Modular type scale + CJK-first font reorder; fix BOTH hardcoded font-sizes (palette:118 + compat body) to var(--fs-md); add --tracking-cjk to prose
- [好看/正确][M/high] Repair dark mode: wider luminance steps, warm-coral accent in the #6d2002 hue family (not scarlet #c43a3e), visible shadows
- [好看/合理][M/high] Add spacing/radius/elevation token scales (alias existing --shadow-sm/md) and sweep authored CSS only (skip wiki_native.css)

## ia-categorization
- [正确/合理][S/high] Rename nav 怪物→生物 across all four surfaces (topnav/sidebar/index/BUCKET_LABELS) — eliminates a creature-lookup terminology split
- [正确/合理][S/high] Rename 祖先→族裔 to match wiki/browse/search canonical term (4 files, no parenthetical gloss)
- [正确/合理/人性化][S/high] Align search-type labels to canonical set (神祇→信仰, 地点→地理, 祖先→族裔) + 戴持物品→穿戴物品
- [正确/合理/人性化][M/high] Collapse the 规则 grab-bag menu, promote 出版物 to top-level, move 分类页面 to footer/About; de-stub source/index.html with real page links
- [正确/合理/人性化][M/high] One canonical label dictionary as single source of truth (_labels.py + labels.json/labels.js) with a build-time assertion against the hand-maintained snippets
- [合理/人性化/好看][M/high] Designate the home center-grid as the canonical IA layer; slim the left rail to additive content (letters + counts) and reconcile vocabulary everywhere

## content-reading
- [好看/正确/人性化][S/high] Statblock red header band (name + level/type pill, muted AoN link, gold rule) — replaces the left-bar pseudo treatment
- [好看/正确/人性化][S/high] Promote the traits row to bordered PF2 trait chips with a separator rule before the stat body
- [人性化/好看][S/high] Cap prose reading measure at ~74ch (direct-child selectors; exclude statblocks/tables/navboxes/notice boxes)
- [合理/人性化/好看][M/high] Replace the redundant left sidebar with a this-page rail (strip the 7 nav groups; keep home+search+bookmarks+recent; keep right-rail TOC)
- [人性化/合理/好看][M/high] Demote the copyright/license box: strip from search excerpts (S) + CSS-recede the opening content-page box (S)
- [人性化/好看/合理][M/high] Turn run-on stat lines into an aligned grid (CSS accent on all `.statblock div b` first; then builder-wrap the ability + AC/saves rows)

## search
- [人性化/合理/正确][S/high] Strip license boilerplate from excerpts + index at build time (only .well.quote-success/.quote-primary + preamble regex) — fixes 40.3% of entries
- [人性化/合理/好看][M/high] Anchor the excerpt window on the query term + <mark> highlights (Phase 1 pure JS; Phase 2 widen stored excerpt to 300ch after boilerplate strip)
- [合理/正确/人性化][M/high] Per-result meta strip (level/traits/rarity/source) read from categories[0] + type-specific regex at build time
- [人性化/好看][M/high] Full keyboard nav of results (↑↓/Enter/Esc) + roving active row, hint text, cheat-sheet update
- [人性化/好看][S/med] Make the whole result row clickable (stretched-link) with a per-type left accent bar on hover/focus-within
- [人性化/合理][S/med] Recent searches in localStorage with click-to-rerun + clear, shown in the empty-input state

## interaction
- [人性化/合理][S/high] Discoverable keyboard shortcuts — persistent '?' hint button (plain text, matches theme button) + optional first-run toast + mobile 工具 entry
- [人性化/正确][S/high] Shared pf2Toast + aria-live primitive (optional undo callback, pointer-events:none, z-index:9999) — foundation for every action
- [正确/合理/人性化][S/high] Fix updater banner stacking so it never occludes the topnav, with role=status + slide-in (reduced-motion guarded)
- [人性化/合理][M/high] Confirm+Undo on bookmark toggle + a real bookmarks.html page reached via a static topnav ★ link (not right-click/long-press)
- [人性化/好看][S/med] Back-to-top button + reading-progress bar on long pages, with a G keybinding registered in the cheat sheet
- [人性化/合理][S/med] Copy-link ¶ anchors on headings (target span.mw-headline[id]) reusing the shared toast

## mobile-a11y
- [正确/人性化][S/high] Global :focus-visible ring via :where() (0 specificity) as the last block in _fmt_mobile.css; gold in dark mode; include th[tabindex]
- [人性化/正确/合理][M/high] Fix the off-canvas drawer: Esc-close+focus-return, inert focus suppression, aria-expanded mirror, debounced resize reaction (hamburger create/teardown)
- [人性化/正确][S/high] Touch-guard the mega-menu hover ((hover:hover) matchMedia + @media(hover:none) override + touch-action:manipulation)
- [正确/人性化][S/med] Global prefers-reduced-motion gate in _fmt_mobile.css (currently only home page inline)
- [正确/好看][S/med] Lift dark-mode --fg-mute (#808080→#a0a0a0) and light (#707070→#6a6a6a) to clear WCAG AA; fix .pf2-tt-source opacity stacking
- [合理/好看][S/med] Fix the right-rail TOC load-time-only placement (debounced resize handler; remove the early-return guard that blocks restoration)

## home
- [人性化/合理][M/high] Wire recent/bookmark localStorage into a live '最近浏览/我的收藏' right-rail widget (read-only, first-run-safe, ~40 lines JS)
- [人性化/好看/合理][S/high] Make the hero own search + onboarding (fold the search-band into a taller hero on index only; add one onboarding line)
- [好看/合理/人性化][M/high] Replace the four tiny link-tile grids with one row of visual category cards (icon+count+blurb); 世界设定/出版物/索引 become compact pill rows
- [人性化][S/high] Dismissible 3-step '从这里开始' newcomer onramp (mount the existing .quickstart component, visible by default)
- [合理/人性化][M→S/high] Give each nav surface a distinct job — delete the ~12 duplicate left-rail category links, add a 出版物浏览 axis link, keep letters
- [正确/好看][S/med] Fix the home rail color-dots referencing undefined vars by moving the per-kind palette into _v2_palette.css; tighten the 8-cell stat panel into one data strip

## browse-lists
- [正确/合理/人性化][M/high] Kill the dead 类型 column; make columns bucket-aware from the joined Data record (feats/spells/creatures/items each get rich, scannable columns)
- [好看/人性化/合理][M/high] Render rarity/trait/size as colored PF2 pills (substring rarity match; no 常见 pill); regenerates all browse pages from Python
- [人性化/合理/好看][M(not L)/high] Faceted filter rail feeding the existing pager — filter.js is already built; the work is Python-side data extraction + data-* attributes + injecting the filter bar
- [合理/人性化/正确][M/high] Convert the 25k-row browse-all + browse-CJK mega-tables into a type+letter matrix hub (sub-bucket CJK by category) — eliminates the 5MB DOM table
- [人性化/合理][S/med] Per-bucket subzone shortcut chip bar at the top of each list (with counts), also expanding the sidebar details
- [人性化/好看][S/med] Sticky table header (top:48px clear of topnav) + persistent count/active-filter bar while scrolling

## NOTE: full per-dimension detail (all kept proposals) is in the Phase roadmap; the above lists each dimension's top confirmed items.

## CORRECTIONS
The critics flagged several proposals that were factually wrong about the CURRENT state — these corrections are baked into the kept versions:
- pf2_theme.css is NOT loaded and its class names (sb-title/sb-level) do NOT appear in generated HTML; the statblock fix must target the existing span.name DOM, not load pf2_theme.css (which would conflict with wiki_native.css).
- The license-strip must NOT decompose bare .well — verified bare .well holds legitimate content (update notices, '相关内容' sidebars, rule summaries). Only .well.quote-success / .well.quote-primary are exclusively license/attribution boxes.
- Heading/headline IDs are on a child span.mw-headline[id], NOT on h2/h3 — affects scroll-spy TOC and copy-link anchors (querySelector must target the span, then .closest('h2,h3')).
- cursor:zoom-in/out on lightbox source images is ALREADY implemented (_v2_compat.css L1263/L1317) — drop that sub-proposal; the real gaps are stop-propagation on the image + a caption.
- The skip-link single-target 'gap' is already correctly implemented; the real gaps are the home page lacking a skip-link entirely and the absence of any back-to-top affordance.
- The tooltip fade-IN already exists (_v2_compat.css 296-301); only fade-OUT, a loading min-height, and reduced-motion are missing.
- --fg-mute fails WCAG AA in BOTH modes, not just dark (#707070 on white ≈ below 4.5:1), so the light value must also be lifted.
- Several phantom tokens cited in original proposals do NOT exist in the loaded files (--r-sm, --font-num, --r-lg, the '5px' radius, .stat-num/td.num selectors) — kept versions use only real tokens or define new ones explicitly.
- filter.js, wikitable_paginate.js, and wikitable_sort.js infrastructure already exist, so the faceted-filter and URL-state work is M (Python data extraction), not L.
- pf2icon.ttf contains ONLY action-cost glyphs (1/2/3/F/R) and has NO category symbols — home/category iconography must use an inline SVG sprite, not the font.
- The root topnav is INLINED in index.html (no separate root snippet), so every nav/label edit must be applied to BOTH topnav_sub.html and index.html (plus regenerating baked browse pages).
