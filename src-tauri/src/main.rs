// PF2 离线百科 — Tauri entry (binary-only, no lib.rs).
// Spins up an embedded HTTP server bound to 127.0.0.1:<random port>, then
// loads index.html in the Tauri WebView serving from resource_dir.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{SocketAddr, TcpListener};
use std::path::PathBuf;
use std::sync::Arc;
use std::thread;

use tauri::Manager;
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

fn main() {
    let port = pick_free_port();
    let start_url = format!("http://127.0.0.1:{port}/index.html");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let base = app.path().resource_dir().expect("resource_dir");
            // Try multiple resource path layouts (Tauri NSIS uses `_up_/` for
            // resources from `../` glob patterns; standalone exe + dev mode
            // expect resources next to exe). Probe in order, use first that exists.
            let candidates = [
                base.join("_up_").join("_wiki_full_v2"),
                base.join("_wiki_full_v2"),
                base.join("resources").join("_up_").join("_wiki_full_v2"),
                base.join("resources").join("_wiki_full_v2"),
                // Try one level up — when running release exe from target/release/
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
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
