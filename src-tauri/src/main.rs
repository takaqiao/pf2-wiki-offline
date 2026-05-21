// PF2 离线百科 — Tauri 2 entry with auto-updater UI.
//
// Architecture:
//   1. Embedded tiny_http server on 127.0.0.1:<random_port> serves the wiki corpus
//   2. WebView loads localhost URL via window.location.replace
//   3. External link clicks intercepted by assets/external_links.js -> IPC
//      open_external -> open crate launches default browser
//   4. Updates are fully client-side: assets/updater_ui.js polls patches.json
//      (raw.githubusercontent), walks the version chain, and on click invokes
//      apply_incremental_update -> Rust downloads/verifies/extracts patches and
//      relaunches. No standard updater plugin (portable build, no latest.json).
//
// ACL note: the wiki is served over http://127.0.0.1:<port>, so the webview's
// IPC origin is REMOTE — capabilities/default.json MUST list those URLs under
// `remote.urls` or every invoke is rejected with "not allowed by ACL".

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{SocketAddr, TcpListener};
use std::path::PathBuf;
use std::sync::Arc;
use std::thread;

use tauri::{AppHandle, Emitter, Manager};
use tiny_http::{Header, Response, Server};

/// Progress payload emitted to the webview during apply_incremental_update so
/// updater_ui.js can render a percentage bar (phase: download | verify | apply).
#[derive(Clone, serde::Serialize)]
struct UpdateProgress {
    phase: String,
    patch: usize,
    total_patches: usize,
    downloaded: u64,
    total: u64,
    pct: u32,
}

fn pick_free_port() -> u16 {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind random port");
    let port = listener.local_addr().expect("local addr").port();
    drop(listener);
    port
}

/// Block until tiny_http is accepting connections on the given port, or timeout.
/// Returns true if ready, false on timeout. Used to avoid the race where the
/// webview tries to load localhost before tiny_http's server.incoming_requests()
/// loop starts servicing them.
fn wait_for_server(port: u16, deadline_ms: u64) -> bool {
    use std::time::{Duration, Instant};
    let addr: SocketAddr = format!("127.0.0.1:{port}").parse().expect("addr");
    let started = Instant::now();
    while started.elapsed() < Duration::from_millis(deadline_ms) {
        if std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(100)).is_ok() {
            return true;
        }
        thread::sleep(Duration::from_millis(30));
    }
    false
}

