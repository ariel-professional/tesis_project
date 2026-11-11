from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from tesis_domain_extensions.contracts.common import (
    NormalizedText,
    Slug,
    StrictModel,
)
from tesis_domain_extensions.contracts.results import ExactFraction

RelLevel = Literal["A", "E", "I", "O", "U", "X"]
ObjectiveStatus = Literal[
    "conclusive", "inconclusive", "not_applicable", "not_calculated", "invalid"
]


class ObjectiveDefinition(StrictModel):
    id: Slug
    version: Literal["1"]
    name: NormalizedText
    summary: NormalizedText
    decision_question: NormalizedText
    classification: Literal["criterion", "indicator"]
    direction: Literal["maximize", "minimize"]
    direction_mode: Literal["fixed", "per_instance"] = "fixed"
    repeatable_input: bool = False
    unit: NormalizedText
    formula: NormalizedText
    scope: Literal["case", "prescribed_adjacencies"]
    limitations: list[NormalizedText] = Field(min_length=1)
    required_inputs: list[Slug] = Field(min_length=1)
    evidence: list[NormalizedText] = Field(min_length=1)


class ObjectiveReference(StrictModel):
    id: Slug
    version: Literal["1"]


class ObjectiveSnapshot(StrictModel):
    definition: ObjectiveDefinition


class RetainedLayoutsResult(StrictModel):
    objective_id: Slug
    objective_version: Literal["1"]
    status: ObjectiveStatus
    compatible_layout_count: int | None = Field(default=None, ge=0)
    base_layout_count: int | None = Field(default=None, ge=0)
    fraction: ExactFraction | None = None
    unit: NormalizedText
    direction: Literal["maximize", "minimize"]
    diagnostics: list[NormalizedText] = Field(default_factory=list)
    limitations: list[NormalizedText] = Field(default_factory=list)


class RelLevelResult(StrictModel):
    objective_id: Slug
    objective_version: Literal["1"]
    level: Literal["A", "E", "I", "O"]
    status: ObjectiveStatus
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)
    fraction: ExactFraction
    guaranteed_pairs: list[tuple[Slug, Slug]]
    pending_pairs: list[tuple[Slug, Slug]]
    unit: NormalizedText
    direction: Literal["maximize", "minimize"]
    diagnostics: list[NormalizedText] = Field(default_factory=list)
    limitations: list[NormalizedText] = Field(default_factory=list)


class FlowContribution(StrictModel):
    first_station_id: Slug
    second_station_id: Slug
    forward_quantity: Decimal
    reverse_quantity: Decimal | None = None
    total: Decimal


class CapturedFlowResult(StrictModel):
    objective_id: Literal["captured-adjacency-flow"]
    objective_version: Literal["1"]
    status: ObjectiveStatus
    total: Decimal | None = None
    unit: NormalizedText
    horizon: NormalizedText
    directed: bool
    direction: Literal["maximize", "minimize"]
    contributions: list[FlowContribution] = Field(default_factory=list)
    diagnostics: list[NormalizedText] = Field(default_factory=list)
    limitations: list[NormalizedText] = Field(default_factory=list)


class AdjacencyValueContribution(StrictModel):
    first_station_id: Slug
    second_station_id: Slug
    forward_value: Decimal
    reverse_value: Decimal | None = None
    total: Decimal


class AdjacencyValueResult(StrictModel):
    objective_id: Slug
    objective_version: Literal["1"]
    matrix_id: Slug
    status: ObjectiveStatus
    total: Decimal | None = None
    unit: NormalizedText
    reference_period: NormalizedText | None = None
    directed: bool
    direction: Literal["maximize", "minimize"]
    contributions: list[AdjacencyValueContribution] = Field(default_factory=list)
    diagnostics: list[NormalizedText] = Field(default_factory=list)
    limitations: list[NormalizedText] = Field(default_factory=list)


class AdjacencyFinding(StrictModel):
    first_station_id: Slug
    second_station_id: Slug
    cause: Literal[
        "safety",
        "cross_contamination",
        "noise",
        "temperature",
        "privacy",
        "interference",
        "process",
    ]
    explanation: NormalizedText
    provenance: NormalizedText
    policy: Literal["warn"]


