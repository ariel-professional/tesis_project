import unicodedata
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    PlainSerializer,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)

MAX_SAFE_JSON_INTEGER = 9_007_199_254_740_991


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def normalize_nfc(value: str) -> str:
    """Normalize contract-semantic text without touching opaque candidate JSON."""
    return unicodedata.normalize("NFC", value)


NfcString = Annotated[StrictStr, AfterValidator(normalize_nfc)]


def _validate_large_integer(value: int | str) -> int | str:
    if isinstance(value, bool):
        raise ValueError("boolean is not a non-negative integer")
    if isinstance(value, int):
        if not 0 <= value <= MAX_SAFE_JSON_INTEGER:
            raise ValueError("integer JSON values must be within the safe range")
        return value
    if not value.isascii() or not value.isdecimal() or value.startswith("0"):
        raise ValueError("large integers must be canonical unsigned decimal strings")
    if int(value) <= MAX_SAFE_JSON_INTEGER:
        raise ValueError("safe integers must use the JSON integer representation")
    return value


type LargeNonNegativeInteger = Annotated[
    StrictInt | StrictStr,
    AfterValidator(_validate_large_integer),
    PlainSerializer(lambda value: value, return_type=int | str),
]

type JsonScalar = StrictBool | StrictInt | StrictStr | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type CandidateJsonScalar = StrictBool | StrictInt | StrictFloat | StrictStr | None
type CandidateJsonValue = (
    CandidateJsonScalar | list[CandidateJsonValue] | dict[str, CandidateJsonValue]
)


def json_size(value: Any) -> int:
    """Return a stable rough size used by bounded public-detail validators."""
    import json

    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
