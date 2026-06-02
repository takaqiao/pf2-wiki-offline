# v0.3.27 UI/UX 重做进度账本

> 用户 2026-06-02 选「全部实现 P1→P3」(基于 WIKI_UXUI_RESEARCH.md)。分阶段做,每块 commit,关键里程碑截图验证,最后全量重建+打包(发版单独授权)。
> 设计方向:一个声音(令牌)· 一套分类(权威标签)· 一个招牌组件(statblock)。基准=干净 pf2-wiki-offline_0.3.26_x64-portable。
> 批判者已纠正的事实(务必遵守):pf2_theme.css 未加载(statblock 改针对 span.name,勿引它);版权剥离只动 .well.quote-success/.quote-primary,**勿动裸 .well**;标题 ID 在 span.mw-headline;lightbox zoom 光标已有;--fg-mute 明暗都不达 AA;index.html topnav 内联(标签改动要同步 topnav_sub.html + index.html + 重建 browse)。

## Phase 1 — 基础(令牌 + 速赢)
- [x] P1a 设计令牌 _v2_palette.css:字号阶梯 --fs-*/--lh-*/--fw-*、间距 --sp-*、圆角 --r-*、阴影/elevation、强调 ramp(--accent-700/600)+ tint 面(--surface-accent via color-mix)、暖化边框(#ddd→#e7e3dd)、--fg-mute 提 AA(明 #6a6a6a/暗 #a0a0a0)、字体 CJK 优先、--font-display 复用衬线;修两处硬编码字号(palette:118 + _v2_compat body)→ var(--fs-md);暗色模式修复(更宽亮度阶 + 暖珊瑚强调同 #6d2002 色系 + 可见阴影)。
- [x] P1b 版权样板剥离:build_search_v2 iter_parsed 剥 .well.quote-success/.quote-primary + "此数据的文档…" 前导(摘要+索引);_v2_compat.css 降权内容页开头版权框(.mw-parser-output>div.well.quote-success:first-child)。
- [x] P1c 权威标签:怪物→生物、祖先→族裔、戴持物品→穿戴物品、状态→状况(topnav_sub/sidebar_sub/index.html/build_browse BUCKET_LABELS/build_nav_stubs/search.js TYPE_INFO)。
- [x] P1d 无障碍/交互底线:全局 :focus-visible(:where() 0 特异性,暗色金)+ 全局 prefers-reduced-motion(_fmt_mobile.css)+ 更新横幅 z-index/role=status + 共享 pf2Toast/aria-live + _components.css(.card/.section-h/.chip/.badge)+ per-kind 调色入 _v2_palette。

## Phase 2 — 四大核心页面
- [ ] P2a statblock(_v2_compat.css 针对 span.name + .statblock b):红头带+金线+粗标签+特征 chip+分隔线;正文行宽 ~74ch。
- [ ] P2b 内容页左栏→this-page rail(去 7 个导航组,留 home+search+bookmark+recent;保留右栏 TOC)。
- [ ] P2c 首页:英雄区纳搜索+onboarding;四网格→图标分类卡(inline SVG sprite,非 pf2icon.ttf);精简左栏(删重复分类链接);recent/bookmark 小组件;统计条收紧。
- [ ] P2d browse:杀 类型 列;按桶取 Data 字段做列(feats 等级/特征/来源;spells 环级/根源;creatures 等级/体型/稀有度;items 物品分类/稀有度/价格);稀有度/特征/体型 chip;facet 过滤(filter.js 已有);browse-all/CJK → type+letter 矩阵 hub;sticky 表头。
- [ ] P2e search:摘要锚定查询词+<mark>;per-result meta strip;键盘导航 ↑↓/Enter/Esc;recent searches;空状态;整行可点。
- [ ] P2f IA:收 规则 杂菜单、提 出版物 顶级、分类页面 入页脚;de-stub source/index.html。

## Phase 3 — 打磨
- [ ] P3 bookmarks.html 页+★入口、快捷键帮助(?)、回到顶部+阅读进度、标题锚点复制、lightbox caption+不点图关闭、移动抽屉(Esc/inert/aria/resize)、焦点陷阱、section-header 左 tick 改造、callout 协调、tooltip 淡出。

## 决策记录 / 日志
- 2026-06-02 | 建账本。
- 2026-06-02 | **P1 全部 DONE + 验证**:令牌系统(字号/间距/圆角/阴影/accent ramp/暖边框/fg-mute AA/CJK字体/暗色修复-暖珊瑚)、版权样板剥离(索引 社区使用政策 14948→1)、权威标签(生物/族裔/穿戴物品 全站传播)、a11y 底线(focus-visible/reduced-motion/_components.css/pf2Toast/更新横幅移底部)。截图验证暗色暖调+许可框受抑+标签正确。下一步:P2a statblock。