fn serve_static(resource_root: PathBuf, port: u16) {
    let addr: SocketAddr = format!("127.0.0.1:{port}").parse().expect("addr");
    let server = Server::http(addr).expect("start tiny_http");
    // Canonicalize once so per-request traversal checks compare like-for-like
    // (Windows canonical paths use the \\?\ prefix).
    let root = Arc::new(std::fs::canonicalize(&resource_root).unwrap_or(resource_root));

    for request in server.incoming_requests() {
        let url = request.url().to_string();
        let root = root.clone();

        let mut path = match urlencoding::decode(url.split('?').next().unwrap_or("/")) {
            Ok(p) => p.into_owned(),
            Err(_) => {
                let _ = request.respond(Response::from_string("Bad Request").with_status_code(400));
                continue;
            }
        };

        if path.contains("..") {
            let _ = request.respond(Response::from_string("Forbidden").with_status_code(403));
            continue;
        }

        if path == "/" || path.is_empty() {
            path = "/index.html".to_string();
        }

        let full = root.join(&path[1..]);

        // Defense in depth: a resolved path must stay under root. Catches
        // Windows absolute-path joins (e.g. "/C:/Windows/...", where PathBuf::join
        // discards the base) and symlink escapes that the textual ".." check
        // above misses. canonicalize only succeeds for existing paths; a
        // non-existent path is no traversal and falls through to 404 below.
        if let Ok(canon) = std::fs::canonicalize(&full) {
            if !canon.starts_with(&*root) {
                let _ = request.respond(Response::from_string("Forbidden").with_status_code(403));
                continue;
            }
        }

        if !full.exists() || !full.is_file() {
            // Friendly 404 fallback: serve _wiki_full_v2/404.html with HTTP
            // status 404 (so the webview renders our themed "page not found"
            // shell instead of a bare plain-text response). The 404 page
            // pre-fills its search box from window.location.pathname, so the
            // user can immediately retry as a search query. Falls through to
            // the plain "Not Found" string only if even the fallback file is
            // missing (e.g. a corrupt install with no _wiki_full_v2/404.html).
            let fallback = root.join("404.html");
            if fallback.exists() && fallback.is_file() {
                if let Ok(bytes) = std::fs::read(&fallback) {
                    let ct = Header::from_bytes(
                        &b"Content-Type"[..],
                        b"text/html; charset=utf-8",
                    )
                    .expect("ctype header");
                    let cc = Header::from_bytes(
                        &b"Cache-Control"[..],
                        b"no-cache, must-revalidate",
                    )
                    .expect("cache header");
                    let _ = request.respond(
                        Response::from_data(bytes)
                            .with_header(ct)
                            .with_header(cc)
                            .with_status_code(404),
                    );
                    continue;
                }
            }
            let _ = request.respond(Response::from_string("Not Found").with_status_code(404));
            continue;
        }

        let mime = mime_guess::from_path(&full).first_or_octet_stream();
        let bytes = match std::fs::read(&full) {
            Ok(b) => b,
            Err(_) => {
                let _ = request.respond(Response::from_string("IO Error").with_status_code(500));
                continue;
            }
        };

        let header = Header::from_bytes(&b"Content-Type"[..], mime.essence_str().as_bytes())
            .expect("ctype header");
        // Per-asset cache policy:
        // - HTML/CSS/JS/JSON: no-cache + must-revalidate so updates take effect
        //   on next page load (no stale chrome after applying a patch).
        // - Images/fonts/media: long-lived cache OK (rarely change, large bytes).
        let mime_str = mime.essence_str();
        let cache_value: &[u8] = if mime_str.starts_with("text/")
            || mime_str.contains("javascript")
            || mime_str.contains("json")
            || mime_str.contains("css")
            || mime_str.contains("html")
        {
            b"no-cache, must-revalidate"
        } else {
            b"public, max-age=604800"
        };
        let cache_header = Header::from_bytes(&b"Cache-Control"[..], cache_value)
            .expect("cache-control header");
        let _ = request.respond(
            Response::from_data(bytes)
                .with_header(header)
                .with_header(cache_header),
        );
    }
}

#[tauri::command]
fn open_external(url: String) -> Result<(), String> {
    // Only ever hand web links to the system browser. The webview only sends
    // http(s) external links here; reject anything else (file://, etc.) so a
    // stray invoke can't launch arbitrary protocol handlers.
    if !(url.starts_with("http://") || url.starts_with("https://")) {
        return Err(format!("refused non-http(s) url: {url}"));
    }
    open::that(&url).map_err(|e| e.to_string())
}

/// Apply incremental patch update for portable distribution.
///
/// Flow:
/// 1. Download patch.zip from `url` to %TEMP%
/// 2. Verify sha256 matches `expected_sha`
/// 3. Write a self-deleting update.ps1 to %TEMP% that:
///    - waits 2 s for pf2-wiki.exe to exit
///    - extracts patch.zip into install_dir (exe parent)
///    - applies _remove_these.txt deletions
///    - cleans up patch.zip + manifest + ps1 itself
///    - relaunches pf2-wiki.exe
/// 4. Spawn the ps1 detached
/// 5. app.exit(0)
/// One step in an update chain: a single patch zip + its sha256.
#[derive(serde::Deserialize)]
struct PatchStep {
    url: String,
    sha256: String,
}

