# update_content.ps1 — 一条命令完成「拉取 wiki 更新 → 重建 → 发增量补丁」
#
# 利用 build_v2 的确定性 (deterministic): 全量重抓 + 全量重建后, build_patch
# 比对 sha256 只会把【真正变化的页面】放进补丁 —— 不需要手工 diff pageid。
# Cloudflare 在本机有持久化 browser-profile 可过墙, 所以 scrape 必须在本地跑
# (GitHub Actions 无头环境过不了 CF, 这是放在本地而非 CI 的根本原因)。
#
# 用法:
#   .\update_content.ps1 -PrevVer v0.3.21 -NewVer v0.3.22
#   (代码没改、纯内容更新时无需 -RebuildExe; 复用上一版 exe)
#
# 流程: 刷新CF cookie → 抓metadata → 抓内容(断点续传) → 抓图 → 重建HTML →
#       交给 release.ps1 出补丁+发布。
param(
  [Parameter(Mandatory=$true)][string]$PrevVer,
  [Parameter(Mandatory=$true)][string]$NewVer,
  [switch]$RebuildExe,
  [switch]$SkipScrape   # 只重建+发布, 跳过抓取 (调试用)
)
$ErrorActionPreference = 'Stop'
$fvtt    = "$env:USERPROFILE\Desktop\fvtt"
$scraper = "$fvtt\pf2wiki-scraper"
$wfv     = "$fvtt\_wiki_full_v2"
$py      = "$scraper\.venv\Scripts\python.exe"

if (-not $SkipScrape) {
  Write-Host "[1/6] 刷新 Cloudflare clearance cookie ..."
  & $py "$scraper\cookie_warmup_v2.py"
  Write-Host "[2/6] 抓取最新 metadata (~20s) ..."
  & $py "$scraper\dump_metadata_v2.py"
  Write-Host "[3/6] 抓取页面内容 (断点续传, 仅缺失/变化, ~数分钟) ..."
  & $py "$scraper\dump_parsed_v2_concurrent.py" -c 20
  Write-Host "[4/6] 抓取图片 (断点续传) ..."
  & $py "$scraper\dump_images_v2_concurrent.py" -c 16
} else {
  Write-Host "[1-4/6] 跳过抓取 (-SkipScrape)"
}

Write-Host "[5/6] 重建静态站点 (deterministic — 未变页面 hash 不变) ..."
& $py "$wfv\build_v2.py" --redirects
& $py "$wfv\build_class_hubs_v2.py"
& $py "$wfv\build_browse_v2.py"
& $py "$wfv\build_browse_letters_v2.py"
& $py "$wfv\build_search_v2.py"
& $py "$wfv\build_nav_stubs.py"

Write-Host "[6/6] 出补丁 + 发布 (交给 release.ps1) ..."
# 内容更新通常不改 Rust; 传 -RebuildExe 才重编 exe。
$rebuild = if ($RebuildExe) { '-RebuildExe' } else { '' }
& "$fvtt\src-tauri\release.ps1" -PrevVer $PrevVer -NewVer $NewVer @($rebuild | Where-Object { $_ })

Write-Host "[OK] 内容更新完成: $PrevVer → $NewVer"
Write-Host "     若 wiki 本次无内容变化, 补丁会非常小 (仅 _app_version 等元数据)。"
