from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field, StrictInt, StrictStr, model_validator

from tesis_domain_extensions.contracts.common import (
    DomainExperimentId,
    DomainRef,
    Hash,
    LargeNonNegativeInteger,
    NormalizedText,
    ProducerRef,
    RunId,
    Slug,
    StrictModel,
    Timestamp,
)
from tesis_domain_extensions.contracts.config import ExecutionConfig
from tesis_domain_extensions.contracts.results import DomainLimitation
from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
    DomainRunManifestV2,
    GenerationMetricsV2,
    LayoutCaseResultV2,
    LayoutDesignResultV2,
    SingleRowExperimentProjectionV2,
    SingleRowExperimentSummaryV2,
    SingleRowFacilityLayoutConfigV2,
    SingleRowFacilityLayoutResultV2,
    SingleRowProjectionContextV2,
    SingleRowRunSummaryV2,
    StationV2,
)
from tesis_domain_extensions.domains.single_row_facility_layout.objectives.contracts import (
    ObjectiveSnapshot,
)


class SingleRowDomainRefV21(DomainRef):
    id: Literal["single-row-facility-layout"]
    version: Literal["2.1.0"]


class ExecutionConfigV21(ExecutionConfig):
    mode: Literal["standard", "high_performance"] = "standard"


class SingleRowFacilityLayoutConfigV21(SingleRowFacilityLayoutConfigV2):
    schema_version: Literal["2.1.0"]  # type: ignore[assignment]
    domain: SingleRowDomainRefV21  # type: ignore[assignment]
    execution: ExecutionConfigV21


class SingleRowProjectionContextV21(SingleRowProjectionContextV2):
    schema_version: Literal["2.1.0"]  # type: ignore[assignment]


class SingleRowExperimentProjectionV21(SingleRowExperimentProjectionV2):
    schema_version: Literal["2.1.0"]  # type: ignore[assignment]
    domain_config: SingleRowFacilityLayoutConfigV21
    projection_context: SingleRowProjectionContextV21


class SingleRowExperimentSummaryV21(SingleRowExperimentSummaryV2):
    schema_version: Literal["2.1.0"]  # type: ignore[assignment]
    domain: SingleRowDomainRefV21  # type: ignore[assignment]


class SingleRowRunSummaryV21(SingleRowRunSummaryV2):
    schema_version: Literal["2.1.0"]  # type: ignore[assignment]
    domain: SingleRowDomainRefV21  # type: ignore[assignment]
    mode: Literal["standard", "high_performance"] = "standard"
    fast_counters: dict[str, int] | None = None


class SignedExactFractionV21(StrictModel):
    numerator: int
    denominator: int = Field(gt=0)


class LayoutCaseResultV21(LayoutCaseResultV2):
    core_run_id: RunId | None = None  # type: ignore[assignment]
    counting_producer: ProducerRef
    scientific_status: Literal["conclusive", "inconclusive"]
    criteria_vector: dict[str, SignedExactFractionV21] = Field(default_factory=dict)


class LayoutDesignResultV21(LayoutDesignResultV2):
    cases: list[LayoutCaseResultV21]  # type: ignore[assignment]


class SingleRowFacilityLayoutResultV21(SingleRowFacilityLayoutResultV2):
    schema_version: Literal["2.1.0"]  # type: ignore[assignment]
    domain: SingleRowDomainRefV21  # type: ignore[assignment]
    designs: list[LayoutDesignResultV21]  # type: ignore[assignment]


class FastDesignSummaryV21(StrictModel):
    design_id: Slug
    design_title: NormalizedText
    theoretical_combinations: LargeNonNegativeInteger
    valid_case_count: LargeNonNegativeInteger
    invalid_combination_count: LargeNonNegativeInteger
    base_case_id: DomainExperimentId
    base_layout_count: LargeNonNegativeInteger | None
    pareto_case_count: LargeNonNegativeInteger
    frontier_index: str | None
    order_indexes: dict[str, str]


class FastResultSummaryV21(StrictModel):
    schema_version: Literal["2.1.0"]
    domain: SingleRowDomainRefV21
    study_id: Slug
    study_title: NormalizedText
    study_description: NormalizedText | None
    stations: list[StationV2]
    execution: dict[str, object]
    generation: GenerationMetricsV2
    objective_snapshots: list[ObjectiveSnapshot]
    designs: list[FastDesignSummaryV21]
    limitations: list[DomainLimitation]
    files: dict[str, dict[str, int | str]]


