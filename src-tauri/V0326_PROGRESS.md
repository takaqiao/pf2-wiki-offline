# v0.3.26 修复批进度账本  —  🎉 已发布 (2026-05-22)

**v0.3.26 已发布**:release.ps1 -RebuildExe(cargo 1m16s)。补丁 v0.3.25→v0.3.26 = **231.19MB**(~40456 改/-42 删[死CSS+_snippets+.py+browse-classes];FOUC+topnav 改全站故大)。tag+3 资产(portable 1236.7MB/patch 231.2MB/patches.json)+ repo commit 91aaa5f + latest=v0.3.26。**新加的链连续性 preflight 实跑通过**。**acl_probe 全绿**(open_external RESOLVED/apply 可达/eventListen OK——硬化 updater+流式下载验证可用)。下次补丁基准=干净 pf2-wiki-offline_0.3.26_x64-portable。



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

### Batch D — 抓取器(不影响发布,修正确性)✅ 核心 DONE
- [x] D1 dump_parsed_v2_concurrent.py:load_state try/except + 损坏时从磁盘 parsed 重建 done-set;_state.json 原子写(temp+os.replace);页面 JSON 原子写(temp+os.replace);补 `import os`。**有意延后**(scraper 一直能用,低值):dump_metadata dedup、dump_images .part、429/5xx 退避重试、revid 跟踪。
- [—] D2 refresh_changed revid:延后(同上)。

### Batch E — 打包卫生 / 死文件 ✅ DONE
- [x] E1 删 20 个死 CSS(31→11,含 style.bundled 96K;实测无任何页引用,含恢复的孤儿页)+ favicon.png(未引用);offline repo git rm 21 项。working assets 加载链完整(style.css+8 @import+search_polish 全在)。
- [x] E2 out_v2/ 已在 offline repo .gitignore(cookies.json 已 IGNORED,无需改);style.css "4-file" 注释纸延后(纯纸)。

### Batch F — browse-all 性能(评估)
- [—] F1 **延后(记录权衡)**:browse-all 25k 行/5.3MB。现已有 wikitable_paginate 客户端分页(限可见行),残留是 5.3MB 初始解析。服务端分页/JSON 渲染=高工作量+改 browse 架构风险,价值(localhost 一次性解析)有限 → 延后,留作单独优化。browse-CJK 近重复同理延后。

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
- 2026-05-22 | **全部 A–E DONE**(F 延后),commit 83243fd(A)/efb1502(B+C)/7c44add(D+E)。clean-before-build 加后实测死链 1.7%→10.5% 已撤回+恢复孤儿。**最终重建+验证全绿**:browse 0 死链、搜索结果 0/300 死(P0 修复实证)、内容死链 1.70%、pages 28514/category 3646/browse 51/css 31→11、fresh 页 topnav 27+FOUC+排序就位。cargo check 通过。**待用户授权打包 v0.3.26(需 -RebuildExe)**。
- 待办(本批延后,记录):browse-all 服务端分页、scraper 退避/revid、wiki_native PurgeCSS、补丁签名 PKI、topnav 客户端注入。
- 2026-05-22(收尾) | **用户选「先补齐抓取缺口再发」→ 调查发现缺口=0**:`fetch_missing.py` + 直接核对——**37068/37068 非重定向 WANTED_NS 页全部已 parsed,无可抓缺口**(我此前"~1.4k 缺口"的说法是错的:metadata-parsed 的算术差不对应实际缺失 pageid)。`diag_deadlinks.py` 实测内容死链构成:**391/395 = not_in_meta(当前 wiki 根本没有该标题=真红链,live wiki 上也是红链,正确镜像)**,0 redirect,1 safe_title 边角(分类:出版物),3 = 实为 redirect(属 [5/5] 的 3 个 unresolved)。结论:**语料已完整,1.70% 死链是 wiki 固有红链 + 保留的上游已删页(孤儿,满足内链优于 404),无可补**。建 fetch_missing.py/diag_deadlinks.py/deadcheck.py。→ 回报用户:无缺口可补,可直接打包。
