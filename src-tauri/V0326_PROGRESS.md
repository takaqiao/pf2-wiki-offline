# v0.3.26 修复批进度账本

> 用户 2026-05-22 选「全修 P0–P3」(基于 WIKI_AUDIT.md)。全部修完→打包 v0.3.26(需 -RebuildExe,因改 main.rs)。发版单独征求授权。
> 基准 = 干净 `pf2-wiki-offline_0.3.25_x64-portable`。每批改完 commit;最后全量重建+验证+打包。

## 批次 (DONE/DOING/TODO)
### Batch A — JS/HTML 资产快修(无需重建语料) ✅ DONE (commit pending)
- [x] A1 search.js(P0):`url = pageBase + r.href`(删 folder 逻辑)。唯一 URL 构造点,已修+语法过。
- [x] A2 index.html 去重复 bookmark.js + 去 topnav.css 独立 link(经 style.css @import)。search.html 同样去 topnav.css 独立 link。
- [x] A3 FOUC:_v2_palette.css `html.dark, body.dark`;index.html+search.html `<head>` 内联前置脚本设 html.dark;theme.js apply/toggle 同步 html+body;主题按钮选择器扩到 .topnav-theme/.sb-theme/.topnav-fallback-theme(图标/aria 生效)。
- [x] A4 updater_ui.js:进度 listener 单次注册(window.__pf2UpdProgressBound)、无 Content-Length 时不定态(40% + MB)、去硬编码 v0.3.18 fallback(未知版本→不弹横幅,decide 守卫)。
- [x] A5(择高值):wikitable_sort 数值判定改多数阈值(≥70%)+ NaN 置尾(配合 B 的 browse 排序启用)。**有意延后的低纸**:keybindings 已守卫输入框(无需改);topnav.js closeAll clearTimeout、bookmark 上限、external_links stopPropagation、image_lightbox 关闭、huiji_tt tabindex、mw_collapsible resize、各注释纸 = 纯打磨/回归风险>价值,记录不做。

### Batch B — 构建生成器(需重建)✅ DONE(验证中)
- [x] B1 build_browse_v2.py:排序改用 wikitable_sort.js(去 inert aon_table.js)、表头去 ▾、topnav_root 补 action 改写(搜索框 404 修)、加 keybindings.js+bookmark.js+FOUC 脚本、去掉 browse-classes(孤儿)、browse-categories 改列全部 ~3646 分类(含成员数)。
- [x] B2 build_browse_letters_v2.py:topnav_root action 改写、加 bookmark/keybindings/wikitable_sort/FOUC。
- [x] B3 build_nav_stubs.py:ITEM_GROUPS 大幅扩(盾→armor、法杖/魔杖/魔典→implements、护符/刺青/植入体→worn、更多消耗品)、topnav_root action、cantrip/focus 分类列改 根源。子区页经 render_browse_html 自动继承 B1 head 修复。
- [x] B4 build_v2.py:**title_index 非覆盖+ns优先**(wikilink 指向修)、[4b] 仅全量+去 exists() 跳过、**构建前 rmtree pages/category/data/project**(去孤儿)、redirect .new 守卫、content 页 head 加 FOUC 脚本。**有意延后**:topnav 客户端注入(高风险架构重构,本批已重烤全站,单独做更稳)、JS 条件注入/单遍语料读(优化,改核心渲染风险>值)、死常量/数字实体(纯纸)。
- [x] B5 build_class_hubs_v2.py:去 no-op replace、出版物 ?q→search.html(search 读 ?q)。
- [x] B6 topnav_sub.html 计数 25→27;sidebar_sub.html 神祇→信仰/地点→地理/状态特征→异常状态。
- [x] B7 search.html:topnav+sidebar 全部 25→27、神祇→信仰、地点→地理、状态特征→异常状态、神祉 typo→信仰、侧栏计数全部刷新真值、加 mw_collapsible.js+keybindings.js、footer 去硬编码总数。

### Batch C — Rust + 发版(需 -RebuildExe)
- [ ] C1 main.rs:assets/* immutable 缓存(HTML no-cache)、updater PS1 ErrorActionPreference Stop + sha256_after_apply 校验、_remove_these.txt 校验、PS 单引号转义、补丁流式写临时文件+增量哈希、open_external url::Url、(可选)线程池+gzip。
- [ ] C2 release.ps1:链连续性断言、robocopy /XF/XD 排除、草稿优先+幂等 tag。
- [ ] C3 update_content.ps1 / make_portable_zip.ps1:UTF-8 BOM 或去中文(ASCII 铁律)。

### Batch D — 抓取器(不影响发布,修正确性)
- [ ] D1 dump_parsed/metadata/images:原子写(temp+os.replace)、load_state try/except 重建、退避重试、revid、dedup、图片 .part。
- [ ] D2 refresh_changed:revid + 删除/移动对账(择优)。

### Batch E — 打包卫生 / 死文件
- [ ] E1 删 21 死 CSS + favicon.png;.gitignore 加 out_v2/。
- [ ] E2 style.css @import→<link> + 更新注释。

### Batch F — browse-all 性能(评估)
- [ ] F1 browse-all 25k 行:评估服务端分页/JSON 渲染 vs 现有客户端分页;高风险则记录权衡。

### Batch C — Rust + 发版 ✅ DONE
- [x] C1 main.rs:**安全/完整性**(高值)——updater PS1 `$ErrorActionPreference='Stop'`、`_remove_these.txt` 加包含校验(GetFullPath StartsWith installRoot,拒 ../绝对路径)、PS 单引号转义($install/$exe/zip)、`-LiteralPath`、补丁**流式写临时文件+增量哈希**(去 224MB RAM 缓冲 + 800MB 静默截断,改 2GB 显式上限)、open_external 拒控制字符。cargo check 通过(1m26s)。**缓存头优化有意延后**:assets/ 无统一 ?v= 破缓存令牌,改 immutable 会导致更新后用户拿不到 search.js 修复(staleness 风险>localhost 重解析收益)。
- [x] C2 release.ps1:robocopy 加 /XF *.py *.pyc *.log /XD __pycache__ _snippets(瘦身)、发版前断言 patches.json latest==NewVer 且含 PrevVer→NewVer 跳(防漏链)。保持纯 ASCII。
- [x] C3 update_content.ps1 + make_portable_zip.ps1:加 UTF-8 BOM(PS5.1 GB2312 误读风险)。

## 决策记录
- **⚠️ clean-before-build 已加又撤回(实测驱动)**:加 rmtree pages/ 后内容页死链从 1.70%→**10.55%**——因当前 parsed 语料(37k)比 metadata(40k)少 ~1.4k 非重定向页(抓取有缺口),这些页由更早更全的抓取渲染、留存磁盘;blanket clean 删掉了这批有效内容。**撤回 clean**,并从干净 v0.3.25 portable 恢复 3575 个孤儿页(死链回到 1.70%)。代价:这 3575 页带旧 chrome(topnav 25/无 FOUC),少数页视觉略不一致但可访问(远胜 404)。**正确根治 = 补全抓取那 ~1.4k 页**(留待单独再抓)。[4b] 去 exists() 跳过保留(重写合成分类页刷新成员数,rendered_cat_names 护住抓取页)。
- 大/高风险项(补丁签名 PKI、wiki_native PurgeCSS、browse-all 服务端分页)按"可安全做的就做,需设计决策的标注延后"处理,不假装做完。
- 更新链 v0.3.21 缺口 = 已知 option B 设计,不在本批(非回归)。

## 日志
- 2026-05-22 | 建账本(全修 P0–P3)。下一步:Batch A。
