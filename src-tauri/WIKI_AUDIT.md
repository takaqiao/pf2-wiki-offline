# PF2 离线百科 — 全面审计报告 (2026-05-22, 截至 v0.3.25)

> 方法:11 维度多 agent 审计(135 agents / 123 findings / 119 通过对抗验证 / 4 驳回)。
> 下列 P0/部分 P1 由我**亲自复核实锤**(读真实代码+磁盘产物),其余为 agent 对抗验证结果。
> 这是研究/审计交付物;修复需用户授权(改完要重打包发版)。

## 我已亲自实锤的关键项
- **[P0] 搜索结果 100% 404**(`search.js:585-586` + `:504`):索引里 `h` 已含目录(实测 `"h":"pages/科米翁.html"`、`"h":"data/Spells-Gecko Grip.json.html"`),search.html 传 `pageBase:""`,但 search.js 又拼 `folder + "/" + r.href` → `pages/pages/X.html` / `data/data/X.html` → **每条搜索结果都打不开**。分类结果(h=`category/X.html`)被强行塞进 pages/ 也错。**修复 = 一行**:`const url = pageBase + r.href;`(删掉 folder 逻辑),顺带修好分类结果。
- **[P1] browse 排序完全失效**:browse 表头有 `名称 ▾` + 文案"点表头排序",但 **0 个 `<th>` 带 `class="sortable"`**,且只引了 aon_table.js 没引 wikitable_sort.js → 点表头无反应(全 52 个 browse 页,含 25k 行 browse-all)。
- **[P1] browse 搜索框 404**:browse/letters/nav_stub 页的 topnav 搜索表单 `action="../search.html"`,但这些页在根目录 → 指向站外 → 404。
- **[P1] aon_table.css 未引入**:52 个 browse 页加载 aon_table.js 却不链 aon_table.css → 过滤栏/排序箭头/特征 pill/列宽全无样式(且该 css 同时是"死文件")。
- **[P2] topnav 计数漂移**:`职业` 计数 content=25 / browse=25 / search=25 / index=27(三处真相)。根因:topnav_sub.html 仍是 25(我之前只改了标签没改计数),search.html 自带过时 root topnav。
- **[P2] 更新链 v0.3.21→v0.3.22 缺口**:确认链在 v0.3.21 断(v0.3.20→v0.3.21 在,但 v0.3.21 无下一跳)。**但这是已知的 option B 设计**(坏掉的 v0.3.21 无法应用任何补丁,故 ≤v0.3.21 用户须手动下完整版一次)——非新回归,记录备查,优先级下调。
- **[P3] index.html 重复引 bookmark.js**(2 次)。

---

## P0 — 关键(立即修)
1. **搜索结果全 404** — `search.js`:`url = pageBase + r.href`(见上)。一行,解锁最常用功能。

## P1 — 高价值
2. **build_v2.py title_index 裸键覆盖**(:856-863):ns=14/4 前缀页覆盖真 ns=0 文章(161 处冲突,如 `《核心规则书》`),导致 `[[wikilink]]` 指向分类列表而非文章 → 改为非覆盖 + ns 优先(0/102 'pages' 优先于 14/4 'category')。
3. **browse 排序失效** — build_browse_v2.py 给表头 `<th>` 加 `class="sortable"`(并确认 aon_table.js/wikitable_sort.js 生效)。
4. **browse 搜索框 404** — build_browse_v2.py:201 / build_browse_letters_v2.py:139 / build_nav_stubs.py:164:`action="../search.html"` → `action="search.html"`(root 变体不该带 `../`)。
5. **aon_table.css 未链** — 给 browse 页加 `<link aon_table.css>`(顺带消除该死 css)。
6. **物品子区漏掉约一半物品** — build_nav_stubs.py ITEM_GROUPS(:57-66)缺盾牌/法杖法仗/护符/冒险道具/纹身/植入体 → 扩充分组,或加 `other = 父桶 − 已映射` 兜底子区。
7. **更新 PS1 不校验应用后完整性** — main.rs:343-359:解压循环 `$ErrorActionPreference='Continue'` 且不校验 manifest `sha256_after_apply` → 半解压/被杀软拦截会"静默损坏却重启成功"。改 'Stop' + 重启前校验哈希。
8. **topnav 内联进每页 → 224MB 补丁** — build_v2.py:566/680:topnav 烤进全部 ~28k 页,任何导航改动重烤全站。**改为客户端单文件注入**(topnav.js 拉一个共享片段)→ 导航改动只几 KB,且彻底根治计数/标签漂移。
9. **资产无缓存头** — main.rs:154-164:HTML/CSS/JS 全 no-cache,每次导航重取+重解析 ~580KB(390KB wiki_native.css + 12 JS)。给 `assets/*` 上 immutable 长缓存(已有 ?v= 破缓存),仅 HTML 文档 no-cache。
10. **构建前未清理 + [4b] exists() 跳过** — 一处修三个 bug:合成分类页成员数永久 stale、被删/改名 wiki 页留孤儿 HTML、死 stub 遮蔽 2153 成员的变体（特征）分类。构建前 rmtree pages/ category/ data/ + 去掉 [4b] 的 exists() 跳过。
11. **browse-all 25k 行/5.3MB 单页** — 服务端分页或 JSON+客户端渲染,只让 ~50-500 行进 DOM。browse-CJK(3.4MB)近重复 browse-all,可去重/分块。

