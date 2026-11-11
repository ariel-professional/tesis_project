"""Shared strict framing for the local control channel."""

import json

from pydantic import BaseModel

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.models.protocols import ControlRequest, ControlResponse


def encode_control(message: ControlRequest | ControlResponse, max_bytes: int) -> bytes:
    payload = (
        json.dumps(
            message.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    if len(payload) > max_bytes:
        raise OperationalError(ErrorCode.RUN_CONTROL_UNAVAILABLE, "Control message is too large.")
    return payload


def decode_control[T: BaseModel](payload: bytes, model: type[T], max_bytes: int) -> T:
    if len(payload) > max_bytes or not payload.endswith(b"\n") or b"\n" in payload[:-1]:
        raise OperationalError(ErrorCode.RUN_CONTROL_UNAVAILABLE, "Control framing is invalid.")
    try:
        return model.model_validate_json(payload[:-1])
    except ValueError as exc:
        raise OperationalError(
            ErrorCode.RUN_CONTROL_UNAVAILABLE, "Control message is invalid."
        ) from exc


def validate_control_response(
    request: ControlRequest, response: ControlResponse
) -> ControlResponse:
    if response.request_id != request.request_id or response.run_id != request.run_id:
        raise OperationalError(
            ErrorCode.RUN_CONTROL_UNAVAILABLE, "Control response identity mismatch."
        )
    return response
