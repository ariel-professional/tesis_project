from __future__ import annotations

import errno
import os
from pathlib import Path
from threading import RLock, local
from types import TracebackType

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode

_workspace_guard = RLock()
_workspace_locks: dict[Path, RLock] = {}
_workspace_local = local()


class RunExecutionLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: object | None = None

    def acquire(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.is_symlink():
                raise OSError(errno.ELOOP, "Lock path is a symlink.")
            handle = self.path.open("a+b")
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                    os.fsync(handle.fileno())
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(  # type: ignore[attr-defined]
                    handle.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,  # type: ignore[attr-defined]
                )
            self._handle = handle
        except OSError as exc:
            if "handle" in locals():
                handle.close()
            if exc.errno in {errno.EACCES, errno.EAGAIN, 13, 36}:
                raise OperationalError(
                    ErrorCode.RUN_ALREADY_ACTIVE, "Run is already active."
                ) from exc
            raise OperationalError(
                ErrorCode.RUN_LOCK_UNAVAILABLE, "Run lock is unavailable."
            ) from exc

    def release(self) -> None:
        if self._handle is None:
            return
        handle = self._handle
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)  # type: ignore[attr-defined]
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
        finally:
            handle.close()  # type: ignore[attr-defined]
            self._handle = None

    def __enter__(self) -> RunExecutionLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


class WorkspaceWriteLock:
    """Reentrant in-process and exclusive cross-process workspace writer lock."""

    def __init__(self, path: Path) -> None:
        self.path = path.absolute()
        self._thread_lock: RLock | None = None
        self._acquired = False

    def acquire(self) -> None:
        with _workspace_guard:
            thread_lock = _workspace_locks.setdefault(self.path, RLock())
        thread_lock.acquire()
        states = getattr(_workspace_local, "states", None)
        if states is None:
            states = {}
            _workspace_local.states = states
        current = states.get(self.path)
        if current is None:
            file_lock = RunExecutionLock(self.path)
            try:
                file_lock.acquire()
            except BaseException:
                thread_lock.release()
                raise
            states[self.path] = [1, file_lock]
        else:
            current[0] += 1
        self._thread_lock = thread_lock
        self._acquired = True

    def release(self) -> None:
        if not self._acquired or self._thread_lock is None:
            return
        states = _workspace_local.states
        current = states[self.path]
        current[0] -= 1
        if current[0] == 0:
            current[1].release()
            del states[self.path]
        self._thread_lock.release()
        self._thread_lock = None
        self._acquired = False

    def __enter__(self) -> WorkspaceWriteLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


def is_run_active(path: Path) -> bool:
    lock = RunExecutionLock(path)
    try:
        lock.acquire()
    except OperationalError as exc:
        if exc.code == ErrorCode.RUN_ALREADY_ACTIVE:
            return True
        raise
    else:
        lock.release()
        return False
