//! Deskline desktop shell (Tauri).
//! Starts the local Python tracker/API and shows the dashboard in a native window.

use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

const PORT: u16 = 8787;
const DASHBOARD_URL: &str = "http://127.0.0.1:8787";

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

fn candidate_pythons() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        out.push(
            PathBuf::from(local)
                .join("Programs")
                .join("Deskline")
                .join("venv")
                .join("Scripts")
                .join("pythonw.exe"),
        );
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
    if let Ok(manifest) = std::env::var("CARGO_MANIFEST_DIR") {
        let root = PathBuf::from(manifest).join("..").join("..");
        let root = root.canonicalize().ok()?;
        if root.join("deskline").is_dir() {
            return Some(root);
        }
    }
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        let install = PathBuf::from(local).join("Programs").join("Deskline");
        if install.join("deskline").is_dir() || install.join("venv").is_dir() {
            return Some(install);
        }
    }
    None
}

fn spawn_backend() -> Result<(Child, bool), String> {
    if port_open() {
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
        cmd.args([
            "-m",
            "deskline",
            "--no-browser",
            "--no-tray",
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

        if let Some(ref wd) = workdir {
            cmd.current_dir(wd);
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
    let already = port_open();
    let mut we_started = false;
    let mut child_slot: Option<Child> = None;

    if !already {
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
