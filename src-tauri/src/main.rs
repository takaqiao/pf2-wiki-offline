// PF2 离线百科 — Tauri 2 entry with auto-updater UI.
//
// Architecture:
//   1. Embedded tiny_http server on 127.0.0.1:<random_port> serves the wiki corpus
//   2. WebView loads localhost URL via window.location.replace
//   3. External link clicks intercepted by assets/external_links.js -> IPC
//      open_external -> open crate launches default browser
//   4. On startup, async update check vs GitHub Release latest.json:
//      - If newer version, emit "update-available" event to webview
//      - Webview's updater_ui.js shows banner; user clicks "更新" -> IPC
//        install_update -> Rust downloads + installs + restarts

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{SocketAddr, TcpListener};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::thread;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_updater::{Update, UpdaterExt};
use tiny_http::{Header, Response, Server};

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
    let root = Arc::new(resource_root);

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

#[derive(Clone, Serialize)]
struct UpdateInfo {
    current_version: String,
    new_version: String,
    body: Option<String>,
}

// Holds the latest Update object for the install_update command to use.
type PendingUpdate = Arc<Mutex<Option<Update>>>;

#[tauri::command]
fn open_external(url: String) -> Result<(), String> {
    open::that(&url).map_err(|e| e.to_string())
}

#[tauri::command]
async fn install_update(
    app: AppHandle,
    pending: tauri::State<'_, PendingUpdate>,
) -> Result<(), String> {
    let update = pending.lock().map_err(|e| e.to_string())?.take();
    let update = update.ok_or_else(|| "no pending update".to_string())?;
    update
        .download_and_install(|_chunk, _total| {}, || {})
        .await
        .map_err(|e| e.to_string())?;
    // Restart the application after install
    app.restart();
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
#[tauri::command]
async fn apply_incremental_update(
    app: AppHandle,
    url: String,
    expected_sha: String,
) -> Result<(), String> {
    use sha2::{Digest, Sha256};
    use std::fs;
    use std::io::{Read, Write};
    use std::process::Command;

    eprintln!("[pf2-wiki updater] downloading patch from {url}");
    let resp = ureq::get(&url)
        .timeout(std::time::Duration::from_secs(120))
        .call()
        .map_err(|e| format!("download failed: {e}"))?;
    let mut buf = Vec::with_capacity(50 * 1024 * 1024);
    resp.into_reader()
        .take(500 * 1024 * 1024) // 500 MB hard cap
        .read_to_end(&mut buf)
        .map_err(|e| format!("read failed: {e}"))?;
    eprintln!("[pf2-wiki updater] downloaded {} bytes", buf.len());

    // Verify sha256
    let mut hasher = Sha256::new();
    hasher.update(&buf);
    let actual = format!("{:x}", hasher.finalize());
    if actual.to_lowercase() != expected_sha.to_lowercase() {
        return Err(format!(
            "sha256 mismatch: got {actual}, expected {expected_sha}"
        ));
    }
    eprintln!("[pf2-wiki updater] sha256 verified");

    // Save patch to temp
    let temp_dir = std::env::temp_dir();
    let patch_path = temp_dir.join("pf2-wiki-patch.zip");
    let ps1_path = temp_dir.join("pf2-wiki-update.ps1");
    fs::write(&patch_path, &buf).map_err(|e| format!("save failed: {e}"))?;

    // Determine install dir
    let exe = std::env::current_exe().map_err(|e| format!("current_exe: {e}"))?;
    let install_dir = exe
        .parent()
        .ok_or("no parent dir")?
        .to_path_buf();

    // Generate update.ps1
    let ps1 = format!(
        r#"$ErrorActionPreference = 'Continue'
Start-Sleep -Seconds 2
$patch = '{patch}'
$install = '{install}'
$exe = '{exe}'
try {{
    Expand-Archive -Path $patch -DestinationPath $install -Force
    $removeFile = Join-Path $install '_remove_these.txt'
    if (Test-Path $removeFile) {{
        Get-Content $removeFile | ForEach-Object {{
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
    Start-Process -FilePath $exe
}} catch {{
    [System.Windows.Forms.MessageBox]::Show("PF2 离线百科更新失败：`n$_", "更新失败", 0, 16)
}}
Remove-Item $PSCommandPath -Force -ErrorAction SilentlyContinue
"#,
        patch = patch_path.display(),
        install = install_dir.display(),
        exe = exe.display()
    );
    fs::write(&ps1_path, ps1).map_err(|e| format!("ps1 write failed: {e}"))?;
    eprintln!("[pf2-wiki updater] wrote {}", ps1_path.display());

    // Launch detached PowerShell
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
    // Exit so PS can take over install dir
    app.exit(0);
    Ok(())
}

fn main() {
    let port = pick_free_port();
    let start_url = format!("http://127.0.0.1:{port}/index.html");

    let pending_update: PendingUpdate = Arc::new(Mutex::new(None));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(pending_update.clone())
        .invoke_handler(tauri::generate_handler![
            open_external,
            install_update,
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

            // Async update check; emit "update-available" if newer version exists
            let handle = app.handle().clone();
            let pending = pending_update.clone();
            tauri::async_runtime::spawn(async move {
                match handle.updater() {
                    Ok(updater) => match updater.check().await {
                        Ok(Some(update)) => {
                            eprintln!(
                                "[pf2-wiki updater] update available: {} -> {}",
                                update.current_version, update.version
                            );
                            let info = UpdateInfo {
                                current_version: update.current_version.clone(),
                                new_version: update.version.clone(),
                                body: update.body.clone(),
                            };
                            if let Ok(mut slot) = pending.lock() {
                                *slot = Some(update);
                            }
                            let _ = handle.emit("update-available", info);
                        }
                        Ok(None) => {
                            eprintln!("[pf2-wiki updater] no update available");
                        }
                        Err(e) => {
                            eprintln!("[pf2-wiki updater] check failed: {}", e);
                        }
                    },
                    Err(e) => {
                        eprintln!("[pf2-wiki updater] init failed: {}", e);
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