## P1 — 安全加固
12. **_remove_these.txt 未校验删除路径** — main.rs PS1:348-351:网络补丁里的删除项 Join-Path 后强删无包含校验,`..`/绝对路径可删安装目录外文件 → Rust 侧拒绝 dot-dot/盘符/前导分隔 + PS 用 `-LiteralPath` + GetFullPath StartsWith。
13. **补丁无签名,url+sha256 同源** — main.rs:295-308:两者都来自未认证 patches.json,篡改可控 → 加补丁签名(内嵌公钥+分离签名)或至少把下载主机 pin 到 github.com。

## P2 — 中等(择优)
- topnav/sidebar 标签+计数单一来源化:25→27,神祇/地点/状态特征→信仰/地理/异常状态(topnav_sub/sidebar_sub/search.html/index.html),由 KNOWN_CLASSES 长度+共享片段驱动。
- search.html 侧栏计数全过时(祖先 16 vs 245、专长 11006 vs 4872、物品 12410 vs 3400、总数 35469 vs 37097)+ `神祉` 错别字 → 重生成或去掉。
- 重定向页 `content="0"` 即时跳转可能跳到不存在的 `.new` 目标(404 无兜底)— render_page_html:619-626 加 title_index 存在性守卫。
- ancestry 桶混入 ~36% feat-hub 页;location 桶混入 ~45% NPC stat/书子页 — 加标题模式二次过滤。
- 出版物索引链向 `browse-all.html?q=...` 但 browse 不读 URL query → 指向 search.html 或给 wikitable_paginate 加 ?q 初始化。
- 抓取器状态写入非原子 + load_state 无 try/except;图片非原子写留半截文件被永久信任 → 临时文件+os.replace,图片下到 .part 校验后改名。
- 抓取器按 pageid 记 done,改动页永不重抓(refresh_changed.py 是 recentchanges 兜底但不覆盖删除/移动/嵌入变化)→ 存 revid + rctype=log/embeddedin 对账。
- 抓取无 429/5xx 退避重试;futures 一次性全提交,abort 后在途请求继续打 CF-403 → 加退避重试 + 分批/cancel_futures。
- update_content.ps1 / make_portable_zip.ps1 含中文且无 BOM → 违反 release.ps1 的纯 ASCII 铁律(PS5.1 按 GB2312 误读)→ 加 UTF-8 BOM 或去中文。
- release.ps1:60-74 写 patches.json 不校验链连续性(就是 v0.3.21 那类 bug)→ 发版前断言链可达 latest。
- release.ps1:70-75 先推 tag 后传资产无回滚 → 草稿优先 + 幂等 tag + 失败清理。
- search.html 移动端侧栏不可达(未引 mw_collapsible.js);主题按钮缺 .theme-toggle 选择器 → theme.js 不更新图标/aria。
- 深色模式 FOUC:theme.js 延迟执行且依赖已删除的 prefers-color-scheme 兜底,且把 dark 加在 <body> 而非 <html> → head 内联渲染前脚本设 class 到 documentElement。
- browse 字母页缺 keybindings.js;letter 页缺 bookmark.js → Ctrl+K/T/?、书签星标静默缺失。
- 焦点陷阱缺失:keybindings/image_lightbox 的 aria-modal 对话框无 focus trap、关闭不还原焦点(WCAG 2.4.3)。
- 触屏平板(>700px)mega-menu 首触开了又关 → matchMedia('(hover:hover)') 门控。

## P2 — 性能
- wiki_native.css 390KB 是 load.php 原始 dump(大量未用 MW/SMW/图标字体)→ PurgeCSS 子集化 + font-display:swap。
- 补丁整体缓冲进内存(224MB)再写,reader 硬限 take(800MB) 会静默截断更大补丁 → 流式写临时文件 + 增量哈希。
- build_v2.py 把 567MB/37k 文件语料 read+json.loads **两遍**(~1.1GB I/O)→ 一遍构建。
- 21 个死 CSS(~270KB 含 style.bundled.css 96KB)、favicon.png(54KB)未引用却随 zip 发 → 删/归档。
- release.ps1 robocopy /MIR 把 .py/__pycache__/_snippets/死 CSS 打进每个 portable 包 → 加 /XF /XD 排除。
- 12 个 JS 无条件每页注入(表格/折叠脚本在多数页空转)→ 按页面是否含 table/.mw-collapsible 条件注入。
- 单线程请求循环 + 无 gzip,每页 ~20 子资源串行 → 有界线程池 + gzip 文本响应。

## P3 — 低/打磨
- index.html 重复引 bookmark.js;topnav.css 双重加载(link + @import);favicon.ico 偏大(52KB)。
- wikitable_sort 列判数值要求每格都能 parse(一个 '—'/中文格就退化为字典序)→ 多数阈值 + NaN 置尾。
- topnav.js mouseleave 关闭定时器 closeAll 不清 → 可能收起刚重开的下拉。
- bookmark.js 无上限 + 静默吞配额错 → 加上限 + 提示。
- 各类 stale 注释、无操作 replace、死常量(APP_VERSION/CACHE_VER)等。
- 详见审计原始 JSON(135 agents 输出)。

## 审计未覆盖/待确认
- 全部为静态代码/文件读取,**无 WebView2 端到端运行验证**(搜索 404、排序失效、FOUC 是推断,虽 P0 我已用磁盘产物+代码双重实锤)。
- 未审 Tauri capability/permission 作用域细节、search 排序相关性质量、3646 合成分类页的成员内容正确性、data/*.html 渲染正确性。
- 多数 a11y/网络延迟类严重度是按"单用户本地 localhost Tauri app"定的;若公开服务则上调。
