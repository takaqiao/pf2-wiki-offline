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
        let _ = request.respond(Response::from_data(bytes).with_header(header));
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

fn main() {
    let port = pick_free_port();
    let start_url = format!("http://127.0.0.1:{port}/index.html");

    let pending_update: PendingUpdate = Arc::new(Mutex::new(None));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(pending_update.clone())
        .invoke_handler(tauri::generate_handler![open_external, install_update])
        .setup(move |app| {
            let base = app.path().resource_dir().expect("resource_dir");
            let candidates = [
                base.join("_up_").join("_wiki_full_v2"),
                base.join("_wiki_full_v2"),
                base.join("resources").join("_up_").join("_wiki_full_v2"),
                base.join("resources").join("_wiki_full_v2"),
                base.join("..").join("..").join("..").join("_wiki_full_v2"),
            ];
            let resource_root = candidates
                .iter()
                .find(|p| p.exists() && p.is_dir())
                .cloned()
                .unwrap_or_else(|| base.join("_wiki_full_v2"));

            eprintln!("[pf2-wiki] resource_root = {}", resource_root.display());
            eprintln!("[pf2-wiki] resource_root exists = {}", resource_root.exists());

            thread::spawn(move || serve_static(resource_root, port));

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
