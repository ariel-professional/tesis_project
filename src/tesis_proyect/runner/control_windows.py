"""Windows named-pipe backend for local run control."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from contextlib import suppress

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.models.protocols import ControlRequest, ControlResponse
from tesis_proyect.runner.control_protocol import (
    decode_control,
    encode_control,
    validate_control_response,
)


class WindowsControlServer:
    def __init__(
        self,
        endpoint: str,
        handler: Callable[[ControlRequest], ControlResponse],
        max_bytes: int,
    ) -> None:
        self.endpoint = endpoint
        self.handler = handler
        self.max_bytes = max_bytes
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._failure: BaseException | None = None
        self._listener: object | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._serve, name="run-control", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=2) or self._failure is not None:
            self.close()
            raise OperationalError(
                ErrorCode.RUN_CONTROL_UNAVAILABLE, "Run control could not start."
            ) from self._failure

    def close(self) -> None:
        self._stop.set()
        if self._listener is not None:
            try:
                import win32file  # type: ignore[import-untyped]

                handle = win32file.CreateFile(
                    self.endpoint,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )
                win32file.CloseHandle(handle)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _serve(self) -> None:
        import pywintypes  # type: ignore[import-untyped]
        import win32file
        import win32pipe  # type: ignore[import-untyped]

        try:
            while not self._stop.is_set():
                handle = win32pipe.CreateNamedPipe(
                    self.endpoint,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
                    1,
                    self.max_bytes,
                    self.max_bytes,
                    0,
                    _windows_security_attributes(),
                )
                self._listener = handle
                try:
                    _verify_windows_pipe_dacl(handle)
                    self._ready.set()
                    try:
                        win32pipe.ConnectNamedPipe(handle, None)
                    except pywintypes.error:
                        if self._stop.is_set():
                            break
                        raise
                    if self._stop.is_set():
                        break
                    payload = _windows_read_line(handle, self.max_bytes)
                    request = decode_control(payload, ControlRequest, self.max_bytes)
                    win32file.WriteFile(
                        handle, encode_control(self.handler(request), self.max_bytes)
                    )
                    win32file.FlushFileBuffers(handle)
                    win32pipe.DisconnectNamedPipe(handle)
                finally:
                    win32file.CloseHandle(handle)
        except BaseException as exc:
            if not self._stop.is_set():
                self._failure = exc
        finally:
            self._ready.set()


def _windows_security_attributes() -> object:
    import ntsecuritycon  # type: ignore[import-untyped]
    import pywintypes
    import win32api  # type: ignore[import-untyped]
    import win32security  # type: ignore[import-untyped]

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    current = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    system = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
    admins = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid, None)
    acl = win32security.ACL()
    access = ntsecuritycon.GENERIC_READ | ntsecuritycon.GENERIC_WRITE
    for sid in (current, system, admins):
        acl.AddAccessAllowedAce(win32security.ACL_REVISION, access, sid)
    descriptor = win32security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorDacl(True, acl, False)
    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    return attributes


def _verify_windows_pipe_dacl(handle: object) -> None:
    import win32api
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_QUERY)
    current = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    system = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
    admins = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid, None)
    descriptor = win32security.GetSecurityInfo(
        handle,
        win32security.SE_KERNEL_OBJECT,
        win32security.DACL_SECURITY_INFORMATION,
    )
    acl = descriptor.GetSecurityDescriptorDacl()
    allowed = (current, system, admins)
    if acl is None or acl.GetAceCount() != 3:
        raise OperationalError(ErrorCode.RUN_CONTROL_UNAVAILABLE, "Named pipe DACL is invalid.")
    for index in range(acl.GetAceCount()):
        sid = acl.GetAce(index)[2]
        if not any(str(sid) == str(expected) for expected in allowed):
            raise OperationalError(ErrorCode.RUN_CONTROL_UNAVAILABLE, "Named pipe DACL is invalid.")


def _windows_read_line(handle: object, max_bytes: int) -> bytes:
    import win32file

    payload = bytearray()
    while not payload.endswith(b"\n") and len(payload) <= max_bytes:
        _, chunk = win32file.ReadFile(handle, min(4096, max_bytes + 1 - len(payload)))
        if not chunk:
            break
        payload.extend(chunk)
    return bytes(payload)


def send_windows_control(
    endpoint: str,
    request: ControlRequest,
    connect_timeout_ms: int,
    response_timeout_ms: int,
    max_bytes: int,
) -> ControlResponse:
    import win32file
    import win32pipe

    try:
        deadline = time.monotonic() + connect_timeout_ms / 1000
        while True:
            try:
                win32pipe.WaitNamedPipe(endpoint, max(1, int((deadline - time.monotonic()) * 1000)))
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.01)
        handle = win32file.CreateFile(
            endpoint,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None,
        )
        try:
            win32file.WriteFile(handle, encode_control(request, max_bytes))
            payload = _windows_read_with_timeout(handle, max_bytes, response_timeout_ms)
            return validate_control_response(
                request, decode_control(payload, ControlResponse, max_bytes)
            )
        finally:
            win32file.CloseHandle(handle)
    except Exception as exc:
        raise OperationalError(
            ErrorCode.RUN_CONTROL_UNAVAILABLE, "Run control is unavailable."
        ) from exc


def _windows_read_with_timeout(handle: object, max_bytes: int, timeout_ms: int) -> bytes:
    import win32file

    completed = threading.Event()
    payload: list[bytes] = []
    failures: list[BaseException] = []

    def read() -> None:
        try:
            payload.append(_windows_read_line(handle, max_bytes))
        except BaseException as exc:
            failures.append(exc)
        finally:
            completed.set()

    thread = threading.Thread(target=read, name="run-control-read", daemon=True)
    thread.start()
    if not completed.wait(timeout_ms / 1000):
        cancel = getattr(win32file, "CancelIoEx", None)
        if cancel is not None:
            with suppress(Exception):
                cancel(handle, None)
        raise OperationalError(ErrorCode.RUN_CONTROL_UNAVAILABLE, "Run control response timed out.")
    if failures:
        raise failures[0]
    return payload[0]
