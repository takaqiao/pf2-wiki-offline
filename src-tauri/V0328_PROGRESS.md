# v0.3.28 — 类目对齐 + 延后打磨/BUG 进度账本

> 用户 2026-06-02:① 类目和 wiki 对不齐(出版物例)修复 ② 之前延后的小打磨 ③ 之前延后的 BUG。
> 基准 = 干净 pf2-wiki-offline_0.3.27_x64-portable。发版单独授权。

## ① 类目对齐(用户explicit:出版物)
- [x] **出版物**:nav 8 处 source/index.html(我们的 14-book 桩)→ 真实 `pages/出版物索引.html`(112KB,wiki 真页);source/index.html 改为重定向到 出版物索引(build_class_hubs)。
- [x] **职业 hub**:classes/index.html 是有价值的 27 职业一览(非桩),保留 + 顶部加「阅读完整《职业》词条」链到真 pages/职业.html。
- [x] **全 nav 目标审计**(`nav_target_audit.py`):除上述两个合成 hub,其余 home/topnav/sidebar 目标全部解析为真实文章(20-426KB)或正确重定向桩(组织→派系/信仰→信仰综述/译名表→术语索引,忠实镜像 wiki 重定向)。**对不齐面=仅 出版物**(已修)。

## ② 延后打磨(P3 小批)
- [x] 搜索结果键盘导航(↑↓/Enter/Esc + roving active row)search.js。
- [x] lightbox:图注 caption + 点图不关闭(只背景/按钮关)image_lightbox.js。
- [x] 移动抽屉 a11y(Esc 关闭汉堡抽屉;桌面 app 移动权重低,做轻量版):Esc 关 + aria-expanded + resize 反应 mw_collapsible.js。
- [x] 快捷键帮助浮层(? 键已有 cheat-sheet;加可见 ? 按钮到 topnav+search,index 补 keybindings.js)(? 触发,列 Ctrl+K/T/B 等)keybindings.js。
- [—] topnav 菜单栏重构(提 出版物 顶级):出版物已改指真页→菜单栏现合理,**判定无需重构**,跳过。

## ③ 延后 BUG
- [x] browse-all 性能:25k 行/5.3MB 单表 → 改为「按类型 + 字母」hub(复用已有 browse-{letter}/{bucket} 页),消除 5.3MB DOM。低风险高值。
- [x] scraper 退避重试(fetch_parse 429/5xx 有界退避+Retry-After;403 仍抛=cookies 需重热)(dump_parsed 429/5xx backoff)— 廉价robust。
- [—] **判定保留延后(高风险/低 ROI,本地 app)**:wiki_native PurgeCSS(390KB 本地磁盘无碍,改有破样式风险)、补丁签名 PKI(大基建)、topnav 客户端注入(高风险架构重构)、scraper revid 全量改动跟踪。→ 向用户说明,征询是否坚持做。

## 状态
全部重建+验证:0 死链、出版物→真页(战士 topnav 已指 出版物索引)、? 帮助按钮全站、browse-all hub 17.7KB、orphans 28514。**内容-only,复用 v0.3.26 exe,无 -RebuildExe**。待用户授权打包 v0.3.28。

## 日志
- 2026-06-02 | 建账本;① 出版物对齐 + 职业 enrich + nav 审计(对不齐面=仅出版物)。下一步:② 打磨 + ③ browse-all hub/backoff。
