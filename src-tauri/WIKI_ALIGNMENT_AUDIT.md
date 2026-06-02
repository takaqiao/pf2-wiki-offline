# PF2 离线百科 — 类目/wiki 对齐 全面审计 (2026-06-02)

> 方法:9 模块多 agent 审计(65 agents / 55 findings / 43 验证通过 / 12 驳回)。基准真值 = metadata.json(wiki 真实页/分类/重定向清单)+ 缓存 live 分类 + 离线产物 + 构建脚本。P0/部分 P1 已我亲自实锤。

## 结论
PARTIALLY TRUE — but not the way the user fears. The user's hypothesis ("很多类目和 wiki 对不齐") is literally correct (43 confirmed divergences across all 9 modules, nothing is perfectly aligned), yet nav_target_audit's earlier read was also right: the misalignment is NARROW IN KIND, concentrated in a handful of root causes that fan out into many symptoms. The 43 findings collapse to ~8 real defects:

(1) ONE metadata regression (redirect_map lost 3661/3666 targets in the 2026-05-21 dump) is the single highest-risk item — a latent break, not yet visible, because on-disk stubs predate it. A rebuild today would silently delete ~3600 redirect stubs (神祇/信仰/组织/译名表/精灵/地精…). This is the only HIGH-blast-radius regression and the clearest "would make the site worse" item.

(2) ONE namespace/category-key normalization gap explains BOTH the 194 delimiter-blob bogus category pages AND the ~1946-member category undercount (templates dropped) AND the 144 English raw-import category stubs — all "synthetic-vs-real" and "structural" symptoms of the same scraper/reverse-index normalization step.

(3) ONE creature-size taxonomy error (微型/超巨型/极巨型 are dead empty stubs; the real sizes 超小型 Tiny=64 and 超大型 Gargantuan=177 are omitted) appears FOUR times: browse-creatures bucket, level subzones, search type-rules (238 creatures mis-badged 其他), and the dragon-statblock symptom. Fix the size set in 2 generators + 1 search rule and all four resolve.

