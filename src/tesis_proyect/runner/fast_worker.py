from __future__ import annotations

import json
import multiprocessing
import re
import struct
from contextlib import suppress
from multiprocessing.connection import Connection
from time import monotonic
from typing import Any, cast
from uuid import uuid4

from tesis_proyect.engines.exact import count_closed_form

_HEADER = struct.Struct(">I")
_DEFAULT_MAX_FRAME_BYTES = 65_536
_DECIMAL_CHUNK_DIGITS = 1_000
_COUNT_CHUNK_BYTES = 60_000
_DECIMAL_PATTERN = re.compile(r"^(?:0|[1-9][0-9]*)$")


class FastWorkerError(RuntimeError):
    """The persistent exact-count worker did not complete a valid request."""


class FastWorkerCancelled(FastWorkerError):
    """Cancellation was observed between worker requests."""


def _json_frame(message: dict[str, object], max_frame_bytes: int) -> bytes:
    payload = json.dumps(message, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(payload) + _HEADER.size > max_frame_bytes:
        raise FastWorkerError("worker frame exceeds configured byte limit")
    return _HEADER.pack(len(payload)) + payload


def _decode_frame(frame: bytes, max_frame_bytes: int) -> dict[str, Any]:
    if len(frame) > max_frame_bytes or len(frame) < _HEADER.size:
        raise FastWorkerError("worker frame has an invalid length")
    size = _HEADER.unpack_from(frame)[0]
    if size != len(frame) - _HEADER.size:
        raise FastWorkerError("worker frame length prefix does not match payload")
    try:
        value = json.loads(frame[_HEADER.size :])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FastWorkerError("worker returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise FastWorkerError("worker response must be an object")
    return value


def _integer_to_decimal(value: int) -> str:
    if value == 0:
        return "0"
    base = 10**_DECIMAL_CHUNK_DIGITS
    chunks: list[int] = []
    while value:
        value, remainder = divmod(value, base)
        chunks.append(remainder)
    return str(chunks[-1]) + "".join(
        f"{chunk:0{_DECIMAL_CHUNK_DIGITS}d}" for chunk in reversed(chunks[:-1])
    )


def _decimal_to_integer(digits: str) -> int:
    if _DECIMAL_PATTERN.fullmatch(digits) is None:
        raise FastWorkerError("worker returned a non-canonical decimal count")
    value = 0
    for offset in range(0, len(digits), _DECIMAL_CHUNK_DIGITS):
        chunk = digits[offset : offset + _DECIMAL_CHUNK_DIGITS]
        value = value * (10 ** len(chunk)) + int(chunk)
    return value


def _worker_main(channel: Connection, max_frame_bytes: int) -> None:
    try:
        while True:
            try:
                request = _decode_frame(channel.recv_bytes(max_frame_bytes), max_frame_bytes)
            except (EOFError, OSError):
                return
            if request == {"kind": "shutdown"}:
                return
            request_id = request.get("request_id")
            try:
                if not isinstance(request_id, str):
                    raise ValueError("request_id must be a string")
                n, c, m = request.get("n"), request.get("c"), request.get("m")
                if any(type(value) is not int for value in (n, c, m)):
                    raise TypeError("n, c, and m must be integers")
                count = count_closed_form(cast(int, n), cast(int, c), cast(int, m))
                digits = _integer_to_decimal(count)
                chunk_size = min(_COUNT_CHUNK_BYTES, max_frame_bytes - 256)
                pieces = [
                    digits[index : index + chunk_size]
                    for index in range(0, len(digits), chunk_size)
                ]
                for index, piece in enumerate(pieces):
                    channel.send_bytes(
                        _json_frame(
                            {
                                "request_id": request_id,
                                "index": index,
                                "total": len(pieces),
                                "digits": piece,
                            },
                            max_frame_bytes,
                        )
                    )
            except Exception as exc:
                if not isinstance(request_id, str):
                    return
                channel.send_bytes(
                    _json_frame(
                        {"request_id": request_id, "error": f"{type(exc).__name__}: {exc}"},
                        max_frame_bytes,
                    )
                )
    finally:
        channel.close()


class FastCountingWorker:
    """One spawned worker reused for exact counts during a single domain run."""

    def __init__(
        self,
        *,
        timeout_ms: int,
        max_frame_bytes: int = _DEFAULT_MAX_FRAME_BYTES,
        is_cancel_requested: Any = None,
    ) -> None:
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError("timeout_ms must be a positive integer")
        if type(max_frame_bytes) is not int or max_frame_bytes < 512:
            raise ValueError("max_frame_bytes must be at least 512")
        self.timeout_ms = timeout_ms
        self.max_frame_bytes = max_frame_bytes
        self.is_cancel_requested = is_cancel_requested or (lambda: False)
        self._process: Any = None
        self._channel: Any = None

    def __enter__(self) -> FastCountingWorker:
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=True)
        process = context.Process(target=_worker_main, args=(child, self.max_frame_bytes))
        process.start()
        child.close()
        self._process = process
        self._channel = parent
        return self

    def __exit__(self, *_: object) -> None:
        process, channel = self._process, self._channel
        self._process = None
        self._channel = None
        if channel is not None:
            with suppress(BrokenPipeError, EOFError, OSError):
                channel.send_bytes(_json_frame({"kind": "shutdown"}, self.max_frame_bytes))
            channel.close()
        if process is not None:
            process.join(timeout=1)
            if process.is_alive():
                process.terminate()
                process.join()

    def count(self, n: int, c: int, m: int) -> int:
        channel = self._channel
        process = self._process
        if channel is None or process is None:
            raise FastWorkerError("worker must be started before requesting a count")
        if self.is_cancel_requested():
            raise FastWorkerCancelled("run cancellation observed before worker request")
        request_id = str(uuid4())
        channel.send_bytes(
            _json_frame(
                {"request_id": request_id, "n": n, "c": c, "m": m},
                self.max_frame_bytes,
            )
        )
        return _receive_count(
            channel,
            process,
            request_id,
            monotonic() + self.timeout_ms / 1000,
            self.max_frame_bytes,
        )


def _receive_count(
    channel: Connection,
    process: Any,
    request_id: str,
    deadline: float,
    max_frame_bytes: int,
) -> int:
    parts: list[str] = []
    expected_total: int | None = None
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise FastWorkerError("exact-count worker timed out")
        if not channel.poll(min(remaining, 0.1)):
            if not process.is_alive():
                raise FastWorkerError("exact-count worker exited before replying")
            continue
        response = _decode_frame(channel.recv_bytes(max_frame_bytes), max_frame_bytes)
        _, total, digits = _validate_count_fragment(response, request_id, len(parts))
        if expected_total is None:
            expected_total = total
        if total != expected_total:
            raise FastWorkerError("worker changed fragment count during response")
        parts.append(digits)
        if len(parts) == expected_total:
            return _decimal_to_integer("".join(parts))


def _validate_count_fragment(
    response: dict[str, Any], request_id: str, expected_index: int
) -> tuple[int, int, str]:
    if response.get("request_id") != request_id:
        raise FastWorkerError("worker response request_id mismatch")
    if "error" in response:
        raise FastWorkerError(str(response["error"]))
    index, total, digits = (
        response.get("index"),
        response.get("total"),
        response.get("digits"),
    )
    if (
        type(index) is not int
        or type(total) is not int
        or total < 1
        or index != expected_index
        or not isinstance(digits, str)
    ):
        raise FastWorkerError("worker returned invalid count fragments")
    return index, total, digits
