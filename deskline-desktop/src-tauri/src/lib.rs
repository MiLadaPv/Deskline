//! Deskline desktop shell (Tauri).
//! Starts the local Python tracker/API and shows the dashboard in a native window.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

const PORT: u16 = 8787;
const DASHBOARD_URL: &str = "http://127.0.0.1:8787";
const EXPECTED_EDITION: &str = "local-python";

struct BackendState {
    child: Mutex<Option<Child>>,
    we_started: bool,
}

fn port_open() -> bool {
    let addr = SocketAddr::from(([127, 0, 0, 1], PORT));
    TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
}

fn wait_for_server(timeout: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if port_open() {
            return true;
        }
        thread::sleep(Duration::from_millis(200));
    }
    false
}

/// GET /api/health over a plain TCP socket (no extra HTTP crate).
fn fetch_health_body() -> Option<String> {
    let addr = SocketAddr::from(([127, 0, 0, 1], PORT));
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(500)).ok()?;
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(2)));
    let req = format!(
        "GET /api/health HTTP/1.0\r\nHost: 127.0.0.1:{PORT}\r\nConnection: close\r\n\r\n"
    );
    stream.write_all(req.as_bytes()).ok()?;
    let mut buf = String::new();
    stream.read_to_string(&mut buf).ok()?;
    let body = buf.split("\r\n\r\n").nth(1)?;
    Some(body.trim().to_string())
}

fn is_our_backend() -> bool {
    let Some(body) = fetch_health_body() else {
        return false;
    };
    let Ok(v) = serde_json::from_str::<serde_json::Value>(&body) else {
        return false;
    };
    v.get("ok").and_then(|x| x.as_bool()) == Some(true)
        && v.get("app").and_then(|x| x.as_str()) == Some("Deskline")
        && v.get("edition").and_then(|x| x.as_str()) == Some(EXPECTED_EDITION)
}

/// Kill whatever is LISTENING on 127.0.0.1:8787 (legacy Deskline.exe, stale python, etc.).
#[cfg(windows)]
fn free_dashboard_port() {
    let Ok(output) = Command::new("netstat").args(["-ano"]).output() else {
        return;
    };
    let text = String::from_utf8_lossy(&output.stdout);
    let needle = format!("127.0.0.1:{PORT}");
    let mut pids = std::collections::BTreeSet::new();
    for line in text.lines() {
        if !line.contains(&needle) || !line.contains("LISTENING") {
            continue;
        }
        if let Some(pid) = line.split_whitespace().last() {
            if let Ok(n) = pid.parse::<u32>() {
                if n > 0 {
                    pids.insert(n);
                }
            }
        }
    }
    for pid in pids {
        eprintln!("Deskline: freeing port {PORT} by stopping PID {pid}");
        let _ = Command::new("taskkill")
            .args(["/F", "/PID", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    // Give Windows a moment to release the bind.
    thread::sleep(Duration::from_millis(400));
}

#[cfg(not(windows))]
fn free_dashboard_port() {}

fn candidate_pythons() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        let scripts = PathBuf::from(local)
            .join("Programs")
            .join("Deskline")
            .join("venv")
            .join("Scripts");
        let install_pyw = scripts.join("pythonw.exe");
        let install_py = scripts.join("python.exe");
        // Prefer the installed venv exclusively when present so we never
        // accidentally start a second backend via a global Python.
        if install_pyw.is_file() {
            out.push(install_pyw);
            return out;
        }
        if install_py.is_file() {
            out.push(install_py);
            return out;
        }
    }
    // Dev: project venv next to deskline-desktop/
    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        let project = PathBuf::from(manifest).join("..").join("..");
        out.push(project.join("venv").join("Scripts").join("pythonw.exe"));
        out.push(project.join(".venv").join("Scripts").join("pythonw.exe"));
    }
    if let Ok(p) = which("pythonw.exe") {
        out.push(p);
    }
    if let Ok(p) = which("python.exe") {
        out.push(p);
    }
    out
}

fn which(name: &str) -> Result<PathBuf, ()> {
    let path = std::env::var_os("PATH").ok_or(())?;
    for dir in std::env::split_paths(&path) {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Ok(candidate);
        }
    }
    Err(())
}

fn project_workdir() -> Option<PathBuf> {
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        let install = PathBuf::from(local).join("Programs").join("Deskline");
        if install.join("deskline").is_dir() || install.join("venv").is_dir() {
            return Some(install);
        }
    }
    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        let root = PathBuf::from(manifest).join("..").join("..");
        let root = root.canonicalize().ok()?;
        if root.join("deskline").is_dir() {
            return Some(root);
        }
    }
    None
}

fn spawn_backend() -> Result<(Child, bool), String> {
    if port_open() && is_our_backend() {
        return Err("already_running".into());
    }

    let pythons = candidate_pythons();
    let workdir = project_workdir();
    let mut last_err = String::from("no python found");

    for python in pythons {
        if !python.is_file() {
            continue;
        }
        let mut cmd = Command::new(&python);
        cmd.args(["-m", "deskline", "--no-browser", "--no-tray"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());

        if let Some(ref wd) = workdir {
            cmd.current_dir(wd);
            cmd.env("PYTHONPATH", wd);
            cmd.env("PYTHONNOUSERSITE", "1");
        }

        // Avoid flashing a console window on Windows
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        match cmd.spawn() {
            Ok(child) => return Ok((child, true)),
            Err(e) => last_err = format!("{}: {e}", python.display()),
        }
    }
    Err(last_err)
}

fn stop_backend(state: &BackendState) {
    if !state.we_started {
        return;
    }
    if let Ok(mut guard) = state.child.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[tauri::command]
fn backend_url() -> String {
    DASHBOARD_URL.to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut we_started = false;
    let mut child_slot: Option<Child> = None;

    if port_open() && !is_our_backend() {
        eprintln!(
            "Deskline: port {PORT} is occupied by a foreign/old server — reclaiming it"
        );
        free_dashboard_port();
    }

    if !(port_open() && is_our_backend()) {
        match spawn_backend() {
            Ok((child, started)) => {
                we_started = started;
                child_slot = Some(child);
            }
            Err(e) if e == "already_running" => {}
            Err(e) => {
                eprintln!("Deskline backend start failed: {e}");
            }
        }
    }

    if !wait_for_server(Duration::from_secs(30)) {
        eprintln!("Deskline server did not become ready on {DASHBOARD_URL}");
    } else if !is_our_backend() {
        eprintln!(
            "Deskline: server on {DASHBOARD_URL} is not the local-python edition — UI may be stale"
        );
    }

    let state = BackendState {
        child: Mutex::new(child_slot),
        we_started,
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(state)
        .invoke_handler(tauri::generate_handler![backend_url])
        .setup(|app| {
            let url = DASHBOARD_URL.parse().expect("valid dashboard url");
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url))
                .title("Deskline")
                .inner_size(1280.0, 840.0)
                .min_inner_size(900.0, 600.0)
                .center()
                .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Deskline desktop")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<BackendState>() {
                    stop_backend(&state);
                }
            }
        });
}