(4) ONE item-category gating error (buckets/search key off Category:物品 instead of the wiki's broader 物品导航 + 子页面 variants) drops 348 base weapons out of the entire item browse AND mis-types ~6000 item-variant pages as 其他 in search. Same root cause, two modules.

(5) Subzone membership is DERIVED from incomplete Data: tables instead of the cached live categories we already have, dropping ~260 focus spells and ~22 cantrips.

(6) The "出版物 pattern" (synthetic stub where the wiki has a real, richer page) recurs in nav/home: the 规则 nav portal omits 规则索引/规则总览/术语索引/勘误索引; home 信仰→browse-deities instead of 信仰综述; browse buckets never link the real topic articles or the 16 curated 列表 pages.

(7) A cluster of label divergences: 异常状态 (wiki says 状态), 生物核心2 (wiki says 怪物核心2 — canonical-label over-application onto a proper noun), 职业 27 (wiki says plain 职业), 装备/物品 inconsistency.

(8) Home book curation is a frozen hand-typed 12-book literal that will keep drifting from the live 17-book home.

So: the user is RIGHT that almost every category has SOME drift, but it is not 40k pages of chaos — it is ~8 generator/normalization bugs whose blast radius is wide. Fix the 8 root causes (mostly small edits in build_browse_v2.py, build_nav_stubs.py, build_search_v2.py, build_v2.py, the nav snippets, and a one-line metadata repair) and the bulk of the 43 findings clear at once.

## 优先修复(top fixes,按价值排序)
1. [P0 / blocking before ANY rebuild] Repair redirect_map in out_v2/metadata.json. Stopgap: copy the 3666 nonempty targets from metadata_backup_20260519_2222.json (2229 keys overlap, all verified to point at real pages). Root fix: in dump_metadata_v2.py make follow_redirect_targets() re-run on any src whose target is '' (don't early-return on stale targets_filled:true). Then ALSO fix build_v2.py:1038 coverage metric to divide by the is_redirect ns0 page count (~3665), not len(redirect_map), and warn when resolvable targets <80% — this would have caught the regression. Without this, a rebuild deletes ~3600 stubs.
2. [P1] Fix the creature-size set in ONE place each: build_browse_v2.py BUCKET_CATS['creatures'] and build_nav_stubs.py SIZE_CATS line 98 -> [超小型,小型,中型,大型,巨型,超大型] (drop 微型, add 超小型); build_search_v2.py:69 creature signals -> {中型,小型,大型,巨型,超大型,超小型,生物子类} (drop dead 微型/超巨型/极巨型). Rebuild browse-creatures, subzones, types.js. Recovers 64 Tiny + restores ~238 creatures (incl. all ancient/adult dragons) to the 生物 badge.
3. [P1] Fix item gating: switch BUCKET_CATS['items'] (build_browse_v2.py) and the build_nav_stubs parent['items'] gate from ['物品'] to union {物品,物品导航,基础武器,基础护甲}; add a weapons-subzone rule including Category:基础武器; in build_search_v2.py:71 add the '…子页面' item signals (物品子页面/穿戴物品子页面/手持物品子页面/特殊魔法武器子页面) and drop the dead 诅咒物品/魔法物品. Recovers 348 base weapons into item browse and ~6000 variant pages into the 物品 search type.
4. [P1] Re-derive the spell subzones from the cached live categories we already have instead of Data: tables: browse-spells-focus from Category:聚能 (out_v2/_cat_audit/_live/a7c0487ddcd1027a.json, +263 spells) and browse-spells-cantrips from Category:戏法 (1ba5ab676bdc032f, +22). Keep the parent-法术 intersection.
5. [P1] Fix category-key normalization in build_v2.py (reverse-index ~line 905 + [4b] gate ~984): split each scraped category name on [,;，；] into components and route members to each real component; suppress writing any synthesized [4b] page whose name still has a delimiter and is not in metadata ns14. Removes the 194 blob pages and repoints ~250 page-bottom 分类 links. Make the same builder namespace-aware so category headers show the wiki categoryinfo.size (footnoted '不含模板/文件') — clears the ~1946-member undercount too.
6. [P2] Expand the baked 规则 nav (the 出版物 pattern at portal scale): in _snippets/topnav_sub.html (and the duplicated block in index.html) add 规则索引/规则总览/创建角色/术语索引/勘误索引/特征 (all target HTML already on disk); mirror into sidebar_sub.html. Then add the core-rules + 列表 access (动作/状态/苦难/危害/环境/仪式 and 法术列表/武器列表/危害列表/仪式列表/动物伙伴列表) either as a home '规则速查' grid or as topic callouts atop each browse bucket.
7. [P2] Repoint synthetic-vs-real label/destination divergences: home 信仰 -> pages/信仰综述.html (not browse-deities); pages/专长.html redirect -> pages/通用专长.html (the article, not the category dump); generate_homenav.py '全部出版物→' -> pages/出版物索引.html (lock in the exemplar fix against regeneration). Add render_browse_html TOPIC_ARTICLE map linking each axis to its real article (feats→通用专长, spells→法术/法术列表, items→装备, creatures→生物, other→状态).
8. [P2] Correct labels: BUCKET_LABELS['other'] 异常状态 -> 状态 (+ replace the 5 hardcoded nav labels); home book label 生物核心2 -> 怪物核心2 (generate_homenav.py:31 + index.html, href already correct); nav '职业 27' -> '职业'; make 装备/物品 consistent for the browse-items target. Update class-hub: split PF2r(25) vs PF2e未重制(魔战士/召唤师) grouping, fix the provenance caption, and bump the stale '25 真职业' docstrings to 27.
9. [P3 / accept-or-defer] Home book curation: drive generate_homenav.py 出版物 from _homepage_summary.json links_sample (17 books) or accept the 12-book stub since 全部出版物→ already reaches the real index. Lowest-value items: ITEM_GROUPS dead token 魔杖->基础魔杖; add 手持物品/特殊盾牌 subzones; add 需要帮助/译名表 home links; English trait-stem cat stubs — fix opportunistically or document as accepted.

# 分形态明细
## broken-redirect (the only HIGH-risk, latent regression)
- [HIGH] redirects-aliases: build_v2 consumes out_v2/metadata.json redirect_map which now has only 5/2231 nonempty targets (was 3666) -> a rebuild deletes ~3600 stubs (神祇/信仰/组织/译名表/精灵/地精). Root in dump_metadata_v2.py follow_redirect_targets() early-return on stale targets_filled:true => repair metadata from backup + fix the dump step + fix the coverage metric.
- [MED] browse-buckets: pages/专长.html redirects to category/通用专长.html (283-row dump) instead of the wiki's real article pages/通用专长.html => prefer ns0 article when a title is both ns0 + ns14.
- [MED] publications: generate_homenav.py:38 '全部出版物→'->source/index.html (redirect stub); only the deployed index.html was hand-fixed => regeneration regresses the exemplar fix; repoint generator to pages/出版物索引.html.

## synthetic-vs-real (the "出版物 pattern")
- [HIGH] category-pages: 194 delimiter-blob category pages synthesized from comma/semicolon-joined trait/item/deity strings the wiki has no ns14 page for (build_v2 [4b] loop) => split category keys on [,;，；] before indexing.
- [MED] redirects-aliases: home 信仰 -> browse-deities.html (synthetic grid) but wiki 信仰 redirects to the real 信仰综述 article => repoint to pages/信仰综述.html.
- [LOW] browse-buckets: browse-feats/spells/items/creatures/other.html are pure member dumps with no link to the wiki's real richer topic article => add TOPIC_ARTICLE callouts.
- [LOW] category-pages: 144 English raw-import cat stubs (Fungus（特征）, Decay domain deities (2E)) — mirror the wiki's own untranslated tags; low priority, document or map to Chinese equivalents.
- [LOW] home-nav-structure: home 出版物 12-book grid is a hardcoded stub vs live 17-title featured set — same anti-pattern, mitigated because 全部出版物→ reaches the real index.

## membership-drift (mostly ONE size bug + ONE derivation gap)
- [HIGH] browse-buckets + [MED] subzones (SAME bug): 超小型 (64 Tiny creatures) omitted and dead 微型 anchor included; browse-creatures shows 1490 vs live 1550.
- [HIGH] subzones: 聚能 focus-spell subzone missing ~263 of 617 (Data-table derivation vs cached Category:聚能).
- [HIGH] subzones: 戏法 cantrip subzone missing 22 of 112 (same derivation gap vs Category:戏法).
- [MED] publications: home 出版物 shows 12 vs live 17 books (missing 《亵渎堡垒》《地狱天命》《地狱破灭》《幽暗地脉》《黑暗档案》（重制版）).
- [LOW] publications: category/出版物.html 366 vs live 373 — 3 real redirect-typed book pages dropped (rest are ns10 templates / cache rename, correctly excluded).
- [LOW] redirects-aliases: 元素使->元素使职业变体 alias — NOT a current break; re-verify after the metadata repair.

## wrong-anchor-or-label
- [HIGH] search-taxonomy: creature size signals wrong (dead 微型/超巨型/极巨型; missing real 超大型/超小型) => 238 creatures mis-typed 其他. SAME root as the size bug above.
- [HIGH] search-taxonomy: item '…子页面' categories omitted => ~6000 variant pages mis-typed 其他. SAME root as the item-gating bug.
- [HIGH] home-nav-structure + [MED] browse-buckets (SAME): label 异常状态 but the wiki's real category/article is 状态.
- [MED] publications + [LOW] index-portals (DUP): home label 生物核心2 vs real 《怪物核心2》 (canonical-label over-applied to a proper noun).
- [MED] home-nav-structure: 装备 vs 物品 used inconsistently for the same browse-items target.
- [LOW] class-hub: nav label '职业 27' leaks internal count; wiki says plain 职业.
- [LOW] class-hub: intro caption wrongly attributes all 27 classes to PF2r remaster line (魔战士/召唤师 are PF2e/《魔法之秘》).
- [LOW] browse-buckets: items has no topic link because 物品/地理 have no bare-title article — 装备 is the wiki's items page (correctly note 地理 has none).
- [LOW] redirects-aliases: wiki home shows 译名表 alias; our home only surfaces 术语索引.

## missing-real-page
- [HIGH] index-portals: baked 规则 nav omits the entire rules portal (规则索引/规则总览/术语索引/勘误索引/创建角色); only 出版物 carried over.
- [MED] index-portals: core rules pages (动作/状态/苦难/危害/环境/死亡/仪式/魔法物品) scraped-complete but absent from home+nav (2nd-class once 规则索引 is in nav).
- [MED] browse-buckets + [MED] subzones + [LOW] index-portals (overlapping): the wiki's 16 curated 列表 articles (法术列表/武器列表/危害列表/仪式列表…) are scraped but linked nowhere.
- [LOW] home-nav-structure: home omits 分类:需要帮助 (live 首页 帮助中心 pairs 帮助+需要帮助; category/需要帮助.html already built).

## structural-mismatch
- [HIGH] subzones: 348 base weapons (Category:基础武器) fall out of BOTH the weapons subzone AND the items parent (parent keys on 物品, base weapons live under 物品导航/基础武器). SAME root as the item-gating search bug.
- [MED] class-hub: hub flattens the wiki's PF2r(25) vs PF2e(2 legacy) split into one 27-row list.
- [MED] home-nav-structure: home 世界设定 adds a 地理 tile the live 首页 axis doesn't have (wiki reaches geography via 内海).
- [MED] search-taxonomy: dragon/element statblocks badged 其他 — downstream symptom of the size bug, kept as a regression test.
- [LOW] home-nav-structure: topnav '设定' menu collapses the wiki's 9-item 世界设定 axis to just 信仰+地理.
- [LOW] category-pages: category counts undercount by excluding ns10 templates (~1946 members; 法术 1761 vs 1765, 《怪物核心》1019 vs 1200). SAME root as the empty-category/normalization fix.
- [LOW] subzones: ITEM_GROUPS['implements'] dead token 魔杖 (real values 特殊魔杖/基础魔杖); base wands fall through.
- [LOW] subzones: real item types 手持物品(244)/特殊盾牌(3)/持握物品/卷轴 mapped to no subzone.
- [LOW] publications: home book curation is a frozen literal, not a projection of _homepage_summary.json — root cause of the drift items.
- [LOW] redirects-aliases: stub-coverage metric divides by the degraded redirect_map, masking the P0 regression.

## other
- [LOW] class-hub: stale '25 真职业' docstrings (lines 1, 120) contradict the 27-class implementation.

## DROPPED (not problems)
Verifiers explicitly confirmed these are NOT problems — do not chase them:
- 出版物 nav (the exemplar) is already correctly repointed to pages/出版物索引.html in the deployed index.html; only the GENERATOR (generate_homenav.py:38) still lags, which is a separate regression-prevention item, not a live break.
- 地理 has NO single ns0 overview article on the wiki (only 分类:地理, 1159 members) — correctly omit a topic link; do not synthesize a 物品/地理 stub. Likewise 物品 is NOT an ns0 article (only the category); the wiki's items overview is 装备.
- 异常状态 was previously logged as a 'canonical label' in prior work — that note is WRONG vs the wiki (wiki uses 状态); flagged for correction, but it is a known prior decision, not a new discovery.
- category/出版物.html's 8 live-only members: 4 are ns10 模板:* (correctly excluded), 1 is 《无形之境》 (a stale-cache rename of the real 《未见之境》 we DO have — cache vintage, not a bug). Only 3 redirect-typed book pages are a genuine (low) omission.
- 微型 size cache shows 0 due to page_missing — it is genuinely an EMPTY/non-existent size, so the only real creature-size GAP is 超小型 (and search also needs 超大型). Don't treat 微型 as a real category to repopulate.
- 元素使/铸念师/魂铸者 *变体 redirects currently resolve correctly on disk; flagged only to RE-VERIFY after the metadata repair, not as a current break. Likewise the class hub's 御能师 canonical mapping is correct.
- Accepted baselines confirmed by verifiers, NOT to be re-reported as defects: ~1.7% content dead links = genuine wiki redlinks; the ns0 slice of the category undercount (~33 members) = the accepted ~0.2% live-edit staleness (recent pubs 《地狱天命》《无形之境》); the 98% bulk of the undercount is ns10 templates (non-user-facing). The English raw-import category stubs faithfully mirror the wiki's own untranslated tags, so they are 'used' on the wiki — accept-or-cosmetic, not invention.
- The 6-menu AoN-style topnav reorg itself is a LEGITIMATE redesign choice (not a divergence to undo) — only the under-population of the '设定' menu is the finding.
- Net: many '类目对不齐' impressions are duplicates of ~8 root causes or are by-design/accepted; the genuinely actionable, wiki-truth-backed defects number ~8 root fixes (the 43 are their symptoms).
