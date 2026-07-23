//! Deskline desktop shell (Tauri).
//! Starts the local Python tracker/API and shows the dashboard in a native window.

use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

const PORT: u16 = 8787;
const DASHBOARD_URL: &str = "http://127.0.0.1:8787";
const EXPECTED_EDITION: &str = "local-python";
const WEBVIEW2_DOWNLOAD: &str =
    "https://developer.microsoft.com/microsoft-edge/webview2/";

struct BackendState {
    child: Mutex<Option<Child>>,
    we_started: bool,
}

fn data_dir() -> PathBuf {
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        return PathBuf::from(local).join("Deskline");
    }
    PathBuf::from(".").join("Deskline")
}

fn log_path() -> PathBuf {
    data_dir().join("desktop.log")
}

fn log_line(msg: &str) {
    let _ = fs::create_dir_all(data_dir());
    let stamp = chrono_like_stamp();
    let line = format!("[{stamp}] {msg}\n");
    eprintln!("{msg}");
    if let Ok(mut f) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path())
    {
        let _ = f.write_all(line.as_bytes());
    }
}

fn chrono_like_stamp() -> String {
    // Local wall time without extra crate dependency.
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("unix:{secs}")
}

#[cfg(windows)]
fn show_error_dialog(title: &str, message: &str) {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;

    #[link(name = "user32")]
    extern "system" {
        fn MessageBoxW(
            hwnd: *mut core::ffi::c_void,
            text: *const u16,
            caption: *const u16,
            flags: u32,
        ) -> i32;
    }

    const MB_ICONERROR: u32 = 0x0000_0010;
    const MB_OK: u32 = 0x0000_0000;

    fn wide(s: &str) -> Vec<u16> {
        OsStr::new(s).encode_wide().chain(Some(0)).collect()
    }

    let text = wide(message);
    let caption = wide(title);
    unsafe {
        MessageBoxW(
            std::ptr::null_mut(),
            text.as_ptr(),
            caption.as_ptr(),
            MB_OK | MB_ICONERROR,
        );
    }
}

#[cfg(not(windows))]
fn show_error_dialog(title: &str, message: &str) {
    eprintln!("{title}: {message}");
}

fn webview2_hint() -> &'static str {
    #[cfg(windows)]
    {
        let keys = [
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        ];
        for key in keys {
            if let Ok(hkey) = winreg_open(key) {
                if hkey {
                    return "";
                }
            }
        }
        return "\n\nMicrosoft Edge WebView2 Runtime was not detected. Install it from:\nhttps://developer.microsoft.com/microsoft-edge/webview2/";
    }
    #[cfg(not(windows))]
    {
        ""
    }
}

#[cfg(windows)]
fn winreg_open(subkey: &str) -> Result<bool, ()> {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;
    use std::ptr;

    #[link(name = "advapi32")]
    extern "system" {
        fn RegOpenKeyExW(
            hkey: isize,
            sub_key: *const u16,
            options: u32,
            sam: u32,
            result: *mut isize,
        ) -> u32;
        fn RegCloseKey(hkey: isize) -> u32;
    }

    const HKEY_LOCAL_MACHINE: isize = 0x8000_0002u32 as isize;
    const KEY_READ: u32 = 0x20019;

    let wide: Vec<u16> = OsStr::new(subkey).encode_wide().chain(Some(0)).collect();
    let mut handle: isize = 0;
    let status = unsafe {
        RegOpenKeyExW(
            HKEY_LOCAL_MACHINE,
            wide.as_ptr(),
            0,
            KEY_READ,
            &mut handle,
        )
    };
    if status == 0 {
        unsafe {
            RegCloseKey(handle);
        }
        Ok(true)
    } else {
        let _ = ptr::null::<()>();
        Ok(false)
    }
}

fn fail_and_exit(reason: &str) -> ! {
    let log = log_path();
    let hint = webview2_hint();
    let message = format!(
        "{reason}{hint}\n\nLog file:\n{}\n\nWebView2 (if needed):\n{WEBVIEW2_DOWNLOAD}",
        log.display()
    );
    log_line(&format!("FATAL: {reason}"));
    show_error_dialog("Deskline — cannot start", &message);
    std::process::exit(1);
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
        log_line(&format!("freeing port {PORT} by stopping PID {pid}"));
        let _ = Command::new("taskkill")
            .args(["/F", "/PID", &pid.to_string()])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
    }
    thread::sleep(Duration::from_millis(400));
}

#[cfg(not(windows))]
fn free_dashboard_port() {}

fn current_exe_dir() -> Option<PathBuf> {
    std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
}

