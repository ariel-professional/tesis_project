from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, StrictInt, StrictStr
from pydantic.main import BaseModel

SCHEMA_VERSION = "1.0.0"
_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")
_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REFERENCE_PATTERN = re.compile(r"^[0-9a-f]{8,64}$")
_RUN_REFERENCE_PATTERN = re.compile(r"^[0-9a-f]{8,32}$")
_TIMESTAMP_PATTERN = re.compile(
    r"^(?:[0-9]{4})-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{3}Z$"
)
_LARGE_INTEGER_PATTERN = re.compile(r"^[1-9][0-9]*$")
MAX_SAFE_JSON_INTEGER = 9_007_199_254_740_991


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


def normalize_nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def non_empty(value: str) -> str:
    if not value:
        raise ValueError("el valor no puede estar vacío")
    return value


def valid_slug(value: str) -> str:
    if _SLUG_PATTERN.fullmatch(value) is None:
        raise ValueError("el valor debe ser un slug en minúsculas de hasta 64 caracteres")
    return value


def valid_hash(value: str) -> str:
    if _HASH_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be a sha256 hash")
    return value


def valid_digest(value: str) -> str:
    if _DIGEST_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be a lower-case SHA-256 digest")
    return value


def valid_reference(value: str) -> str:
    if _REFERENCE_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be a lower-case hexadecimal reference of length 8..64")
    return value


def valid_run_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError("value must be a canonical UUID v4") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("value must be a canonical lower-case UUID v4")
    return value


def valid_run_reference(value: str) -> str:
    if _RUN_REFERENCE_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be a compact hexadecimal run reference of length 8..32")
    return value


def valid_timestamp(value: str) -> str:
    if _TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise ValueError("value must be an RFC 3339 UTC timestamp with millisecond precision")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ValueError("value must contain a valid calendar date and time") from exc
    return value


NormalizedText = Annotated[
    StrictStr,
    AfterValidator(normalize_nfc),
    AfterValidator(non_empty),
]
Slug = Annotated[
    StrictStr,
    AfterValidator(normalize_nfc),
    AfterValidator(valid_slug),
]
Hash = Annotated[StrictStr, AfterValidator(valid_hash)]
DomainExperimentId = Annotated[StrictStr, AfterValidator(valid_digest)]
DomainExperimentReference = Annotated[StrictStr, AfterValidator(valid_reference)]
RunId = Annotated[StrictStr, AfterValidator(valid_run_id)]
RunReference = Annotated[StrictStr, AfterValidator(valid_run_reference)]
Timestamp = Annotated[StrictStr, AfterValidator(valid_timestamp)]


class DomainRef(StrictModel):
    id: Slug
    version: NormalizedText


class MeasureDefinition(StrictModel):
    id: Slug
    name: NormalizedText
    definition: NormalizedText


class ProducerRef(StrictModel):
    id: NormalizedText
    version: NormalizedText


class CoreRunAttempt(StrictModel):
    """A durable attempt to execute one projected case in CORE."""

    core_run_id: RunId
    status: Literal["created", "running", "completed", "failed", "cancelled"]


def validate_large_integer(value: object) -> int | str:
    if isinstance(value, bool):
        raise ValueError("value must be a non-negative integer")
    if isinstance(value, int):
        if not 0 <= value <= MAX_SAFE_JSON_INTEGER:
            raise ValueError("integer form must fit the safe JSON integer range")
        return value
    if isinstance(value, str) and _LARGE_INTEGER_PATTERN.fullmatch(value):
        if int(value) <= MAX_SAFE_JSON_INTEGER:
            raise ValueError("string form is reserved for large integers")
        return value
    raise ValueError("value must be a non-negative integer or canonical decimal string")


LargeNonNegativeInteger = Annotated[
    StrictInt | StrictStr,
    AfterValidator(validate_large_integer),
]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
PositiveInt = Annotated[StrictInt, Field(ge=1)]


def large_non_negative_integer(value: int) -> int | str:
    """Return the canonical public wire representation for a non-negative integer."""

    if value < 0:
        raise ValueError("value must be non-negative")
    return value if value <= MAX_SAFE_JSON_INTEGER else str(value)
