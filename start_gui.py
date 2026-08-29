"""
TradingAgents 桌面 GUI 一键启动脚本
同时启动 Python 后端和 Rust GUI 前端
"""

import os
import signal
import socket
import subprocess
import sys
import time
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_PORT = 8420
BACKEND_HOST = "127.0.0.1"

# ── Python discovery ──────────────────────────────────────────────────────────
# `python` may not be on PATH in the user's shell; probe common locations.
_PY_CANDIDATES = [
    sys.executable,  # the interpreter running this script
    "python",
    "python3",
    r"C:\Python311\python.exe",
    r"C:\Python310\python.exe",
    r"C:\Program Files\Python311\python.exe",
    r"C:\Program Files\Python310\python.exe",
    r"C:\Users\Aren\AppData\Local\Programs\Python\Python311\python.exe",
    r"C:\Users\Aren\.local\bin\python3.11.exe",
]


def find_python() -> str | None:
    """Return a python executable that can import granian (or at least exists)."""
    seen: set[str] = set()
    for cand in _PY_CANDIDATES:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            r = subprocess.run(
                [cand, "-c", "import granian"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0:
            return cand
    # Fallback: first candidate that merely exists
    for cand in _PY_CANDIDATES:
        if cand and os.path.isfile(cand):
            return cand
    return None


def find_gui_binary() -> Path | None:
    """Locate the compiled GUI binary (Tauri app under target/ or src-tauri/target/)."""
    candidates = [
        # Workspace-root target (newest build from cargo build --release at tradingagents_gui/)
        ROOT / "tradingagents_gui" / "target" / "release" / "tradingagents-gui.exe",
        ROOT / "tradingagents_gui" / "target" / "release" / "tradingagents-gui",
        # Legacy src-tauri target
        ROOT / "tradingagents_gui" / "src-tauri" / "target" / "release" / "tradingagents-gui.exe",
        ROOT / "tradingagents_gui" / "src-tauri" / "target" / "release" / "tradingagents-gui",
        # Debug builds
        ROOT / "tradingagents_gui" / "target" / "debug" / "tradingagents-gui.exe",
        ROOT / "tradingagents_gui" / "target" / "debug" / "tradingagents-gui",
        ROOT / "tradingagents_gui" / "src-tauri" / "target" / "debug" / "tradingagents-gui.exe",
        ROOT / "tradingagents_gui" / "src-tauri" / "target" / "debug" / "tradingagents-gui",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def build_gui_assets() -> bool:
    """Rebuild frontend assets (dist/) and the Tauri binary if stale.

    Tauri 2 release builds may embed frontend assets at compile time, so we
    must rebuild the binary whenever dist/ changes to ensure the latest code
    is served.
    """
    gui_dir = ROOT / "tradingagents_gui"
    if not (gui_dir / "package.json").exists():
        return False

    # Step 1: vite build (fast, ~12s)
    print("Rebuilding frontend assets (npm install + vite build)...")
    for cmd_str in ("npm install", "npm run build"):
        print(f"  -> {cmd_str}")
        r = subprocess.run(cmd_str, cwd=str(gui_dir), shell=True)
        if r.returncode != 0:
            print(f"Build step failed: {cmd_str}")
            return False

    dist_index = gui_dir / "dist" / "index.html"
    if not dist_index.exists():
        return False

    # Step 2: Check if the existing binary is older than dist/index.html.
    # If so, rebuild the Tauri binary to embed the latest frontend.
    gui_bin = find_gui_binary()
    if gui_bin:
        bin_mtime = gui_bin.stat().st_mtime
        dist_mtime = dist_index.stat().st_mtime
        bin_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(bin_mtime))
        dist_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(dist_mtime))
        print(f"  Binary time:  {bin_time}  ({gui_bin})")
        print(f"  dist/ time:   {dist_time}")
        if bin_mtime >= dist_mtime:
            print(f"Binary is up to date.")
            return True

    print("Binary is older than frontend assets. Rebuilding Tauri binary...")
    cmd_str = "npm run tauri build -- --no-bundle"
    print(f"  -> {cmd_str}")
    r = subprocess.run(cmd_str, cwd=str(gui_dir), shell=True)
    if r.returncode != 0:
        print(f"Tauri build step failed: {cmd_str}")
        return False
    return find_gui_binary() is not None


def build_gui() -> bool:
    """Full Tauri build (Rust + frontend) — used only when no binary exists."""
    gui_dir = ROOT / "tradingagents_gui"
    if not (gui_dir / "package.json").exists():
        return False
    print("Building GUI (first build takes a few minutes)...")
    for cmd_str in ("npm install", "npm run build", "npm run tauri build -- --no-bundle"):
        print(f"  -> {cmd_str}")
        r = subprocess.run(cmd_str, cwd=str(gui_dir), shell=True)
        if r.returncode != 0:
            print(f"Build step failed: {cmd_str}")
            return False
    return find_gui_binary() is not None


def wait_for_backend(host: str, port: int, timeout: float = 30.0) -> bool:
    """Wait until the FastAPI backend accepts TCP connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((host, port))
            sock.close()
            return True
        except (ConnectionRefusedError, OSError, TimeoutError):
            time.sleep(0.5)
    return False


def print_backend_output(proc: subprocess.Popen):
    """Print backend stdout/stderr in a background thread for debugging."""
    for line in iter(proc.stdout.readline, b""):
        try:
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                print(f"  [backend] {text}")
        except Exception:
            pass


def start_backend(python_bin: str) -> subprocess.Popen:
    """Start the Python backend using granian ASGI server."""
    print(f"Starting Python backend with granian on {BACKEND_HOST}:{BACKEND_PORT} ...")
    proc = subprocess.Popen(
        [
            python_bin, "-B", "-m", "granian",
            "--interface", "asgi",
            "--host", BACKEND_HOST,
            "--port", str(BACKEND_PORT),
            "tradingagents_api.server:app",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


def main():
    procs: list[subprocess.Popen] = []

    def cleanup(*_args):
        for p in procs:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # ── 1. Start Python FastAPI backend ──────────────────────────────
    python_bin = find_python()
    if python_bin is None:
        print("ERROR: Could not find a working Python with granian installed.")
        print("       Install granian or make sure python is on PATH:")
        print("  pip install granian")
        cleanup()
        sys.exit(1)
    print(f"Using Python: {python_bin}")
    backend = start_backend(python_bin)
    procs.append(backend)

    # Print backend output in background for debugging
    t = threading.Thread(target=print_backend_output, args=(backend,), daemon=True)
    t.start()

    if not wait_for_backend(BACKEND_HOST, BACKEND_PORT):
        print("ERROR: Backend failed to start within 30s.")
        rc = backend.poll()
        if rc is not None:
            print(f"Backend exited with code {rc}")
        else:
            print("Backend is still running but not accepting connections.")
        print("Try running manually:")
        print("  python -m granian --interface asgi --host 127.0.0.1 --port 8420 tradingagents_api.server:app")
        cleanup()
        sys.exit(1)
    print("Backend is ready!")

    # ── 2. Rebuild frontend + binary if needed, then Start GUI ──────
    if not build_gui_assets():
        print("Build failed. Build it manually:")
        print("  cd tradingagents_gui")
        print("  npm install && npm run tauri build -- --no-bundle")
        cleanup()
        sys.exit(1)

    gui_bin = find_gui_binary()
    if gui_bin is None:
        print("GUI binary still not found after build.")
        cleanup()
        sys.exit(1)

    print(f"Starting GUI: {gui_bin}")
    print(f"  Binary timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(gui_bin.stat().st_mtime))}")

    # Clear WebView2 cache to prevent stale content
    import shutil
    webview_cache = Path(os.environ.get("LOCALAPPDATA", "")) / "TradingAgents" / "ebwebview" / "Cache"
    if webview_cache.exists():
        try:
            shutil.rmtree(webview_cache, ignore_errors=True)
            print("  Cleared WebView2 cache")
        except Exception:
            pass

    env = os.environ.copy()
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = "--disable-http-cache"

    gui = subprocess.Popen(
        [str(gui_bin)],
        cwd=str(ROOT),
        env=env,
    )
    procs.append(gui)

    # ── 3. Wait for GUI to exit, then clean up ──────────────────────
    try:
        gui.wait()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
        print("Done.")


if __name__ == "__main__":
    main()
