from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tesis_domain_extensions.catalog import resolve_adapter
from tesis_domain_extensions.contracts.projection import domain_experiment_id
from tesis_domain_extensions.domains.single_row_facility_layout.adapter_v2 import (
    SingleRowFacilityLayoutAdapterV2,
)
from tesis_domain_extensions.domains.single_row_facility_layout.adapter_v21 import (
    SingleRowFacilityLayoutAdapterV21,
)
from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v21 import (
    LayoutCaseResultV21,
    SignedExactFractionV21,
    SingleRowFacilityLayoutConfigV21,
)


def _versioned_payload() -> dict[str, object]:
    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_text(
            encoding="utf-8"
        )
    )
    payload["schema_version"] = "2.1.0"
    payload["domain"]["version"] = "2.1.0"
    return payload


def test_v21_defaults_to_standard_and_dispatches_by_persisted_domain_version() -> None:
    payload = _versioned_payload()
    config = SingleRowFacilityLayoutAdapterV21().parse_config(json.dumps(payload).encode("utf-8"))

    assert config.execution.mode == "standard"
    adapter = resolve_adapter(json.dumps(payload).encode())
    assert isinstance(adapter, SingleRowFacilityLayoutAdapterV21)
    assert isinstance(
        adapter.parse_config(json.dumps(payload).encode()),
        SingleRowFacilityLayoutConfigV21,
    )
    assert (
        SingleRowFacilityLayoutAdapterV2()
        .parse_config(
            Path("examples/domains/single-row-facility-layout/v2-complete.json").read_bytes()
        )
        .domain.version
        == "2.0.0"
    )


def test_v21_execution_mode_is_strict_and_persisted() -> None:
    payload = _versioned_payload()
    payload["execution"]["mode"] = "high_performance"
    config = SingleRowFacilityLayoutConfigV21.model_validate(payload)
    assert config.model_dump(mode="json")["execution"]["mode"] == "high_performance"

    payload["execution"]["mode"] = "turbo"
    with pytest.raises(ValidationError):
        SingleRowFacilityLayoutConfigV21.model_validate(payload)


def test_v21_case_contract_has_deterministic_ids_and_no_required_core_run_id() -> None:
    schema = LayoutCaseResultV21.model_json_schema()
    properties = schema["properties"]
    assert {"case_id", "forest_id", "counting_producer", "scientific_status"} <= set(properties)
    assert "core_run_id" not in schema["required"]
    assert {"counting_producer", "scientific_status"} <= set(schema["required"])
    assert "criteria_vector" in properties
    assert SignedExactFractionV21(numerator=-3, denominator=2).numerator == -3
    with pytest.raises(ValidationError):
        SignedExactFractionV21(numerator=3, denominator=0)


def test_v21_projection_round_trips_without_rewriting_v20() -> None:
    adapter = SingleRowFacilityLayoutAdapterV21()
    config = adapter.parse_config(json.dumps(_versioned_payload()).encode())
    context = adapter.project(config).context
    nonce = "0123456789abcdef0123456789abcdef"
    projection = adapter.build_projection_record(
        domain_experiment_id=domain_experiment_id(config, nonce),
        created_at="2026-09-29T12:00:00.000Z",
        config=config,
        context=context,
        instance_nonce=nonce,
    )

    restored = adapter.parse_projection_record(projection.model_dump_json().encode())
    assert restored.domain_config.execution.mode == "standard"
    assert restored.domain_config.domain.version == "2.1.0"
    first_case = next(adapter.generate_cases(config, context).cases)
    assert first_case.core_config.schema_version == "1.0.0"
    assert first_case.linear_forest_edge_count == len(first_case.payload.edges)
    assert first_case.linear_forest_edge_component_count is not None
    repeated_first_case = next(adapter.generate_cases(config, context).cases)
    assert first_case.case_id == repeated_first_case.case_id
    legacy = SingleRowFacilityLayoutAdapterV2().parse_config(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_bytes()
    )
    assert legacy.schema_version == "2.0.0"