/// Apply a CHAIN of incremental patches (v_cur→v+1→…→latest) in order.
///
/// Each release ships exactly ONE patch (previous→current). A client that is
/// several versions behind receives the ordered list of intermediate patches
/// and applies them sequentially — "无数个小更新迭代". Flow:
/// 1. Download every patch zip, verify each sha256
/// 2. Write update.ps1 that, after the app exits, Expand-Archive's each zip in
///    chain order (later patch assumes the earlier one is already applied),
///    processes each patch's _remove_these.txt, then relaunches
/// 3. Spawn ps1 detached, app.exit(0)
#[tauri::command]
async fn apply_incremental_update(
    app: AppHandle,
    patches: Vec<PatchStep>,
) -> Result<(), String> {
    use sha2::{Digest, Sha256};
    use std::fs;
    use std::io::Read;
    use std::process::Command;

    if patches.is_empty() {
        return Err("no patches to apply".into());
    }

    let temp_dir = std::env::temp_dir();
    let mut zip_paths: Vec<std::path::PathBuf> = Vec::new();

    for (i, step) in patches.iter().enumerate() {
        eprintln!(
            "[pf2-wiki updater] downloading patch {}/{}: {}",
            i + 1,
            patches.len(),
            step.url
        );
        let resp = ureq::get(&step.url)
            .timeout(std::time::Duration::from_secs(180))
            .call()
            .map_err(|e| format!("download #{} failed: {e}", i + 1))?;
        let total: u64 = resp
            .header("Content-Length")
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);
        // Stream in chunks so we can emit download progress to the webview.
        let mut buf = Vec::with_capacity(8 * 1024 * 1024);
        let mut reader = resp.into_reader().take(800 * 1024 * 1024);
        let mut chunk = [0u8; 65536];
        let mut downloaded: u64 = 0;
        let mut last_emit = std::time::Instant::now();
        loop {
            let n = reader
                .read(&mut chunk)
                .map_err(|e| format!("read #{} failed: {e}", i + 1))?;
            if n == 0 {
                break;
            }
            buf.extend_from_slice(&chunk[..n]);
            downloaded += n as u64;
            if last_emit.elapsed().as_millis() >= 120 {
                let pct = if total > 0 {
                    ((downloaded as f64 / total as f64) * 100.0).min(100.0) as u32
                } else {
                    0
                };
                let _ = app.emit(
                    "update-progress",
                    UpdateProgress {
                        phase: "download".into(),
                        patch: i + 1,
                        total_patches: patches.len(),
                        downloaded,
                        total,
                        pct,
                    },
                );
                last_emit = std::time::Instant::now();
            }
        }
        // download of this patch complete -> verify phase
        let _ = app.emit(
            "update-progress",
            UpdateProgress {
                phase: "verify".into(),
                patch: i + 1,
                total_patches: patches.len(),
                downloaded,
                total,
                pct: 100,
            },
        );
        let mut hasher = Sha256::new();
        hasher.update(&buf);
        let actual = format!("{:x}", hasher.finalize());
        if actual.to_lowercase() != step.sha256.to_lowercase() {
            return Err(format!(
                "patch #{} sha256 mismatch: got {actual}, expected {}",
                i + 1,
                step.sha256
            ));
        }
        let zp = temp_dir.join(format!("pf2-wiki-patch-{i}.zip"));
        fs::write(&zp, &buf).map_err(|e| format!("save #{} failed: {e}", i + 1))?;
        zip_paths.push(zp);
    }
    eprintln!(
        "[pf2-wiki updater] {} patch(es) downloaded + verified",
        patches.len()
    );
    // all patches in hand -> applying + relaunch imminent
    let _ = app.emit(
        "update-progress",
        UpdateProgress {
            phase: "apply".into(),
            patch: patches.len(),
            total_patches: patches.len(),
            downloaded: 0,
            total: 0,
            pct: 100,
        },
    );

    let exe = std::env::current_exe().map_err(|e| format!("current_exe: {e}"))?;
    let install_dir = exe.parent().ok_or("no parent dir")?.to_path_buf();
    let ps1_path = temp_dir.join("pf2-wiki-update.ps1");

    // PowerShell array of patch zip paths, in chain order.
    let zips_ps = zip_paths
        .iter()
        .map(|p| format!("'{}'", p.display()))
        .collect::<Vec<_>>()
        .join(",");

    let ps1 = format!(
        r#"$ErrorActionPreference = 'Continue'
Start-Sleep -Seconds 2
$install = '{install}'
$exe = '{exe}'
$patches = @({zips})
try {{
    foreach ($patch in $patches) {{
        Expand-Archive -Path $patch -DestinationPath $install -Force
        $removeFile = Join-Path $install '_remove_these.txt'
        if (Test-Path $removeFile) {{
            Get-Content $removeFile -Encoding UTF8 | ForEach-Object {{
                if ($_ -and $_.Trim()) {{
                    $target = Join-Path $install $_
                    if (Test-Path $target) {{ Remove-Item $target -Force -ErrorAction SilentlyContinue }}
                }}
            }}
            Remove-Item $removeFile -Force -ErrorAction SilentlyContinue
        }}
        $manifestFile = Join-Path $install '_patch_manifest.json'
        if (Test-Path $manifestFile) {{ Remove-Item $manifestFile -Force -ErrorAction SilentlyContinue }}
        Remove-Item $patch -Force -ErrorAction SilentlyContinue
    }}
    Start-Process -FilePath $exe
}} catch {{
    try {{ Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show("PF2 离线百科更新失败：`n$_", "更新失败", 0, 16) }} catch {{}}
    Start-Process -FilePath $exe
}}
Remove-Item $PSCommandPath -Force -ErrorAction SilentlyContinue
"#,
        install = install_dir.display(),
        exe = exe.display(),
        zips = zips_ps,
    );
    // Write with a UTF-8 BOM. Windows PowerShell 5.1 decodes a BOM-less .ps1
    // using the system ANSI code page (GB2312/CP936 on Chinese Windows), which
    // mangles any non-ASCII install path interpolated below (e.g.
    // C:\Users\<中文名>\...) into mojibake, breaking Expand-Archive. A BOM forces
    // correct UTF-8 decoding. (The _remove_these.txt list is read with
    // `Get-Content -Encoding UTF8` for the same reason.)
    let mut ps1_bytes = vec![0xEF, 0xBB, 0xBF];
    ps1_bytes.extend_from_slice(ps1.as_bytes());
    fs::write(&ps1_path, ps1_bytes).map_err(|e| format!("ps1 write failed: {e}"))?;
    eprintln!("[pf2-wiki updater] wrote {}", ps1_path.display());

    Command::new("powershell")
        .args([
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            ps1_path.to_str().ok_or("ps1 path not utf-8")?,
        ])
        .spawn()
        .map_err(|e| format!("spawn powershell: {e}"))?;

    eprintln!("[pf2-wiki updater] update launcher spawned, exiting");
    app.exit(0);
    Ok(())
}

