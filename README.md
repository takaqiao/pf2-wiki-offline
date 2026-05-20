# PF2 离线百科

Pathfinder 2nd Edition 中文资料离线镜像 + Tauri Windows 客户端。源数据来自 [pf2.huijiwiki.com](https://pf2.huijiwiki.com)（CC BY-SA 4.0）。

## 终端用户

1. 到 [Releases](../../releases) 下载 `PF2 离线百科_0.1.0_x64-setup.exe`（~1 GB）
2. 双击安装（默认装到 `%LocalAppData%\Programs\pf2-wiki\`，不需要管理员）
3. Start Menu / 桌面快捷方式启动
4. 内嵌 HTTP server + WebView2 离线显示

## 开发者

### Pipeline 阶段

| 阶段 | 工具 | 时间 | 说明 |
|---|---|---|---|
| 0 · cookie warmup | `cookie_warmup_v2.py` | 5 s | Playwright 一次性拿 CF cookies |
| A · 元数据 | `dump_metadata_v2.py` | 20 s | 抓全 namespace + redirect 链 |
| B · 内容并发抓 | `dump_parsed_v2_concurrent.py -c 20` | 7-8 min | curl_cffi + Chrome TLS 模拟 |
| B.5 · redirect targets | `resolve_redirect_targets_v2_concurrent.py` | 2 s | 解析 redirect_map 真实 target |
| C · 图片并发抓 | `dump_images_v2_concurrent.py -c 16` | 1 min | imageinfo + 下载 originalurl |
| D · 原生 CSS | `fetch_native_styles_v2.py` | 3 s | pulled huiji native CSS (390 KB) |
| F · build HTML | `build_v2.py --redirects` | 7 min | parse.text → HTML + redirect stubs |
| F.5 · browse 页 | `build_browse_v2.py` + `build_class_hubs_v2.py` | 15 s | 13 buckets + classes/source hubs |
| G · 搜索索引 | `build_search_v2.py` | 1.5 min | titles.js + bigram + word shards |
| H · 打包发版 | `cargo build --release` + `release.ps1` | 5-20 min | portable ZIP ~1.2 GB（放弃 NSIS：2GB bundle 上游 bug）|

总耗时（curl_cffi 并发版）：~25-35 min 端到端。

### 环境

- Python 3.14 + Playwright 1.58 + jieba + curl_cffi 0.15 + beautifulsoup4 + Pillow
- Node 24 + npm 11
- Rust 1.95 + cargo + tauri-cli 2.11

### 一键 pipeline

```powershell
cd pf2wiki-scraper
.\run_v2_pipeline.ps1
```

### CI / 发版

CI（GitHub Actions）**仅验证代码能编译**——不产出发布物。语料太大（不入 git）且 CF 反爬过不了无头 runner，**发版一律本地**：`src-tauri\release.ps1 -PrevVer vX -NewVer vY [-RebuildExe]`，产出 portable ZIP + 上传 Release + 更新 `patches.json`。

**更新机制**：纯客户端驱动——`assets/updater_ui.js` 拉 `patches.json`（raw.githubusercontent）走版本链，调 `apply_incremental_update` 应用增量补丁。**无** Tauri 标准 updater 插件、**无** `latest.json`、**无**签名。

## 项目结构

```
pf2-wiki-offline/
├── pf2wiki-scraper/        Python scrapers (curl_cffi + Playwright fallback)
├── _wiki_full_v2/          Build scripts + CSS/JS/snippets (no built artifacts in git)
├── src-tauri/              Rust Tauri shell
├── _tauri_placeholder/     Minimal frontendDist (real content served by tiny_http)
├── agent_outputs_v2/       Iteration log + scout report
└── .github/workflows/      CI
```

## License

MIT（代码部分）— wiki 内容继承 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)，PF2 游戏内容遵循 Paizo OGL / 社区使用政策。
