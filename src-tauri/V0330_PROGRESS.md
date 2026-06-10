# v0.3.30 — 全面保真度修复批账本（WIKI_FIDELITY_AUDIT RC1-RC7 + 42-agent 新审计）

> 用户 2026-06-10 指令「全面审计 PF2wiki 项目，让它和原生 wiki 体验一致，优化/修复」。
> 两轮工作流：审计 42 agents（6 已知根因核验 + 5 新维度 + 对抗核查 + 完备性批评）→ 实施 10 agents（5 实施 + 5 审查）→ 主控收尾整合。
> 审计原始规格：`src-tauri/V0330_AUDIT_SPECS.md`（6 RC + 27 confirmed + 3 rejected/备案 + critic）。
> 改动前原件备份：`src-tauri/_v0330_backup/`（11 文件）。基准 = v0.3.29。**发版需用户单独授权。**

## 已知根因（WIKI_FIDELITY_AUDIT.md，全部落地 ✅）

- [x] **RC1 (P0) 标题索引裸键覆盖**：`build_v2.py` 索引循环重写为 `build_title_index(meta)` —— ns0/102 无冒号标题也登记 `bare_owner_prio`，后到 ns14 不再覆写。160 个碰撞键 clobbered 0（武器/护甲/动作/《核心规则书》等 110 个有效受害键翻转回 pages/）。**配套必要修正**：页脚分类条查找链加 `分类:{X}` 中间查找（metadata ns14 全部用 `分类:` 前缀，原行为靠 RC1 缺陷才碰巧正确）。另做规格「可选加固」：两处 `redirect_map.get(t) or t`（空目标=无重定向）。
- [x] **RC2 导航指向原生富清单**：topnav_sub.html（桌面+移动）/sidebar_sub.html/index.html（内联 topnav+左 rail+homenav 卡片）—— 法术→法术列表(6,985 链)、生物→生物总表(8,756 链)、武器拆近战/远程、护甲→基础护甲列表+盾牌、新增 仪式/戏法/主题法术/危害/动物伙伴/载具/攻城武器/魔法刺青/符箓/圈套 等原生清单项；browse-* 降级为「浏览:XX(表格)」二级项。R6 规则菜单 8 项与 R8（信仰综述/出版物索引）红线未动。注意 2r 版本陷阱：链无后缀文件（法术列表/动物伙伴列表），不链 （2e） 旧版；武器列表.html 是消歧义页不直链。
- [x] **RC3 子页面指针桩转跳**：5,017 个 ns0 指针桩（"本页面是存放…子页面"）→ `SUBPAGE_POINTER_RX` 检测，渲染为 script+meta 双保险跳转桩，父页经 RC7 _chase 折叠+RC1 修复后索引解析；父页不存在/自指 → kept_static 保持原样。搜索侧（build_search_v2.py）同一正则整体剔除。误伤 0（50 命中样本人工核验+负样本）。
- [x] **RC4 分类合成噪声清理**：[4b] 不再合成 194 分隔符 blob（v0.3.29 已有）+ ~545 「…子页面」簿记/维护伪分类（相关/PC/含有受损文件链接的页面 等 MAINT_PSEUDO_CATS 名单）；704 个单成员自指分类 → 极简跳转桩直达成员条目；页脚分类条对不再有页面的伪分类降级为 `<span class="new">` 纯文本（_v2_compat.css 加红字样式）；[4b] 末尾孤儿 sweep（仅 category/，casefold 白名单防 NTFS 误删，n_fail>0 时跳过——审查员防护）；build_browse_v2.py categories 桶按磁盘存在性剔除 + 自指分类直链成员条目。
- [x] **RC5 缺 .flex 规则**：`.mw-parser-output .flex{display:flex}` + `.flex-wrap`（~58% 页面金边状态块塌缩的根因，一行修复）。
- [x] **RC6 首页补全**：index.html 加「维基原版首页」入口×2（存档快照文案）+ 跑团工具 6 外链 rail 卡片（PF2 Tools/Pathbuilder2e/Foundry VTT/Scribe/Monster Tool/PF2 Easy，走 external_links.js）+ 特色词条（塔-巴丰）+ 维基任务/需要帮助页面 链接；generate_homenav.py SECTIONS 同步（防将来重生成回贴覆盖）；_v2_compat.css 加 ~25 条 `body.page-首页` 限定作用域的 Tailwind/grid 规则修复 pages/首页.html 单列塌缩 + :has() 隐藏 huiji 死 embed。
- [x] **RC7 重定向链折叠 + 无闪屏**：`_chase()` visited-set 防环折叠到终端真页（45 条 2-3 跳特征别名链全折叠）；自指（任务__首页推送/博客）不再无限刷新；所有跳转桩 meta-refresh 前加 `<script>location.replace(…)</script>`（WebView2 必启 JS → 基本无闪屏，meta 兜底）；[5/5] existing_titles 改用 rendered_titles（幽灵 redirect 源恢复生成 stub）；专项审计 3,610 个 stub 0 个覆写真页。

