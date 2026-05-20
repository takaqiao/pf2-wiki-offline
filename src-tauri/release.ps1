# release.ps1 — 一条命令发布新版本 (链式增量更新)
#
# 每版只生成 1 个 patch (上一版→本版) 并追加到 patches.json 的版本链。
# 客户端会从自己的版本沿链应用所有小补丁到最新。
#
# 用法:
#   .\release.ps1 -PrevVer v0.3.19 -NewVer v0.3.20 [-RebuildExe]
#
# 前置: 已 bump _app_version.json / Cargo.toml / tauri.conf.json 到 NewVer，
#       (若改了 Rust) 加 -RebuildExe，且 _wiki_full_v2 已是最新内容。
param(
  [Parameter(Mandatory=$true)][string]$PrevVer,
  [Parameter(Mandatory=$true)][string]$NewVer,
  [switch]$RebuildExe
)
$ErrorActionPreference = 'Stop'
$fvtt   = "$env:USERPROFILE\Desktop\fvtt"
$rel    = "$fvtt\src-tauri\target\release"
$base   = "$rel\bundle\portable"
$repo   = "$env:USERPROFILE\pf2-wiki-offline"
$py     = "$fvtt\pf2wiki-scraper\.venv\Scripts\python.exe"
$sevenz = "C:\Program Files\7-Zip\7z.exe"
$sv     = $NewVer.Replace('v','')
$prevDir = "$base\pf2-wiki-offline_$($PrevVer.Replace('v',''))_x64-portable"
$newDir  = "$base\pf2-wiki-offline_${sv}_x64-portable"

if ($RebuildExe) {
  Write-Host "[*] cargo build ..."
  Push-Location "$fvtt\src-tauri"
  & "$env:USERPROFILE\.cargo\bin\cargo.exe" build --release
  Pop-Location
}

Write-Host "[*] assembling $NewVer portable folder ..."
if (Test-Path $newDir) { Remove-Item -Recurse -Force $newDir }
New-Item -ItemType Directory -Force $newDir | Out-Null
Copy-Item "$rel\pf2-wiki.exe" "$newDir\pf2-wiki.exe"
robocopy "$fvtt\_wiki_full_v2" "$newDir\_wiki_full_v2" /MIR /NFL /NDL /NJH /NJS /NP /NS /NC | Out-Null

Write-Host "[*] zipping ..."
Remove-Item "$newDir.zip" -Force -ErrorAction SilentlyContinue
& $sevenz a -tzip -mx=3 -mcu=on "$newDir.zip" "$newDir" | Out-Null

Write-Host "[*] building ONE patch $PrevVer -> $NewVer + appending chain ..."
$pj = "$base\patches.json"
# Seed patches.json from the repo copy so the chain accumulates across releases.
if (Test-Path "$repo\patches.json") { Copy-Item "$repo\patches.json" $pj -Force }
$patchZip = "$base\pf2-wiki-patch_${PrevVer}_to_${NewVer}.zip"
$baseUrl  = "https://github.com/takaqiao/pf2-wiki-offline/releases/download/$NewVer"
& $py "$fvtt\src-tauri\build_patch.py" --old $prevDir --new $newDir --out $patchZip `
    --from-ver $PrevVer --to-ver $NewVer --patches-json $pj --base-url $baseUrl

Write-Host "[*] creating GitHub release + uploading (portable + 1 patch + patches.json) ..."
Push-Location $repo
git tag $NewVer -m "$NewVer"
git push origin $NewVer
gh release create $NewVer --title "$NewVer" --notes "Incremental release. Existing users get a small auto-update patch; new users download the full portable.zip."
gh release upload $NewVer "$newDir.zip" $patchZip $pj --clobber
Pop-Location

Write-Host "[*] committing patches.json + version bumps to repo ..."
Copy-Item $pj "$repo\patches.json" -Force
Copy-Item "$fvtt\_wiki_full_v2\_app_version.json" "$repo\_wiki_full_v2\_app_version.json" -Force
Copy-Item "$fvtt\src-tauri\Cargo.toml" "$repo\src-tauri\Cargo.toml" -Force
Copy-Item "$fvtt\src-tauri\tauri.conf.json" "$repo\src-tauri\tauri.conf.json" -Force
Push-Location $repo
git add patches.json _wiki_full_v2/_app_version.json src-tauri/Cargo.toml src-tauri/tauri.conf.json
git commit -m "release $NewVer (chain patch from $PrevVer)"
git push origin main
Pop-Location

Write-Host "[OK] $NewVer released. Patch $PrevVer->$NewVer = $([math]::Round((Get-Item $patchZip).Length/1MB,2)) MB"