fn candidate_frozen_backends() -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(dir) = current_exe_dir() {
        out.push(dir.join("Deskline.exe"));
        out.push(dir.join("backend").join("Deskline.exe"));
    }
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        let install = PathBuf::from(local).join("Programs").join("Deskline");
        out.push(install.join("Deskline.exe"));
        out.push(install.join("backend").join("Deskline.exe"));
    }
    out
}

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
    if let Some(dir) = current_exe_dir() {
        out.push(dir.join("venv").join("Scripts").join("pythonw.exe"));
        out.push(dir.join("venv").join("Scripts").join("python.exe"));
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
    if let Some(dir) = current_exe_dir() {
        if dir.join("deskline").is_dir() || dir.join("venv").is_dir() {
            return Some(dir);
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

fn open_log_stdio() -> (Stdio, Stdio) {
    let _ = fs::create_dir_all(data_dir());
    match OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path())
    {
        Ok(f) => {
            let f2 = f.try_clone().unwrap_or_else(|_| {
                OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(log_path())
                    .expect("log reopen")
            });
            (Stdio::from(f), Stdio::from(f2))
        }
        Err(_) => (Stdio::null(), Stdio::null()),
    }
}

fn apply_no_window(cmd: &mut Command) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let _ = cmd;
}

fn spawn_frozen(exe: &Path) -> Result<Child, String> {
    let (stdout, stderr) = open_log_stdio();
    let mut cmd = Command::new(exe);
    cmd.args(["--no-browser", "--no-tray"])
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr);
    if let Some(parent) = exe.parent() {
        cmd.current_dir(parent);
    }
    apply_no_window(&mut cmd);
    cmd.spawn()
        .map_err(|e| format!("{}: {e}", exe.display()))
}

fn spawn_python(python: &Path, workdir: Option<&Path>) -> Result<Child, String> {
    let (stdout, stderr) = open_log_stdio();
    let mut cmd = Command::new(python);
    cmd.args(["-m", "deskline", "--no-browser", "--no-tray"])
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr);
    if let Some(wd) = workdir {
        cmd.current_dir(wd);
        cmd.env("PYTHONPATH", wd);
        cmd.env("PYTHONNOUSERSITE", "1");
    }
    apply_no_window(&mut cmd);
    cmd.spawn()
        .map_err(|e| format!("{}: {e}", python.display()))
}

fn spawn_backend() -> Result<(Child, bool), String> {
    if port_open() && is_our_backend() {
        return Err("already_running".into());
    }

    let mut last_err = String::from("no backend found");

    for exe in candidate_frozen_backends() {
        if !exe.is_file() {
            continue;
        }
        log_line(&format!("trying frozen backend {}", exe.display()));
        match spawn_frozen(&exe) {
            Ok(child) => return Ok((child, true)),
            Err(e) => {
                log_line(&format!("frozen backend failed: {e}"));
                last_err = e;
            }
        }
    }

    let workdir = project_workdir();
    for python in candidate_pythons() {
        if !python.is_file() {
            continue;
        }
        log_line(&format!("trying python backend {}", python.display()));
        match spawn_python(&python, workdir.as_deref()) {
            Ok(child) => return Ok((child, true)),
            Err(e) => {
                log_line(&format!("python backend failed: {e}"));
                last_err = e;
            }
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
    log_line("Deskline desktop starting");

    let mut we_started = false;
    let mut child_slot: Option<Child> = None;

    if port_open() && !is_our_backend() {
        log_line(&format!(
            "port {PORT} is occupied by a foreign/old server — reclaiming it"
        ));
        free_dashboard_port();
    }

    if !(port_open() && is_our_backend()) {
        match spawn_backend() {
            Ok((child, started)) => {
                we_started = started;
                child_slot = Some(child);
                log_line("backend process spawned");
            }
            Err(e) if e == "already_running" => {
                log_line("backend already running");
            }
            Err(e) => {
                fail_and_exit(&format!(
                    "Could not start the Deskline tracker backend.\n\n{e}\n\n\
Fix: reinstall Deskline (install.bat) so venv and deskline-desktop.exe are present."
                ));
            }
        }
    }

    if !wait_for_server(Duration::from_secs(30)) {
        fail_and_exit(&format!(
            "Deskline server did not become ready on {DASHBOARD_URL} within 30 seconds.\n\n\
Check that Python dependencies installed correctly, then try again."
        ));
    }

    if !is_our_backend() {
        fail_and_exit(&format!(
            "Something else is answering on {DASHBOARD_URL}, but it is not Deskline \
(local-python edition).\n\nClose other apps using port {PORT} and retry."
        ));
    }

    log_line("backend healthy — opening window");

    let state = BackendState {
        child: Mutex::new(child_slot),
        we_started,
    };

    let app = match tauri::Builder::default()
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
    {
        Ok(app) => app,
        Err(e) => {
            fail_and_exit(&format!(
                "Could not create the Deskline window (WebView2 may be missing).\n\n{e}"
            ));
        }
    };

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = app_handle.try_state::<BackendState>() {
                stop_backend(&state);
            }
        }
    });
}
