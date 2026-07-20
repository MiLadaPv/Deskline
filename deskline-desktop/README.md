# Deskline Desktop (Tauri)

Native Windows window for the local Deskline tracker/dashboard.

## How it works

1. On launch, the Tauri app starts `pythonw -m deskline --no-browser --no-tray` if port `8787` is free.
2. When the API is ready, it opens a native WebView at `http://127.0.0.1:8787`.
3. On quit, if this app started the backend, it stops that process.

Tracker logic stays in Python (FastAPI + SQLite). Tauri is the shell.

## Requirements

- Rust (`cargo`, `rustc`)
- Node.js + npm
- Deskline Python env (project editable install or `%LOCALAPPDATA%\Programs\Deskline\venv`)

## Dev

```powershell
cd D:\Projects\Deskline
pip install -e .

cd deskline-desktop
npm install
npm run dev
```

Or from repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_desktop.ps1
```

## Release build

```powershell
cd deskline-desktop
npm run build
```

Installers land in `deskline-desktop\src-tauri\target\release\bundle\`.
