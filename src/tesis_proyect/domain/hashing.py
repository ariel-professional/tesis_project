from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from tesis_proyect.models.config import ExperimentConfig


def _normalize(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats are forbidden")
        raise ValueError("floats are forbidden in canonical hash inputs")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {_normalize(str(key)): _normalize(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize(item) for item in value]
    if value is None or isinstance(value, (bool, int)):
        return value
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", by_alias=True)
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _opaque_candidate(value: Any) -> Any:
    """Validate JSON shape while preserving candidate strings and keys byte-for-byte."""
    if isinstance(value, float):
        raise ValueError("floats are forbidden in canonical hash inputs")
    if isinstance(value, Mapping):
        return {str(key): _opaque_candidate(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_opaque_candidate(item) for item in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def sha256_wire(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def run_config_hash(config: ExperimentConfig) -> str:
    raw = config.model_dump(mode="json", by_alias=True)
    normalized = _normalize(raw)
    if raw["source"]["kind"] == "inline":
        normalized["source"]["edges"] = _opaque_candidate(raw["source"]["edges"])
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256_wire(payload)


def instance_hash(n: int, edges: Sequence[tuple[int, int]]) -> str:
    identity = {"edges": [list(edge) for edge in edges], "n": n, "vertex_base": 1}
    return sha256_wire(canonical_json_bytes(identity))
