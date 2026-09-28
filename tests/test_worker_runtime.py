"""Tests for the worker single-instance lock and duplicate-log suppression."""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tradingagents.dataflows.a_stock.worker_runtime import (
    AlreadyRunning,
    InstanceLock,
    log_handlers,
)

REPO_ROOT = str(Path(__file__).resolve().parents[1])

_HOLDER_SCRIPT = (
    "import sys, time\n"
    "sys.path.insert(0, {root!r})\n"
    "from tradingagents.dataflows.a_stock.worker_runtime import InstanceLock\n"
    "InstanceLock({name!r}, lock_dir={lock_dir!r}).acquire()\n"
    "print('held', flush=True)\n"
    "time.sleep(60)\n"
)


def _spawn_holder(name: str, lock_dir: Path) -> subprocess.Popen:
    """Start a separate process holding the lock and wait until it has it."""
    script = _HOLDER_SCRIPT.format(root=REPO_ROOT, name=name, lock_dir=str(lock_dir))
    proc = subprocess.Popen(
        [sys.executable, "-c", script], stdout=subprocess.PIPE, text=True
    )
    assert proc.stdout.readline().strip() == "held"
    return proc


def _holder_pid(lock_dir: Path, name: str) -> int:
    """PID recorded in the lock file — the real interpreter, not the launcher.

    A venv ``python.exe`` on Windows is a launcher that re-execs the actual
    interpreter as a child, so ``Popen.pid`` and the lock holder differ.
    """
    text = (lock_dir / f".{name}.lock").read_text().strip()
    match = re.search(r"\d+", text)
    assert match, f"no pid recorded in lock file: {text!r}"
    return int(match.group())


def test_lock_released_on_normal_exit(tmp_path):
    """Releasing (or process exit) frees the lock for the next start."""
    first = InstanceLock("rel", lock_dir=tmp_path)
    first.acquire()
    first._release()

    second = InstanceLock("rel", lock_dir=tmp_path)
    second.acquire()
    second._release()


def test_other_process_is_refused(tmp_path):
    """A separate process holding the lock makes the next start exit loudly."""
    proc = _spawn_holder("x", tmp_path)
    try:
        with pytest.raises(AlreadyRunning) as exc:
            InstanceLock("x", lock_dir=tmp_path).acquire()
        # The message names the holder so an operator can find the process.
        assert f"(pid {_holder_pid(tmp_path, 'x')})" in str(exc.value)
    finally:
        proc.kill()
        proc.wait(timeout=15)


def test_lock_released_when_holder_dies(tmp_path):
    """A hard kill must never leave a stale lock blocking the next start."""
    proc = _spawn_holder("y", tmp_path)
    holder = _holder_pid(tmp_path, "y")
    try:
        # SIGKILL the process itself: no atexit hook, no chance to clean up.
        subprocess.run(
            ["taskkill", "/F", "/PID", str(holder)],
            capture_output=True,
            check=False,
        )
        proc.wait(timeout=15)

        lock = InstanceLock("y", lock_dir=tmp_path)
        lock.acquire()  # must not raise
        lock._release()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=15)


def test_log_handlers_drops_stream_when_stderr_is_the_log(tmp_path):
    """`... >> worker.log 2>&1` must not double every line."""
    log = tmp_path / "worker.log"
    saved = sys.stderr

    with open(log, "a") as fh:
        sys.stderr = fh  # emulate the shell redirect
        try:
            handlers = log_handlers(str(log))
        finally:
            sys.stderr = saved

    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.FileHandler)
    handlers[0].close()


def test_log_handlers_keeps_stream_for_a_separate_stderr(tmp_path):
    log = tmp_path / "worker.log"
    saved = sys.stderr

    with open(tmp_path / "err.txt", "a") as fh:
        sys.stderr = fh
        try:
            handlers = log_handlers(str(log))
        finally:
            sys.stderr = saved

    assert len(handlers) == 2
    for h in handlers:
        h.close()


def test_log_handlers_keeps_stream_without_redirect(tmp_path):
    """With stderr elsewhere (a terminal, or pytest's capture): keep both."""
    handlers = log_handlers(str(tmp_path / "worker.log"))
    try:
        assert len(handlers) == 2
    finally:
        for h in handlers:
            h.close()