class DomainRunManifestV21(DomainRunManifestV2):
    schema_version: Literal["2.1.0"]  # type: ignore[assignment]
    domain: SingleRowDomainRefV21  # type: ignore[assignment]
    mode: Literal["standard", "high_performance"] = "standard"
    fast_counters: dict[str, int] | None = None
    fast_artifacts: dict[str, dict[str, int | str]] | None = None
    failure_reason: Literal["interrupted"] | None = None


def normalize_archived_fast_config(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("archived configuration must be an object")
    execution = value.get("execution")
    if (
        not isinstance(execution, dict)
        or execution.get("strategy") != "direct_exact_checkpointed"
        or "mode" in execution
    ):
        raise ValueError("configuration does not use the archived direct exact strategy")
    normalized = dict(value)
    normalized_execution = dict(execution)
    del normalized_execution["strategy"]
    normalized_execution["mode"] = "high_performance"
    normalized["execution"] = normalized_execution
    return normalized


class ArchivedFastExperimentProjectionV21(StrictModel):
    """Read-only compatibility for projections from the archived 2.1 runner."""

    schema_version: Literal["2.1.0"]
    domain_experiment_id: DomainExperimentId
    created_at: Timestamp
    domain_config: SingleRowFacilityLayoutConfigV21
    projection_context: SingleRowProjectionContextV21
    objective_snapshots: list[ObjectiveSnapshot]

    @model_validator(mode="before")
    @classmethod
    def normalize_archived_identity(cls, value: object) -> object:
        if not isinstance(value, dict):
            raise ValueError("archived projection must be an object")
        config = value.get("domain_config")
        context = value.get("projection_context")
        if not isinstance(config, dict) or not isinstance(context, dict):
            raise ValueError("archived projection is missing its configuration or context")
        canonical = json.dumps(
            config, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        if hashlib.sha256(canonical).hexdigest() != value.get("domain_experiment_id"):
            raise ValueError("archived projection identity does not match its configuration")
        normalized = dict(value)
        normalized["domain_config"] = normalize_archived_fast_config(config)
        normalized_context = dict(context)
        if normalized_context.get("schema_version") != "2.0.0":
            raise ValueError("archived projection context has an unsupported version")
        normalized_context["schema_version"] = "2.1.0"
        normalized["projection_context"] = normalized_context
        return normalized


class ArchivedFastArtifactV21(StrictModel):
    """Artifact metadata emitted by the archived checkpointed 2.1 runner."""

    path: StrictStr
    schema_id: StrictStr
    media_type: StrictStr
    encoding: StrictStr
    compression: StrictStr
    records: StrictInt = Field(ge=0)
    stored_size_bytes: StrictInt = Field(ge=0)
    uncompressed_size_bytes: StrictInt = Field(ge=0)
    sha256: Hash


class ArchivedFastChunkV21(StrictModel):
    sequence: StrictInt = Field(ge=0)
    cursor_start: StrictInt = Field(ge=0)
    cursor_end: StrictInt = Field(ge=0)
    cases: ArchivedFastArtifactV21
    forests: ArchivedFastArtifactV21


class ArchivedFastDomainRunManifestV21(StrictModel):
    """Read-only compatibility for direct exact runs created by the old 2.1 runner.

    That runner stored its complete evidence in per-run chunks and did not create
    CORE attempts, so the deletion inventory must treat it as having no CORE refs.
    """

    schema_version: Literal["2.1.0"]
    domain_run_id: RunId
    domain_experiment_id: DomainExperimentId
    domain: SingleRowDomainRefV21
    display_name: NormalizedText
    status: Literal["created", "running", "completed", "failed", "cancelled"]
    generator_cursor: LargeNonNegativeInteger
    generation: GenerationMetricsV2
    strategy: Literal["direct_exact_checkpointed"]
    checkpoint_sequence: StrictInt = Field(ge=0)
    chunks: list[ArchivedFastChunkV21]
    result: ArchivedFastArtifactV21
    created_at: Timestamp
    updated_at: Timestamp
    mode: Literal["high_performance"] = "high_performance"
    active_duration_ms: int = Field(default=0, ge=0)

    @property
    def cases(self) -> list[object]:
        return []
