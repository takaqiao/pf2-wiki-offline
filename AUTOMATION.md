# 自动化与发布说明

## 目标可行性：每天自动拉取 wiki → diff → patch → build → 发布

| 环节 | 能否全自动 | 在哪跑 | 说明 |
|---|---|---|---|
| 抓取 wiki 更新 | ⚠️ 半自动 | **本地** | huiji 有 Cloudflare。本机 `pf2wiki-scraper/.browser-profile/` 有持久 clearance cookie 可过墙；GitHub Actions 无头环境**过不了 CF**，所以抓取必须在本地。 |
| 比对变化 | ✅ 自动 | 本地 | 不需手工 diff：`build_v2.py` 是**确定性**的，未变页面输出字节级不变，`build_patch.py` 比对 sha256 只把真正变化的页放进补丁。 |
| 重建 HTML | ✅ 自动 | 本地/CI | 纯 Python，可在任意环境。 |
| 编译 exe | ✅ 自动 | 本地/CI | 代码逻辑改动需人工测试（你认可）；纯内容更新复用上一版 exe，不重编。 |
| 出补丁 + 链式 + 发布 | ✅ 自动 | 本地/CI | `build_patch.py` + `gh release`。 |

**结论**：除「抓取」因 Cloudflare 必须在本地外，其余全自动。最实际的方案是**本地一条命令 / 定时任务**，而非 GitHub Actions（CI 过不了 CF，且 1.8 GB 语料不入 git）。

## 内容是否 100%

当前 ns=0 主条目 24,647/24,647 全抓，数据页 wikitext 已渲染，分类页反向索引补全，法术列表按环级合成。**有效内容 ≈ 100%**。唯一缺口是 29 个 niche 怪物「特征」页 —— 这些**上游 wiki 自己的 SMW 查询已失效**（在线访问也是空），非本镜像问题，无法修复。

## 日常操作

### 纯内容更新（wiki 有新页/改动，代码没动）
```powershell
.\src-tauri\update_content.ps1 -PrevVer v0.3.21 -NewVer v0.3.22
```
自动：刷新 CF cookie → 抓 metadata/内容/图（断点续传）→ 重建 → 出 1 个增量补丁 → 追加版本链 → 发布 + 提交。wiki 无变化时补丁仅几十 KB。

可挂到 Windows 计划任务每天跑（需本机已登录、browser-profile 有效）。

### 代码更新（改了 Rust / JS / CSS，需本地编译测试）
```powershell
.\src-tauri\release.ps1 -PrevVer v0.3.21 -NewVer v0.3.22 -RebuildExe
```

## 链式增量更新

`patches.json`（repo 根 + 每个 release）是一条版本链：
```
v0.3.18 → v0.3.19 → v0.3.20 → v0.3.21 → ...
```
- 每版只发 **1 个补丁**（上一版→本版）。
- 客户端从自身版本沿链依次应用所有补丁到最新（落后几版就连打几个小补丁），全自动。
- 客户端读 `raw.githubusercontent.com/.../patches.json`（有 CORS）；补丁 zip 在各自 release。
- **不要删旧 release**——链依赖它们的补丁 zip。

## GitHub 上有什么 / 没什么

- **入 git**（代码，防丢失）：scraper、build 脚本、`assets/*.{js,css}`、Rust 源、`capabilities/`、`permissions/`、`patches.json`、发布脚本。
- **不入 git**（`.gitignore`，太大/可重建）：`out_v2/`（parsed+images 原始数据）、`_wiki_full_v2/{pages,data,category,images,...}`（生成的 HTML）、`target/`、`.venv/`、portable 文件夹/zip。
- **放 Release**：portable.zip（完整包）+ 每版 1 个补丁 zip + patches.json。

## 本地磁盘维护

发新版后只需保留**最新一个** `target/release/bundle/portable/pf2-wiki-offline_<最新版>_x64-portable` 文件夹（作下次补丁的 `--old` 基准）；旧的 portable 文件夹和所有本地 zip 可删（Release 有备份）。`target/release/{build,_up_,wix}` 是编译中间产物，可随时删，下次编译重建。
