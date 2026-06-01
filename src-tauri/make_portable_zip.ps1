# Build a portable ZIP package: pf2-wiki.exe + _wiki_full_v2/ in one folder.
# Users can unzip + double-click pf2-wiki.exe without running NSIS at all.
# Bypasses Defender/SmartScreen heuristics that may flag NSIS installer.
#
# Usage: .\make_portable_zip.ps1 [-Version 0.3.3]

param(
    [string]$Version = "0.3.3"
)

$ErrorActionPreference = "Stop"

$srcExe = "C:\Users\Taka\Desktop\fvtt\src-tauri\target\release\pf2-wiki.exe"
$srcWiki = "C:\Users\Taka\Desktop\fvtt\_wiki_full_v2"
$dstName = "pf2-wiki-offline_${Version}_x64-portable"
$dstDir = "C:\Users\Taka\Desktop\fvtt\src-tauri\target\release\portable\$dstName"
$zipPath = "C:\Users\Taka\Desktop\fvtt\src-tauri\target\release\portable\$dstName.zip"

if (-not (Test-Path $srcExe)) {
    Write-Error "missing $srcExe — run `cargo tauri build --no-bundle` first"
    exit 1
}

if (Test-Path $dstDir) { Remove-Item $dstDir -Recurse -Force }
New-Item -ItemType Directory $dstDir -Force | Out-Null

Write-Host "==> copying pf2-wiki.exe ($(((Get-Item $srcExe).Length/1MB).ToString('F1')) MB)..."
Copy-Item $srcExe $dstDir

Write-Host "==> copying _wiki_full_v2/ (this takes ~30s due to 40k files)..."
$t0 = Get-Date
robocopy $srcWiki "$dstDir\_wiki_full_v2" /E /MT:16 /NDL /NFL /NJH /NJS /NS /NC /R:1 /W:1 2>&1 | Out-Null
$dt = (Get-Date) - $t0
Write-Host "    copy done in $($dt.TotalSeconds.ToString('F1')) sec"

$wikiSize = (Get-ChildItem "$dstDir\_wiki_full_v2" -Recurse -File | Measure-Object -Sum Length).Sum
Write-Host "    wiki size: $([math]::Round($wikiSize/1MB,1)) MB / $((Get-ChildItem "$dstDir\_wiki_full_v2" -Recurse -File).Count) files"

# Write a README.txt for the user
@"
PF2 离线百科 v$Version — Portable Edition

直接运行:
  pf2-wiki.exe

不需要安装。如果 NSIS 装包 (setup.exe) 在你机器上报 "corrupted data" 错,
用这个 portable 版本绕开 NSIS / Windows Defender 的解压过程。

文件夹结构:
  pf2-wiki.exe          主程序 (~10 MB)
  _wiki_full_v2\        wiki 资源 (~1.85 GB)

要点:
- 不需要管理员权限
- 不在注册表写任何东西, 可随意复制到 U 盘 / 其他电脑
- 完全离线, 不联网 (除自动更新检查会访问 GitHub Release)

源代码 + 自构建说明:
  https://github.com/takaqiao/pf2-wiki-offline

License: MIT (代码) + CC BY-SA 4.0 (wiki 内容继承自 pf2.huijiwiki.com)
"@ | Out-File -FilePath "$dstDir\README.txt" -Encoding utf8

Write-Host ""
Write-Host "==> creating ZIP (this takes ~60s for ~1.85 GB, no compression for speed)..."
$t1 = Get-Date
# Use Compress-Archive (built-in)... actually for 2 GB use 7zip if available, fallback Compress-Archive
$sevenZip = Get-Command 7z -ErrorAction SilentlyContinue
if ($sevenZip) {
    & 7z a -tzip -mx=3 -mmt=on $zipPath "$dstDir\*" | Out-Null
    Write-Host "    used 7zip (mx=3 fast compress)"
} else {
    Compress-Archive -Path "$dstDir\*" -DestinationPath $zipPath -CompressionLevel Fastest -Force
    Write-Host "    used built-in Compress-Archive"
}
$dt = (Get-Date) - $t1
$zipSize = (Get-Item $zipPath).Length / 1MB
Write-Host "    zip done: $([math]::Round($zipSize, 1)) MB in $($dt.TotalSeconds.ToString('F1')) sec"

Write-Host ""
Write-Host "=== output ==="
Write-Host "Portable folder: $dstDir"
Write-Host "Portable zip:    $zipPath"