fn main() {
    let port = pick_free_port();
    let start_url = format!("http://127.0.0.1:{port}/index.html");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            open_external,
            apply_incremental_update
        ])
        .setup(move |app| {
            let base = app.path().resource_dir().expect("resource_dir");
            // exe_dir is where pf2-wiki.exe sits. In portable ZIP layout this
            // is the directory containing _wiki_full_v2/, so it must be probed
            // first; Tauri 2's resource_dir() can point elsewhere when the app
            // is launched without an installer.
            let exe_dir: PathBuf = std::env::current_exe()
                .ok()
                .and_then(|p| p.parent().map(|p| p.to_path_buf()))
                .unwrap_or_else(|| base.clone());
            let candidates = [
                exe_dir.join("_wiki_full_v2"),
                exe_dir.join("_up_").join("_wiki_full_v2"),
                base.join("_up_").join("_wiki_full_v2"),
                base.join("_wiki_full_v2"),
                base.join("resources").join("_up_").join("_wiki_full_v2"),
                base.join("resources").join("_wiki_full_v2"),
                base.join("..").join("..").join("..").join("_wiki_full_v2"),
            ];
            let resource_root = match candidates.iter().find(|p| p.exists() && p.is_dir()) {
                Some(p) => p.clone(),
                None => {
                    let probed = candidates
                        .iter()
                        .map(|p| format!("  - {}", p.display()))
                        .collect::<Vec<_>>()
                        .join("\n");
                    panic!(
                        "[pf2-wiki] FATAL: could not locate _wiki_full_v2/.\n\
                         exe_dir = {}\n\
                         resource_dir = {}\n\
                         Checked these paths (none exist as a directory):\n{}\n\
                         Please report this with your install layout to the project issues page.",
                        exe_dir.display(),
                        base.display(),
                        probed
                    );
                }
            };

            eprintln!("[pf2-wiki] exe_dir = {}", exe_dir.display());
            eprintln!("[pf2-wiki] resource_dir = {}", base.display());
            eprintln!("[pf2-wiki] resource_root = {}", resource_root.display());
            eprintln!("[pf2-wiki] resource_root exists = {}", resource_root.exists());

            thread::spawn(move || serve_static(resource_root, port));

            // Wait up to 3 s for the server thread to bind + start accepting.
            // Avoids the race where eval() runs before tiny_http is ready, which
            // would show a "ERR_CONNECTION_REFUSED" white page until the user
            // hits refresh.
            let ready = wait_for_server(port, 3000);
            if !ready {
                eprintln!(
                    "[pf2-wiki] WARN: tiny_http on :{} not ready after 3s; navigating anyway",
                    port
                );
            }

            if let Some(main) = app.get_webview_window("main") {
                let _ = main.eval(&format!("window.location.replace('{}')", start_url));
            }

            // Update detection + application is entirely client-side: assets/
            // updater_ui.js polls patches.json (raw.githubusercontent) and calls
            // the apply_incremental_update command. No standard updater plugin.

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
