from __future__ import annotations

from typing import Literal

from tesis_domain_extensions.contracts.common import (
    LargeNonNegativeInteger,
    MeasureDefinition,
    NonNegativeInt,
    NormalizedText,
    ProducerRef,
    Slug,
    StrictModel,
)


class ExactFraction(StrictModel):
    numerator: LargeNonNegativeInteger
    denominator: LargeNonNegativeInteger


class MeasureValue(StrictModel):
    measure: MeasureDefinition
    value: ExactFraction


class RouteCount(StrictModel):
    value: LargeNonNegativeInteger | None
    method: ProducerRef | None
    exact_value: LargeNonNegativeInteger | None
    reference_value: LargeNonNegativeInteger | None
    counting_convention: Literal["undirected_paths_reverse_identified"]
    comparison_status: Literal["match", "mismatch", "not_applicable"] | None


class DomainDiagnostic(StrictModel):
    core_code: NormalizedText
    message: NormalizedText
    affected_locations: list[Slug]


class TechnicalMetrics(StrictModel):
    duration_ms: NonNegativeInt
    candidates_examined: LargeNonNegativeInteger


class DomainLimitation(StrictModel):
    code: NormalizedText
    message: NormalizedText
