# Run the entire v2 scrape + build pipeline end-to-end.
# Concurrent + curl_cffi (no Playwright per request).
# Each phase is idempotent / resumable; safe to re-run.

$ErrorActionPreference = "Stop"
$root = "C:\Users\Taka\Desktop\fvtt"
$py = "$root\pf2wiki-scraper\.venv\Scripts\python.exe"

function Step($name, $block) {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  $name"
    Write-Host "=========================================="
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & $block
    $sw.Stop()
    Write-Host "  [$name done in $([math]::Round($sw.Elapsed.TotalMinutes, 1)) min]"
}

Set-Location "$root\pf2wiki-scraper"

# Phase 0: cookie warmup (skipped if cookies present + fresh)
$cookies = "$root\pf2wiki-scraper\out_v2\cookies.json"
$cookieFresh = $false
if (Test-Path $cookies) {
    $age = (Get-Date) - (Get-Item $cookies).LastWriteTime
    if ($age.TotalMinutes -lt 25) { $cookieFresh = $true }
}
if (-not $cookieFresh) {
    Step "Phase 0: Cookie warmup (Playwright -> CF cookies)" {
        & $py cookie_warmup_v2.py
    }
} else {
    Write-Host "Phase 0: cookies fresh (< 25 min), skipping warmup"
}

# Phase A: metadata
if (-not (Test-Path "$root\pf2wiki-scraper\out_v2\metadata.json")) {
    Step "Phase A: Metadata harvest (Playwright)" {
        & $py dump_metadata_v2.py
    }
} else {
    Write-Host "Phase A: metadata.json exists, skipping"
}

# Phase B: concurrent parsed scrape (curl_cffi)
Step "Phase B: Parsed scrape (curl_cffi c=20)" {
    & $py dump_parsed_v2_concurrent.py -c 20
}

# Phase B.5: resolve redirect targets (curl_cffi)
Step "Phase B.5: Resolve redirect targets (curl_cffi c=8)" {
    & $py resolve_redirect_targets_v2_concurrent.py
}

# Phase C: concurrent image scrape (curl_cffi)
Step "Phase C: Image scrape (curl_cffi c=16)" {
    & $py dump_images_v2_concurrent.py -c 16
}

# Phase F: build static HTML
Step "Phase F: Build static HTML" {
    Set-Location "$root\_wiki_full_v2"
    & $py build_v2.py --redirects
    Set-Location "$root\pf2wiki-scraper"
}

# Phase G: search index
Step "Phase G: Build search index" {
    Set-Location "$root\_wiki_full_v2"
    & $py build_search_v2.py
    Set-Location "$root\pf2wiki-scraper"
}

# Phase H: Tauri (requires Rust; manual)
Write-Host ""
Write-Host "Phase H (Tauri): manual — requires Rust toolchain:"
Write-Host "  winget install Rustlang.Rustup"
Write-Host "  rustup default stable"
Write-Host "  cargo install tauri-cli --version '^2.0'"
Write-Host "  cd $root\src-tauri"
Write-Host "  cargo tauri build  # -> bundle/nsis/*.exe"

Write-Host ""
Write-Host "=========================================="
Write-Host "  Pipeline run complete"
Write-Host "=========================================="
