"""Unix-domain-socket backend for local run control."""

from __future__ import annotations

import os
import socket
import threading
from collections.abc import Callable
from pathlib import Path

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.models.protocols import ControlRequest, ControlResponse
from tesis_proyect.runner.control_protocol import (
    decode_control,
    encode_control,
    validate_control_response,
)


class UnixControlServer:
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
        self._listener: socket.socket | None = None

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
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as wake:  # type: ignore[attr-defined]
                    wake.connect(self.endpoint)
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)
        Path(self.endpoint).unlink(missing_ok=True)

    def _serve(self) -> None:
        endpoint = Path(self.endpoint)
        try:
            endpoint.unlink(missing_ok=True)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:  # type: ignore[attr-defined]
                self._listener = listener
                listener.bind(self.endpoint)
                os.chmod(endpoint, 0o600)
                listener.listen(1)
                self._ready.set()
                while not self._stop.is_set():
                    connection, _ = listener.accept()
                    with connection:
                        if self._stop.is_set():
                            break
                        payload = _read_line(connection, self.max_bytes)
                        request = decode_control(payload, ControlRequest, self.max_bytes)
                        connection.sendall(encode_control(self.handler(request), self.max_bytes))
        except BaseException as exc:
            if not self._stop.is_set():
                self._failure = exc
        finally:
            self._ready.set()


def _read_line(connection: socket.socket, max_bytes: int) -> bytes:
    payload = bytearray()
    while not payload.endswith(b"\n"):
        chunk = connection.recv(min(4096, max_bytes + 1 - len(payload)))
        if not chunk:
            break
        payload.extend(chunk)
        if len(payload) > max_bytes:
            break
    return bytes(payload)


def send_unix_control(
    endpoint: str,
    request: ControlRequest,
    connect_timeout_ms: int,
    response_timeout_ms: int,
    max_bytes: int,
) -> ControlResponse:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:  # type: ignore[attr-defined]
            client.settimeout(connect_timeout_ms / 1000)
            client.connect(endpoint)
            client.settimeout(response_timeout_ms / 1000)
            client.sendall(encode_control(request, max_bytes))
            payload = _read_line(client, max_bytes)
            return validate_control_response(
                request, decode_control(payload, ControlResponse, max_bytes)
            )
    except (OSError, OperationalError) as exc:
        raise OperationalError(
            ErrorCode.RUN_CONTROL_UNAVAILABLE, "Run control is unavailable."
        ) from exc
