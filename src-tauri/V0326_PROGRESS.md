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

### Batch B — 构建生成器(需重建)
- [ ] B1 build_browse_v2.py:th sortable、search-box action、aon_table.css 链、keybindings.js、browse-classes 去掉、browse-categories 用全 keys。
- [ ] B2 build_browse_letters_v2.py:search-box action、bookmark.js、keybindings.js。
- [ ] B3 build_nav_stubs.py:search-box action、ITEM_GROUPS 扩 + other 兜底、cantrip/focus 分类列标签。
- [ ] B4 build_v2.py:title_index 非覆盖+ns优先、[4b] 去 exists() 跳过 + 仅全量、redirect .new 守卫、构建前清理、**topnav 客户端注入**、JS 条件注入、单遍语料读、死常量、meta 数字实体、safe_title 冲突哈希、fragment quote。
- [ ] B5 build_class_hubs_v2.py:去 no-op replace、source ?q→search.html。
- [ ] B6 topnav_sub.html + sidebar_sub.html:标签+计数单一来源(25→27、信仰/地理/异常状态);配合 B4 客户端注入做共享片段。
- [ ] B7 search.html:重生成 root topnav(信仰/地理/异常状态/27)+ 侧栏计数 + mw_collapsible.js + 神祉 typo。

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

## 决策记录
- 大/高风险项(补丁签名 PKI、wiki_native PurgeCSS、browse-all 服务端分页)按"可安全做的就做,需设计决策的标注延后"处理,不假装做完。
- 更新链 v0.3.21 缺口 = 已知 option B 设计,不在本批(非回归)。

## 日志
- 2026-05-22 | 建账本(全修 P0–P3)。下一步:Batch A。