class RelRequirement(StrictModel):
    first_station_id: Slug
    second_station_id: Slug
    level: RelLevel
    reason: NormalizedText
    provenance: NormalizedText

    @model_validator(mode="before")
    @classmethod
    def canonical_pair(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        first = value.get("first_station_id")
        second = value.get("second_station_id")
        if first == second:
            raise ValueError("una relación REL no puede ser reflexiva")
        if isinstance(first, str) and isinstance(second, str) and first > second:
            return {**value, "first_station_id": second, "second_station_id": first}
        return value


class RelMatrix(StrictModel):
    requirements: list[RelRequirement] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_pairs(self) -> RelMatrix:
        pairs = [(item.first_station_id, item.second_station_id) for item in self.requirements]
        if len(pairs) != len(set(pairs)):
            raise ValueError("la matriz REL no puede repetir pares")
        return self


class FlowEntry(StrictModel):
    from_station_id: Slug
    to_station_id: Slug
    # JSON Schema intentionally admits both JSON numbers and decimal strings.
    # The field-level exception keeps that public contract valid even when a
    # parent before-validator makes nested validation re-enter Python mode.
    quantity: Decimal = Field(ge=0, strict=False)

    @model_validator(mode="after")
    def valid_pair(self) -> FlowEntry:
        if self.from_station_id == self.to_station_id:
            raise ValueError("el flujo no puede ser reflexivo")
        return self


def _canonicalize_undirected_matrix(value: Any) -> Any:
    if not isinstance(value, dict) or value.get("directed") is not False:
        return value
    entries = value.get("entries")
    if not isinstance(entries, list):
        return value
    canonical_entries: list[Any] = []
    for entry in entries:
        if isinstance(entry, dict):
            first = entry.get("from_station_id")
            second = entry.get("to_station_id")
            canonical_entries.append(
                {
                    **entry,
                    "from_station_id": second,
                    "to_station_id": first,
                }
                if isinstance(first, str) and isinstance(second, str) and first > second
                else entry
            )
            continue
        first = getattr(entry, "from_station_id", None)
        second = getattr(entry, "to_station_id", None)
        canonical_entries.append(
            entry.model_copy(update={"from_station_id": second, "to_station_id": first})
            if isinstance(first, str)
            and isinstance(second, str)
            and first > second
            and hasattr(entry, "model_copy")
            else entry
        )
    return {**value, "entries": canonical_entries}


class FlowMatrix(StrictModel):
    unit: NormalizedText
    horizon: NormalizedText
    provenance: NormalizedText
    directed: bool
    entries: list[FlowEntry] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def canonicalize_undirected_entries(cls, value: Any) -> Any:
        return _canonicalize_undirected_matrix(value)

    @model_validator(mode="after")
    def unique_entries(self) -> FlowMatrix:
        keys = [(item.from_station_id, item.to_station_id) for item in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("la matriz de flujo no puede repetir celdas")
        if not self.directed and any(a > b for a, b in keys):
            raise ValueError("una matriz no dirigida debe usar pares canónicos")
        return self


class AdjacencyValueEntry(StrictModel):
    from_station_id: Slug
    to_station_id: Slug
    value: Decimal = Field(strict=False)

    @field_validator("value", mode="before")
    @classmethod
    def reject_binary_float(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("el valor debe ser un decimal exacto, no un float")
        return value

    @model_validator(mode="after")
    def valid_pair(self) -> AdjacencyValueEntry:
        if self.from_station_id == self.to_station_id:
            raise ValueError("un valor de adyacencia no puede ser reflexivo")
        return self


class AdjacencyValueMatrix(StrictModel):
    id: Annotated[Slug, Field(max_length=48)]
    name: NormalizedText
    description: NormalizedText
    direction: Literal["maximize", "minimize"]
    unit: NormalizedText
    reference_period: NormalizedText | None = None
    provenance: NormalizedText
    directed: bool
    entries: list[AdjacencyValueEntry] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def canonicalize_undirected_entries(cls, value: Any) -> Any:
        return _canonicalize_undirected_matrix(value)

    @model_validator(mode="after")
    def unique_entries(self) -> AdjacencyValueMatrix:
        keys = [(item.from_station_id, item.to_station_id) for item in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("la matriz de valor de adyacencia no puede repetir celdas")
        if not self.directed and any(a > b for a, b in keys):
            raise ValueError("una matriz no dirigida debe usar pares canónicos")
        return self


class UndesiredAdjacency(StrictModel):
    first_station_id: Slug
    second_station_id: Slug
    cause: Literal[
        "safety",
        "cross_contamination",
        "noise",
        "temperature",
        "privacy",
        "interference",
        "process",
    ]
    explanation: NormalizedText
    provenance: NormalizedText
    policy: Literal["forbidden", "warn"]

    @model_validator(mode="before")
    @classmethod
    def canonical_pair(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        first = value.get("first_station_id")
        second = value.get("second_station_id")
        if first == second:
            raise ValueError("una adyacencia inconveniente no puede ser reflexiva")
        if isinstance(first, str) and isinstance(second, str) and first > second:
            return {**value, "first_station_id": second, "second_station_id": first}
        return value


class ParetoDifference(StrictModel):
    objective_id: Slug
    preferred_case_id: Slug
    preferred_value: ExactFraction | str
    other_case_id: Slug
    other_value: ExactFraction | str


class ParetoClassification(StrictModel):
    status: Literal["conclusive", "inconclusive"]
    objective_refs: list[Slug]
    dominated: bool | None
    pareto_optimal: bool | None
    dominated_by_case_ids: list[Slug] = Field(default_factory=list)
    differences: list[ParetoDifference] = Field(default_factory=list)
