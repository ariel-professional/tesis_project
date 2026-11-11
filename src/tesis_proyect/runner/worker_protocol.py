from __future__ import annotations

import json
import struct

from pydantic import BaseModel

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode


def encode_frame(message: BaseModel, max_bytes: int) -> bytes:
    payload = message.model_dump_json(by_alias=True).encode("utf-8")
    if len(payload) > max_bytes:
        raise OperationalError(ErrorCode.WORKER_MESSAGE_TOO_LARGE, "Worker message is too large.")
    return struct.pack(">I", len(payload)) + payload


def decode_frame[T: BaseModel](frame: bytes, model: type[T], max_bytes: int) -> T:
    if len(frame) < 4:
        raise OperationalError(ErrorCode.WORKER_PROTOCOL_ERROR, "Worker frame is truncated.")
    declared = struct.unpack(">I", frame[:4])[0]
    if declared > max_bytes:
        raise OperationalError(ErrorCode.WORKER_MESSAGE_TOO_LARGE, "Worker message is too large.")
    payload = frame[4:]
    if len(payload) != declared:
        raise OperationalError(ErrorCode.WORKER_PROTOCOL_ERROR, "Worker frame length is invalid.")
    try:
        decoded = payload.decode("utf-8", errors="strict")
        value = json.loads(
            decoded,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
        return model.model_validate(value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise OperationalError(
            ErrorCode.WORKER_PROTOCOL_ERROR, "Worker message is invalid."
        ) from exc
