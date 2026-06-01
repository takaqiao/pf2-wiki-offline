# release.ps1 - one command to publish a new version (chained incremental updates).
#
# Each release ships exactly ONE patch (prev -> current) appended to the version
# chain in patches.json. A client walks the chain from its own version to latest.
#
# Usage:
#   .\release.ps1 -PrevVer v0.3.19 -NewVer v0.3.20 [-RebuildExe]
#
# Prereq: bump _app_version.json / Cargo.toml / tauri.conf.json to NewVer first,
#         add -RebuildExe if Rust changed, and ensure _wiki_full_v2 is current.
#
# NOTE: keep this file ASCII-only. It is read by Windows PowerShell 5.1, which
# decodes a BOM-less script as the system ANSI codepage (GB2312 on zh-CN); any
# non-ASCII here (even in comments) can desync the parser. English only.
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

# Guard: prevDir is the diff base for the incremental patch. It MUST be the
# clean, as-published previous-version portable folder. If it is missing or was
# overwritten (e.g. swapping the exe / editing _wiki_full_v2 during local
# testing), the patch is computed wrong (loses real changes, or treats every
# file as new -> near-full-size patch).
if (-not (Test-Path $prevDir -PathType Container)) {
  Write-Host "[ERROR] prevDir not found: $prevDir" -ForegroundColor Red
  Write-Host "        It must be the clean, as-published $PrevVer portable folder (the patch diff base)."
  Write-Host "        If deleted/overwritten, re-download portable.zip from the $PrevVer release and extract it back."
  exit 1
}

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
# Exclude build-only files from the shipped portable: Python generators, caches,
# build-time snippets, and stray logs are never read at runtime.
robocopy "$fvtt\_wiki_full_v2" "$newDir\_wiki_full_v2" /MIR /NFL /NDL /NJH /NJS /NP /NS /NC `
    /XF *.py *.pyc *.log /XD __pycache__ _snippets | Out-Null

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

# Preflight: this release's hop must be present and latest must point at NewVer
# (catches a forgotten/mis-written chain entry before we tag + publish).
$pjObj = Get-Content $pj -Raw -Encoding UTF8 | ConvertFrom-Json
if ($pjObj.latest -ne $NewVer) {
    Write-Host "[ERROR] patches.json latest=$($pjObj.latest), expected $NewVer" -ForegroundColor Red
    exit 1
}
$hop = $pjObj.chain.$PrevVer
if (-not $hop -or $hop.to -ne $NewVer) {
    Write-Host "[ERROR] patches.json missing hop $PrevVer -> $NewVer" -ForegroundColor Red
    exit 1
}
Write-Host "[ok] chain hop $PrevVer -> $NewVer present; latest=$NewVer"

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
