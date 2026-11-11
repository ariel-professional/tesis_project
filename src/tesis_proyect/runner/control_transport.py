"""Platform-selecting facade for local run control."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from types import TracebackType

from tesis_proyect.models.protocols import ControlRequest, ControlResponse
from tesis_proyect.runner.control_endpoint import control_endpoint
from tesis_proyect.runner.control_unix import UnixControlServer, send_unix_control
from tesis_proyect.runner.control_windows import WindowsControlServer, send_windows_control


class ControlServer:
    def __init__(
        self,
        workspace: Path,
        run_id: str,
        handler: Callable[[ControlRequest], ControlResponse],
        *,
        max_bytes: int,
    ) -> None:
        self.endpoint = control_endpoint(workspace, run_id)
        self.handler = handler
        backend = WindowsControlServer if os.name == "nt" else UnixControlServer
        self._backend = backend(self.endpoint, self.handler, max_bytes)

    def start(self) -> None:
        self._backend.start()

    def close(self) -> None:
        self._backend.close()

    def __enter__(self) -> ControlServer:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def send_control(
    workspace: Path,
    request: ControlRequest,
    *,
    connect_timeout_ms: int,
    response_timeout_ms: int,
    max_bytes: int,
) -> ControlResponse:
    endpoint = control_endpoint(workspace, request.run_id)
    sender = send_windows_control if os.name == "nt" else send_unix_control
    return sender(endpoint, request, connect_timeout_ms, response_timeout_ms, max_bytes)
