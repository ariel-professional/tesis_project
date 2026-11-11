from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StrictBool, StrictInt, StrictStr, model_validator

from tesis_proyect.models.base import JsonValue, StrictModel, normalize_nfc
from tesis_proyect.models.enums import CountingConvention, PersistencePolicy


def _relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("path must be a confined POSIX relative path")
    return value


RelativePath = Annotated[
    StrictStr,
    AfterValidator(normalize_nfc),
    AfterValidator(_relative_path),
]


class InlineSource(StrictModel):
    kind: Literal["inline"]
    edges: list[JsonValue]

    @model_validator(mode="after")
    def reject_floats(self) -> "InlineSource":
        def walk(value: object) -> None:
            if isinstance(value, float):
                raise ValueError("floats are forbidden in inline sources")
            if isinstance(value, list):
                for item in value:
                    walk(item)
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)

        walk(self.edges)
        return self


class FileSource(StrictModel):
    kind: Literal["file"]
    path: RelativePath


class EmptyParameters(StrictModel):
    pass


class EdgeCountParameters(StrictModel):
    edge_count: Annotated[StrictInt, Field(ge=0)]


class MultiplePathsParameters(StrictModel):
    component_edge_lengths: list[Annotated[StrictInt, Field(ge=1)]]


class OutOfRangeParameters(StrictModel):
    direction: Literal["below", "above"]


class CycleParameters(StrictModel):
    cycle_length: Annotated[StrictInt, Field(ge=3)]


GeneratorParameters = (
    EmptyParameters
    | EdgeCountParameters
    | MultiplePathsParameters
    | OutOfRangeParameters
    | CycleParameters
)
GeneratorFamily = Literal[
    "empty",
    "matching",
    "single_path",
    "multiple_paths",
    "invalid_loop",
    "invalid_duplicate",
    "invalid_vertex_out_of_range",
    "invalid_cycle",
    "invalid_degree3",
]

_GENERATOR_PARAMETER_TYPES: dict[str, type[StrictModel]] = {
    "empty": EmptyParameters,
    "matching": EdgeCountParameters,
    "single_path": EdgeCountParameters,
    "multiple_paths": MultiplePathsParameters,
    "invalid_loop": EmptyParameters,
    "invalid_duplicate": EmptyParameters,
    "invalid_vertex_out_of_range": OutOfRangeParameters,
    "invalid_cycle": CycleParameters,
    "invalid_degree3": EmptyParameters,
}


def _validate_generator_bounds(n: int, source: "GeneratorSource") -> None:
    family = source.family
    params = source.parameters
    if family == "matching" and isinstance(params, EdgeCountParameters):
        if params.edge_count > n // 2:
            raise ValueError("matching edge_count exceeds floor(n/2)")
    elif family == "single_path" and isinstance(params, EdgeCountParameters):
        if params.edge_count > n - 1:
            raise ValueError("single_path edge_count exceeds n-1")
    elif family == "multiple_paths" and isinstance(params, MultiplePathsParameters):
        if sum(length + 1 for length in params.component_edge_lengths) > n:
            raise ValueError("multiple_paths components require more than n vertices")
    elif (
        family == "invalid_cycle"
        and isinstance(params, CycleParameters)
        and params.cycle_length > n
    ):
        raise ValueError("cycle_length exceeds n")
    minimum_n = {"invalid_duplicate": 2, "invalid_degree3": 4}.get(family, 1)
    if n < minimum_n:
        raise ValueError(f"{family} requires n >= {minimum_n}")


class GeneratorSource(StrictModel):
    kind: Literal["generator"]
    family: GeneratorFamily
    generator_version: Literal["builtin-v1"]
    seed: Annotated[StrictInt, Field(ge=0, le=9_223_372_036_854_775_807)]
    parameters: GeneratorParameters


Source = Annotated[InlineSource | FileSource | GeneratorSource, Field(discriminator="kind")]


class ExactMethodConfig(StrictModel):
    engine: Literal["auto"]


class ReferenceMethodConfig(StrictModel):
    engine: Literal["bruteforce_python_v1"]


class MethodsConfig(StrictModel):
    exact: ExactMethodConfig
    reference: ReferenceMethodConfig


class IntegerLimits(StrictModel):
    max_n: Annotated[StrictInt, Field(ge=1)]
    reference_max_n: Annotated[StrictInt, Field(ge=1)]
    exact_timeout_ms: Annotated[StrictInt, Field(ge=1)]
    reference_timeout_ms: Annotated[StrictInt, Field(ge=1)]
    cancellation_grace_ms: Annotated[StrictInt, Field(ge=0)]
    control_connect_timeout_ms: Annotated[StrictInt, Field(ge=1)]
    control_response_timeout_ms: Annotated[StrictInt, Field(ge=1)]
    control_max_message_bytes: Annotated[StrictInt, Field(ge=1)]
    input_max_bytes: Annotated[StrictInt, Field(ge=1)]
    event_max_payload_bytes: Annotated[StrictInt, Field(ge=1)]
    worker_max_message_bytes: Annotated[StrictInt, Field(ge=1)]
    runner_log_max_bytes: Annotated[StrictInt, Field(ge=1)]
    runner_log_backup_count: Annotated[StrictInt, Field(ge=0)]


class PersistenceConfig(StrictModel):
    policy: PersistencePolicy
    persist_events: StrictBool = False


class ExperimentConfig(StrictModel):
    schema_version: Literal["1.0.0"]
    n: Annotated[StrictInt, Field(ge=1)]
    source: Source
    methods: MethodsConfig
    integer_limits: IntegerLimits
    persistence: PersistenceConfig
    counting_convention: CountingConvention

    @model_validator(mode="after")
    def validate_cross_fields(self) -> "ExperimentConfig":
        if self.n > self.integer_limits.max_n:
            raise ValueError("n exceeds integer_limits.max_n")
        if not isinstance(self.source, GeneratorSource):
            return self
        family = self.source.family
        params = self.source.parameters
        expected = _GENERATOR_PARAMETER_TYPES[family]
        if not isinstance(params, expected):
            raise ValueError(f"parameters do not match generator family {family}")
        _validate_generator_bounds(self.n, self.source)
        return self


InlineSource.model_rebuild()
