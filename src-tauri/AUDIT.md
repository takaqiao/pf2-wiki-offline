# PF2 离线百科 — 全方位体检 (post v0.3.22)

> 目标：从 0–100 扫描整个流程链 + 程序本身，所有方向（逻辑 bug / 格式 / CSS 表现 / 安全 / 构建 / 发版 / 内容）找问题，列出 → 逐步解决。
> 方法：只读并行 agents 分域检测 → 汇总本表 → 按独立性并行修复。
> 严重度：**P0** 崩溃/数据错误/安全 · **P1** 功能失效/明显错误 · **P2** 体验/表现 · **P3** 清理/打磨。
> 状态：`TODO` / `FIXING` / `DONE` / `WONTFIX(原因)`。

## 域划分（检测 agents）

| # | 域 | 范围 | agent 状态 |
|---|---|---|---|
| D1 | Rust 后端 | main.rs：tiny_http、路径穿越/解码安全、MIME、缓存头、端口、资源定位、apply_incremental_update(下载/校验/解压/ps1)、panic/错误处理 | pending |
| D2 | 构建管线 (Py) | build_v2.py / build_browse_v2.py / build_class_hubs_v2.py / build_browse_letters_v2.py / build_patch.py：确定性、编码、边界 | pending |
| D3 | 前端交互 JS | keybindings / wikitable_sort / wikitable_paginate / mw_collapsible / image_lightbox / bookmark / filter / aon_table / huiji_tt：逻辑/事件/边界 | pending |
| D4 | CSS / 表现 | _v2_compat / _fmt_* / palettes / layout / overflow / infobox / creature / breadcrumb / filter：暗黑对比、移动端、溢出、层级 | pending |
| D5 | 生成 HTML | 抽样各类页面：结构、UTF-8 编码、内链死链、meta-refresh 重定向、404、navbox/statblock/TOC 布局 | pending |
| D6 | 内容/数据 | data 页、分类反向索引、法术列表、redirect 双闪、29 缺失 trait 页 | pending |
| D7 | 发版/更新管线 | release.ps1 / update_content.ps1 / patches.json 链 / AUTOMATION.md 一致性 | pending |

---

## 发现 (FINDINGS)

> 8 个只读 agent 扫出 ~75 条原始发现。逐条批判性核实后：真正值得修 4 条、可选缓办 3 条、其余驳回（噪音/已处理/按设计/误判）。

### A. 待修 (ACCEPTED)

#### [P2][D1] serve_static 路径穿越加固 — TODO
- file: `src-tauri/src/main.rs:75-77`（`root.join(&path[1..])`）
- 证据: Windows 上 URL `/C:/Windows/...` → path[1..]=`C:/Windows/...` 是绝对路径，`PathBuf::join` 会**丢弃 root** → 逃出 `_wiki_full_v2/`。`..` 检查不拦此情形；符号链接同理。**真实但低危**（服务仅监听 127.0.0.1，只加载可信静态内容，无未信任输入）。
- 修复: 拼接后 `std::fs::canonicalize(&full)` 并校验 `starts_with(canonicalize(root))`，否则 403。一并挡住符号链接逃逸。
- 注: agent 报的 `%252e%252e` 双解码穿越是**误报**（decode 只一次，`%2e` 不会再被 PathBuf 解成 `.`）。

#### [P2][D1] open_external scheme 白名单 — TODO
- file: `src-tauri/src/main.rs:148-151`
- 证据: `open::that(&url)` 不限 scheme，恶意页面可 invoke `open_external('file:///...')` 等。低危（可信内容）但应加固。
- 修复: 仅放行 `http://` / `https://`，否则返回 Err。

#### [P2][D7] release.ps1 缺 prevDir 有效性校验 — TODO
- file: `src-tauri/release.ps1:24,50`
- 证据: 直接拿 `$prevDir` 做 diff 基准，不校验其存在/未被改动。**本次发版已踩坑**（旧 portable 文件夹被诊断覆盖 → 若按原流程会产出错误补丁）。
- 修复: build_patch 前校验 `$prevDir` 存在；加注释提醒「prevDir 必须是干净的上一发布版」。

#### [P3][D7] 文档过时引用已删 updater — TODO
- file: 备份 repo `README.md`(CI 段提 NSIS/wiki-data.zip)、`AUTOMATION.md`
- 证据: 代码已切 portable-only + 客户端驱动更新，文档仍描述旧 NSIS/updater 流程，误导。
- 修复: 更新 README CI 段 + AUTOMATION 说明「CI 仅验证编译，发版靠本地 release.ps1；更新为客户端 patches.json 驱动，无 latest.json/签名」。

### B. 可选缓办 (DEFERRED, 低价值)

- [P3][D2] build_v2.py rglob 加 `sorted()`：纯防御性确定性，**输出已由 render 期 sort 保证确定**（line 553），实际无影响。零风险可顺手加。
- [P3][D4] 暗黑 `.well` 边框偏灰（已知）：`_v2_compat.css:998` 可补 `border-color`。纯装饰。
- [P3][D4] updater banner `z-index:99999` 偏高（updater_ui.js）：可降到 ~120。仅更新可用时短暂出现，不影响功能。

### C. 驳回 (REJECTED — 核实为非问题)

- [D1] `%252e%252e` 双解码穿越：误报，decode 只一次。
- [D1] 补丁顺序/XSS 注入、800MB OOM、pick_free_port TOCTOU：均为假设/极罕见，patches 仅 ~5MB；不值得。
- [D2] 「Windows 下 `new_dir / path` 斜杠拼接坏」：误报，pathlib 在 Win 上 `/` 也是分隔符；且 v0.3.18→0.3.21 补丁链历史可用反证。
- [D3a/D3b] 表格/lightbox/bookmark/filter 的多数项：边界已被优雅处理、单窗口 app 的多标签同步、英文目录假设不影响 ASCII 的 URL 结构等——niche P3，不值当。
- [D4] keybind modal 暗黑「缺 override」：误报，`_v2_compat.css:1645-1657` 已有完整 dark 规则（title 是金色 #ffcc66）。palette 分层：功能正常（末位生效）。
- [D5] 「数百死链」：wiki 红链（上游本无的页面），离线镜像忠实再现，正常。编码/结构/wikitext 残留全部通过 ✓。
- [D6] 内容完整性：全部通过（`[[`/`{{` 仅存于 meta description，非渲染体）；0 损坏 / 重定向有效 ✓。
- [D7] [P0]「patches.json 链断 v0.3.21→v0.3.22」：**按设计**（option B，坏的 v0.3.21 无法应用任何补丁），客户端正确回退「下载完整版」。

---

## 已知/已修（本会话先前）
- ✅ ACL origin 根因（capability remote.urls）— v0.3.22 已修已发
- ✅ B：update.ps1 UTF-8 BOM — 已修
- ✅ C：更新检测改 patches.json + 节流 — 已修
- ✅ 清理标准 updater 脚手架 — 已删
- ⏳ 已知遗留 P2：redirect 双闪(23 条,终点正确)；README 暗黑 `.well` 边框灰
- ⛔ 无法修：29 个 niche 怪物「特征」页（上游 SMW 查询失效）
