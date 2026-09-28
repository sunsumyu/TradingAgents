"""Runtime concerns shared by the long-running A-share worker processes.

Two problems recur with these daemons, and both live here rather than being
copy-pasted into each worker:

**Double instances.** Two recorders would insert every snapshot twice — each
sweep stamps its own microsecond ``ts``, so ``ON CONFLICT (ts, ticker, stream)``
cannot dedupe them — and two importers would fight over the same progress files
while quadrupling BaoStock's request rate, which is how the IP ban got extended
last time. An OS advisory lock is the right primitive rather than a PID file:
the kernel releases it when the process dies, so a hard kill can never leave a
stale lock that blocks the next start. The PID goes in the file for diagnostics
only.

**Doubled log lines.** Each worker logs through both a StreamHandler and a
FileHandler. When the launcher redirects stderr into the worker's own log file
(``... >> snapshot_recorder.log 2>&1``), both handlers point at that file and
every line lands twice. Detecting the overlap and dropping the stream handler
keeps the log readable without changing how the worker is started.
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
from pathlib import Path

LOCK_OFFSET = 1024  # lock a byte past the PID text so other processes can read it

if os.name == "nt":  # pragma: no cover - platform split
    import msvcrt

    def _try_lock(fh) -> bool:
        fh.seek(LOCK_OFFSET)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(fh) -> None:
        fh.seek(LOCK_OFFSET)
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:  # pragma: no cover - platform split
    import fcntl

    def _try_lock(fh) -> bool:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(fh) -> None:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass


class AlreadyRunning(RuntimeError):
    """Raised when another process already holds the instance lock."""


class InstanceLock:
    """Context manager holding an exclusive lock on ``<name>.lock``.

    ``lock_dir`` defaults to this package's directory, where the workers keep
    their progress and cache files. Raises AlreadyRunning (naming the holding
    PID when readable) instead of blocking, so the caller exits loudly rather
    than silently duplicating work.
    """

    def __init__(self, name: str, lock_dir: str | os.PathLike | None = None):
        base = Path(lock_dir) if lock_dir else Path(__file__).parent
        self.path = base / f".{name}.lock"
        self._fh = None

    def __enter__(self) -> "InstanceLock":
        self.acquire()
        return self

    def acquire(self) -> None:
        """Take the lock, or raise AlreadyRunning. Released at process exit.

        For callers whose critical section is the rest of the process life
        rather than a ``with`` block; ``__enter__`` is the same call.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+")
        if not _try_lock(self._fh):
            holder = self._read_holder()
            self._fh.close()
            self._fh = None
            raise AlreadyRunning(
                f"another instance already holds {self.path.name}"
                + (f" (pid {holder})" if holder else "")
            )
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(str(os.getpid()))
        self._fh.flush()
        atexit.register(self._release)

    def _read_holder(self) -> str:
        try:
            return self.path.read_text().strip()
        except OSError:
            return ""

    def _release(self) -> None:
        if self._fh is None:
            return
        _unlock(self._fh)
        try:
            self._fh.close()
        except OSError:
            pass
        self._fh = None

    def __exit__(self, *exc) -> None:
        self._release()


def _same_file(fh, path: str) -> bool:
    try:
        a = os.fstat(fh.fileno())
        b = os.stat(path)
    except (OSError, ValueError, AttributeError):
        return False
    return (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino)


def log_handlers(log_file: str) -> list[logging.Handler]:
    """Handlers for a worker's ``basicConfig``, without duplicate file writes.

    Returns console + file handlers normally. When stderr already *is*
    ``log_file`` (the ``2>&1`` redirect case) the console handler is dropped,
    since the file handler already writes every line there.
    """
    file_handler = logging.FileHandler(log_file, mode="a")
    if _same_file(sys.stderr, log_file):
        return [file_handler]
    return [logging.StreamHandler(), file_handler]
