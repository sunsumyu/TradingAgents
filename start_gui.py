"""
TradingAgents 桌面 GUI 一键启动脚本
同时启动 Python 后端和 Rust GUI 前端

配置从 tradingagents.config 加载（支持环境变量覆盖）。
"""

import os
import signal
import socket
import subprocess
import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tradingagents.config import BACKEND_HOST, BACKEND_PORT, RESULTS_DIR

ROOT = Path(__file__).resolve().parent

# ── Python discovery ──────────────────────────────────────────────────────────
# `python` may not be on PATH in the user's shell; probe common locations.
_PY_CANDIDATES = [
    r"G:\Hermes\hermes-agent\venv\Scripts\python.exe",  # project venv
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


def find_port_holders(port: int) -> list[int]:
    """Return PIDs of processes LISTENING on *port* (via netstat).

    Decodes output with errors='replace' — Chinese Windows emits GBK text
    that crashes UTF-8 text-mode subprocess reads.
    """
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, timeout=10
        ).stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            parts = line.split()
            if parts:
                try:
                    pid = int(parts[-1])
                    if pid > 0 and pid not in pids:
                        pids.append(pid)
                except ValueError:
                    pass
    return pids


def _is_python_process(pid: int) -> bool:
    """True if *pid* belongs to python.exe (safety check before killing)."""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, timeout=10,
        ).stdout.decode("utf-8", errors="replace").strip()
        return bool(out) and "python" in out.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def _port_is_free(host: str, port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((host, port))
        s.close()
        return True
    except OSError:
        return False


def kill_port_holders(host: str, port: int, timeout: float = 15.0) -> bool:
    """Kill leftover python processes holding *port* (granian main + workers).

    granian is multi-process: worker children inherit the listening socket,
    so killing only the parent leaves orphaned workers on the port. We use
    `taskkill /T` to take down the whole process tree.

    Only python.exe processes are killed — anything else holding the port is
    left alone and reported.
    """
    pids = find_port_holders(port)
    if not pids:
        return _port_is_free(host, port)

    print(f"Port {host}:{port} is held by PID(s): {', '.join(map(str, pids))}")
    for pid in pids:
        if not _is_python_process(pid):
            print(f"  PID {pid} is NOT python — leaving it alone.")
            continue
        print(f"  Killing leftover backend process tree (PID {pid})...")
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, timeout=10,
        )

    # Wait for the kernel to actually release the socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_is_free(host, port):
            print(f"Port {port} released.")
            return True
        time.sleep(0.5)

    return _port_is_free(host, port)


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


def wait_port_bindable(host: str, port: int, timeout: float = 210.0) -> bool:
    """Poll until `host:port` can actually be bound.

    On Windows, binding a port that was used moments ago (a previous session's
    connections sitting in TIME_WAIT, or an outbound connection that grabbed it
    as its ephemeral source port) fails with WSAEACCES (os error 10013) — even
    though netstat shows nothing listening. The blockage clears on its own, so
    wait for it before handing the port to granian.
    """
    deadline = time.time() + timeout
    warned = False
    while time.time() < deadline:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((host, port))
            sock.close()
            return True
        except OSError as exc:
            if not warned:
                print(f"Port {host}:{port} is temporarily unavailable ({exc}).")
                print("A previous run's connections are likely still in TIME_WAIT.")
                print(f"Waiting up to {timeout:.0f}s for it to clear ...")
                warned = True
            time.sleep(3)
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
    """Start the Python backend via _start_combined.py (combined vendor + SO_REUSEADDR)."""
    print(f"Starting Python backend with granian on {BACKEND_HOST}:{BACKEND_PORT} (combined vendor) ...")
    # 传递 combined vendor 环境变量
    env = os.environ.copy()
    env["TRADINGAGENTS_MARKET_DATA_VENDOR"] = "combined"
    proc = subprocess.Popen(
        [
            python_bin, "-B",
            str(ROOT / "_start_backend.py"),
            BACKEND_HOST,
            str(BACKEND_PORT),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


def main():
    procs: list[subprocess.Popen] = []

    def cleanup(*_args):
        for p in procs:
            if p.poll() is not None:
                continue
            # taskkill /T kills the whole process tree — granian workers
            # inherit the listening socket and would otherwise survive as
            # orphans still holding the backend port.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                capture_output=True, timeout=10,
            )
            try:
                p.wait(timeout=5)
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
    # Auto-clean leftover backend processes, then start immediately.
    # _start_backend.py uses SO_REUSEADDR to bypass Windows TIME_WAIT,
    # so we no longer need to passively wait for the port to clear.
    kill_port_holders(BACKEND_HOST, BACKEND_PORT)
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

    # ── 1.5. Start hourly kline collector (background) ────────────
    collector_tickers = os.environ.get("HOURLY_COLLECT_TICKERS", "001232")
    if collector_tickers.strip():
        _coll_env = os.environ.copy()
        _coll_env["TRADINGAGENTS_MARKET_DATA_VENDOR"] = "combined"
        collector = subprocess.Popen(
            [python_bin, "-m", "tradingagents.dataflows.a_stock.hourly_collector",
             "--tickers", collector_tickers, "--daemon", "--interval", "1"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=_coll_env,
        )
        procs.append(collector)
        print(f"Hourly collector started for: {collector_tickers}")
        t2 = threading.Thread(target=print_backend_output, args=(collector,), daemon=True)
        t2.start()

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
