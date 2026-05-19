# PF2 离线百科 — Tauri 打包

Windows .exe NSIS 安装包构建说明。

## 先决条件（用户手动）

```powershell
winget install --id Rustlang.Rustup
rustup default stable
cargo install tauri-cli --version "^2.0" --locked
```

可选: WebView2 Runtime 通常 Windows 11 自带；老 Win10 系统可能需要安装
（https://developer.microsoft.com/en-us/microsoft-edge/webview2/）。

## 准备工作

1. 确保 `_wiki_full_v2/` 已构建完成（含 `index.html`, `pages/`, `data/`, `assets/`,
   `images/` 等）。
2. 准备 `src-tauri/icons/` 目录（若没有，初次构建用默认占位）:
   ```powershell
   cargo tauri icon C:\path\to\source-logo-1024x1024.png
   ```
3. 创建项目根 `LICENSE` 文件（tauri.conf.json 引用）。

## 构建

```powershell
cd C:\Users\Taka\Desktop\fvtt\src-tauri
cargo tauri build
```

输出: `src-tauri/target/release/bundle/nsis/PF2 离线百科_0.1.0_x64-setup.exe`

体积预估 ~1.5-2 GB（含 _wiki_full_v2 资源）。

## 运行说明

主入口 `src/main.rs`:
- 启动时 OS 分配 127.0.0.1 上的空闲端口
- `tiny_http` crate 在该端口上服务 `_wiki_full_v2/` 静态资源
- Tauri WebView 加载 `http://127.0.0.1:<port>/index.html`
- 资源路径解析: 安装后 `tauri::path::resource_dir() / "_wiki_full_v2"`

## 调试模式

```powershell
cargo tauri dev
```
（需先在 `_wiki_full_v2/` 启动 `python -m http.server 7891`）
