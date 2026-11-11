import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, Field, StrictBool, StrictInt, StrictStr, model_validator

from tesis_proyect.models.base import (
    CandidateJsonValue,
    JsonValue,
    LargeNonNegativeInteger,
    NfcString,
    StrictModel,
    json_size,
)
from tesis_proyect.models.config import GeneratorFamily, GeneratorParameters, RelativePath
from tesis_proyect.models.enums import DOMAIN_ERROR_CODES, ErrorCode, StageId

_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_EXPERIMENT_RE = re.compile(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?\Z")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\Z")


def _hash(value: str) -> str:
    if not _HASH_RE.fullmatch(value):
        raise ValueError("expected sha256:<64 lowercase hex>")
    return value


def _experiment_id(value: str) -> str:
    if not _EXPERIMENT_RE.fullmatch(value):
        raise ValueError("invalid experiment ID")
    return value


def _run_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError("invalid run UUID") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("run ID must be a canonical lowercase UUID v4")
    return value


def _timestamp(value: str) -> str:
    if not _TIMESTAMP_RE.fullmatch(value):
        raise ValueError("timestamp must use RFC 3339 UTC milliseconds")
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    return value


def _token(value: str) -> str:
    if not _TOKEN_RE.fullmatch(value):
        raise ValueError("invalid producer token")
    return value


Hash = Annotated[StrictStr, AfterValidator(_hash)]
ExperimentId = Annotated[StrictStr, AfterValidator(_experiment_id)]
RunId = Annotated[StrictStr, AfterValidator(_run_id)]
Timestamp = Annotated[StrictStr, AfterValidator(_timestamp)]
Token = Annotated[StrictStr, AfterValidator(_token)]
Vertex = Annotated[StrictInt, Field(ge=1)]
Edge = tuple[Vertex, Vertex]


class ArtifactRef(StrictModel):
    path: RelativePath
    sha256: Hash
    size_bytes: LargeNonNegativeInteger


class ProducerRef(StrictModel):
    id: Token
    version: Token


class Cancellation(StrictModel):
    requested_at: Timestamp
    origin: Literal["cli"]
    reason: Annotated[NfcString, Field(max_length=512)] | None


class StructuredError(StrictModel):
    schema_version: Literal["1.0.0"]
    code: ErrorCode
    domain_error_code: Annotated[StrictInt, Field(ge=1, le=63)] | None
    message: Annotated[NfcString, Field(min_length=1, max_length=512)]
    recoverable: StrictBool
    details: dict[str, JsonValue]
    stage: StageId | None

    @model_validator(mode="after")
    def validate_mapping_and_details(self) -> "StructuredError":
        if self.domain_error_code != DOMAIN_ERROR_CODES.get(self.code):
            raise ValueError("domain_error_code does not match code")
        if (
            len(self.details) > 32
            or _json_depth(self.details) > 4
            or json_size(self.details) > 65_536
        ):
            raise ValueError("error details exceed their public bound")
        return self


class Diagnostic(StrictModel):
    code: ErrorCode
    domain_error_code: Annotated[StrictInt, Field(ge=1, le=63)] | None
    message: Annotated[NfcString, Field(min_length=1, max_length=512)]
    edge_index: Annotated[StrictInt, Field(ge=0)] | None
    edge: CandidateJsonValue | None

    @model_validator(mode="after")
    def validate_mapping(self) -> "Diagnostic":
        if self.domain_error_code != DOMAIN_ERROR_CODES.get(self.code):
            raise ValueError("domain_error_code does not match code")
        return self


class AttemptMetrics(StrictModel):
    duration_ms: Annotated[StrictInt, Field(ge=0)]
    worker_duration_ms: Annotated[StrictInt, Field(ge=0)] | None
    candidates_examined: LargeNonNegativeInteger | None
    peak_memory_bytes: LargeNonNegativeInteger | None
    producer: ProducerRef | None


class InlineMetadata(StrictModel):
    kind: Literal["inline"]


class FileMetadata(StrictModel):
    kind: Literal["file"]
    path: RelativePath
    sha256: Hash
    size_bytes: LargeNonNegativeInteger


class GeneratorMetadata(StrictModel):
    kind: Literal["generator"]
    family: GeneratorFamily
    generator_version: Literal["builtin-v1"]
    seed: Annotated[StrictInt, Field(ge=0, le=9_223_372_036_854_775_807)]
    parameters: GeneratorParameters

    @model_validator(mode="after")
    def validate_family_parameters(self) -> "GeneratorMetadata":
        from tesis_proyect.models.config import _GENERATOR_PARAMETER_TYPES

        if not isinstance(self.parameters, _GENERATOR_PARAMETER_TYPES[self.family]):
            raise ValueError("generator metadata parameters do not match family")
        return self


SourceMetadata = Annotated[
    InlineMetadata | FileMetadata | GeneratorMetadata,
    Field(discriminator="kind"),
]


StructuredError.model_rebuild()
Diagnostic.model_rebuild()


def _json_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0