## 42-agent 新审计 confirmed 修复（同批落地 ✅）

**P0×3**
- [x] **CF1/VF1 图片锚点整体删除**：rewrite_links() 原把 `<a class="image"><img></a>` 整体删除 → 3,062 页丢 9,118 张图（怪物立绘/书封/职业立绘）。改 `a.unwrap()` 保 img 交 rewrite_images() 本地化。
- [x] **INT-1 折叠表格藏标题行**：mw_collapsible.js 折叠 TABLE 藏整个 tbody（1,648 页导航框首屏消失不可恢复）。复刻 MediaWiki makeCollapsible：只藏 toggle 行外的 tbody>tr。
- [x] **SRCH-1 重定向别名不入索引**：AC/巨龙/挥砍/先攻/HP 等 3,614 别名零结果 → build_search_v2 合成别名条目（沿链折叠到终端；3,498 入索引，184 正确跳过），search.js 渲染「AC → 护甲」。

**P1-P2**
- [x] CF2 短期：wiki_native.css 删两段 404 HTML 假内容（~50KB；site.styles 层从未被抓到——中期需浏览器重抓，见遗留）。
- [x] CF3 .monster-portrait 约束（CF1 恢复肖像后防 711-1000px 撑爆版面）；CF5 Tailwind 任意值类回填（my-[1em]/max-w-[350px]/text-[18px] 等）+ 主控补 .text-[#004416] 暗黑覆盖；CF6 cite 参考文献双栏；CF7 .statblock-仪式 色条；CF4 enlink/img-fullwidth/disambigpage 尽力回填。
- [x] INT-4 mw-customtoggle 处理器 + 无 content 包裹 div.mw-collapsible + mw-collapsed 初始折叠态（规则索引 等 8 页）；INT-2 wikitable_sort 组小标题行（th-only）检测跳过。
- [x] SRCH-2 ns3500 数据页独立类型+降权（'AC' top50 中 46 条数据页污染）；SRCH-3 索引正文窗口跳过 规则导航 模板（87 规则页正文未被索引）；SRCH-4 英文原名权重（Fireball→火球术）；SRCH-5 Latin 词边界（AC 不再命中 Sack/Tack）；SRCH-6 英文前缀扩展恒触发（fire→fireball）；SRCH-7 50 条上限→加载更多；SRCH-8 排序热度 tiebreaker 修正。
- [x] VF2 特征 chip 内链接白字（主控加强：dark 态 (0,5,2) 特异性压过 body.dark a.mw-redirect:link !important）；VF3 statblock 红冠头补 span.line 直挂变体（~4,200 页）；VF4 暗黑内联样式族兜底（纯蓝评级字 1,481 页/奶油底浮窗/深绿字 [style*=] 选择器）；VF5 README .well 暗黑边框。
- [x] LINK-2 safe_title NTFS 大小写碰撞消歧（~sha1[:6] 后缀，3 组；render 与链接两侧一致）；LINK-3 226 个 action=edit/history 死链剥离为纯文本。
- [x] 完备性批评者确认-1：**随机页面**（root random.html 从搜索索引抽 ns0 文章 24,862 池 + sidebar/搜索页入口）；确认-2：**SourceHanSerifCN @font-face local() 别名**（装机有思源宋体/Noto 用户得原观感，回退宋体；真字体捆绑见遗留）。
- [x] 主控收尾：全部构建器资产引用加缓存戳（build_v2 用 {CACHE_VER}，3 个二级构建器 ?v=v2i；style.css 两个改动 import bump ?v=v0330；search.html topnav.js v2d→v2i）——JS 审查实测 WebView2 启发式缓存命中旧 JS 的根治；CACHE_VER v2h→v2i；search.html 内联 topnav 从新 topnav_sub.html 派生重嵌（脱漂移）。

**否决/备案**（详见 V0330_AUDIT_SPECS.md）：INT-3 smw 工具提示（wiki 固有 display:none）；LINK-1 browse-letters 88 死链（已被存在性守卫自愈，现状 0）；LINK-4 7 个特殊字符标题（语料本身没有，非映射缺陷）；LINK-5/VF6 核验通过项备案。

## 重建与验证

- 重建顺序：build_v2.py --redirects → build_browse_v2 → build_browse_letters_v2 → build_search_v2 → build_nav_stubs → build_class_hubs_v2（RC2 要求 class hubs 也重嵌 topnav）。日志 `src-tauri/_v0330_rebuild.log`。
- [x] 重建完成：37,097 页 0 fail；RC3 5,017 桩全转跳（0 kept static）；RC4 blob=194/synth=424/self=704 跳转桩/sweep 617 孤儿/browse 剔 618；RC7 3,610 stub、覆盖 99.93%；搜索 +3,498 别名/剔 5,017 桩/12,881 英文名；27/27 职业。
- [x] RC1 验证：6,000 页抽样受害锚点 = 0；长剑.html 的 武器 链接 → pages/ ✓（验证脚本 `_v0330_verify_static.py`）
- [x] CF1 验证：3,000 页抽样 5,629 个 img 标签分布 1,778 页（链接式图片恢复）
- [x] RC7 验证：全站 4,318 个跳转桩（含 RC3/RC4 桩）stub→stub 链 = 0、自指 = 0
- [x] 死链扫描：1.19%（51,809/4.35M，`_v0330_deadlink_full.py`）vs 基准 0.92%（51,610/5.58M）——绝对数 +199 全为口径差（本扫描含 classes/ 等且不计 #fragment 锚）；归因（`_v0330_deadlink_triage.py`）：top 25 全部 meta=None 的 wiki 固有红链（万寿/帕迪沙帝国/Paizo Inc…），「出版物」364 条实为 title="模板:出版物" 的 ns10 模板红链（基线同类）；**RC4 清理零损伤：category/ 死链仅 11 锚点**。
- [x] Playwright 实测（http.server + WebView 同源 Chromium）：INT-1 战士.html 折叠表 1→21→1 行往返、标题行恒可见；INT-4 规则索引 25 个 mw-collapsed 初始折叠+customtoggle 点击 none→block；RC6-C 原版首页三栏 grid 成型+3 个 huiji 死 embed 全隐藏；RC5 .flex 计算值 flex；搜索 AC→护甲/Fireball→火球术/治疗药水（前排无桩）/fire→231 条前缀扩展+加载更多；random.html 跳真条目（池 24,862 仅文章）；index.html 原版首页入口×3+4 工具外链+塔-巴丰+随机页面 全在；VF2 暗黑 chip 链接 rgb(255,255,255)。
- [x] 验证期间补修 2 项：**搜索「最佳匹配」横幅**（类型分组固定顺序会把 score≥900 的精确命中埋在大组下面——AC 曾被 7 个强酸法术压住；search.js renderResults + search.html CSS）；**topnav 面板视口限高**（装备菜单 18 项在 600px 视口溢出 49px → .topnav-panel max-height:calc(100vh-72px)+overflow-y:auto，topnav.css?v=v0330）。
- [ ] 110 个 RC1 翻转键逐一存在性核对（已知 1 例：酸液（特征） 无 pages html→成红链，忠实；死链归因未见其他异常，低优先）

## 遗留（延后，按优先级）

1. **CF2 中期**：fetch_native_styles_v2.py 加 404 守卫 + 单独抓 site.styles/ext.cite/Tailwind loader CSS（需 .browser-profile 过 CF，勿并行）。抓到后用真值替换 CF3/CF4/CF5 的近似回填。
2. SourceHanSerifCN 真字体捆绑（woff2 子集化，~1,002 页装饰标题；现为 local() 别名）。
3. random.html 轻量化（现加载 19.9MB titles.js；可构建期生成仅 href 清单 ~1MB）。
4. RC3 可选增强：480 个变体名不被父页覆盖的桩 → 父页别名条目（现整体剔除，变体名直搜召回损失）。
5. SRCH 别名条目计入 manifest n_pages（搜索页标题计数虚高 3,498）。
6. INT-2 可选：组内分段排序（现检测即禁排）。
7. 最近更改/链入页面（WhatLinksHere）未实现——离线快照语义价值有限，未立项。
8. topnav 装备菜单 16 项短视口溢出风险（RC2 Risk 6）——重建后实测，必要时给 .topnav-panel 加 max-height+滚动。

## 日志
- 2026-06-10 | 审计工作流 42 agents 完成（2.37M tokens/982 工具调用/56 分钟）：RC1-RC7 全部 present/partial 确认 + 27 条新发现 confirmed（3 P0）+ 3 否决。
- 2026-06-10 | 实施工作流 10 agents 完成（1.17M tokens）：build/search/js/nav 批准，css 审查 1 major（VF2 特异性）。
- 2026-06-10 | 主控收尾 12 项整合完成；全量重建启动（后台）。
- 2026-06-11 | 重建 0 fail；静态+死链+Playwright 验证全过；补修 最佳匹配横幅 + topnav 限高。源码 commit f28539e。
- 2026-06-11 | **用户全部授权 → v0.3.30 已发布**：push f28539e + 8b28af8；release.ps1 -PrevVer v0.3.29 -NewVer v0.3.30（无 -RebuildExe，复用 exe）。补丁 275.58MB（+18/~43,728/-617——topnav+缓存戳重烤全站所致，同 v0.3.25 先例；下次纯内容补丁恢复小）。资产：portable.zip 1.33GB + 补丁 + patches.json（latest=v0.3.30，链 v0.3.29→v0.3.30 ✓）。打包前清理 _wiki_full_v2 内 .playwright-mcp/ 与 _audit_resolve.txt（历史发布无此杂物，本批新混入）。**下次补丁基准 = 干净 pf2-wiki-offline_0.3.30_x64-portable（勿覆盖）**；旧 folder/zip 已按惯例清理。
