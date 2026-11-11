from __future__ import annotations

import json
from pathlib import Path

import pytest

from tesis_domain_extensions.domains.inspection_route.adapter import InspectionRouteAdapter
from tesis_domain_extensions.domains.inspection_route.contracts import InspectionRouteConfig
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.projection_store import (
    ProjectionStore,
    normalize_projection_prefix,
)
from tesis_proyect.application.commands import CoreCommands


def _workspace(path: Path) -> ProjectionStore:
    (path / "experiments").mkdir(parents=True)
    (path / "runs").mkdir()
    return ProjectionStore(path, CoreCommands.open(path))


def test_reference_validation_and_resolution_failures(tmp_path: Path) -> None:
    store = _workspace(tmp_path)
    assert normalize_projection_prefix("ABCDEF12", minimum_length=8) == "abcdef12"
    for value in ("abc", "not-hex", "a" * 65):
        with pytest.raises(DomainExtensionError) as failure:
            normalize_projection_prefix(value, minimum_length=8)
        assert failure.value.exit_code == 64
    with pytest.raises(DomainExtensionError, match="No se encontró"):
        store.resolve("12345678")
    store._matching_ids = lambda prefix: ["1" * 64, "1" * 63 + "2"]  # type: ignore[method-assign]
    with pytest.raises(DomainExtensionError, match="ambigua"):
        store.resolve("11111111")
    with pytest.raises(DomainExtensionError, match="ID"):
        store.load("invalid")
    assert store.short_reference("a" * 64) == "aaaaaaaa"


def test_listing_warns_about_noncanonical_and_invalid_entries(tmp_path: Path) -> None:
    store = _workspace(tmp_path)
    root = tmp_path / "domain_projections"
    root.mkdir()
    (root / "noise.txt").write_text("noise", encoding="utf-8")
    (root / ".temporary").write_text("ignored", encoding="utf-8")
    invalid_id = "f" * 64
    (root / f"{invalid_id}.json").write_text("{}", encoding="utf-8")
    listing = store.list_experiments(domain_id=None, prefix=None)
    assert listing.experiments == ()
    assert len(listing.warnings) == 2


def test_projection_filename_and_context_integrity_failures(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    store = _workspace(tmp_path)
    loaded = store.prepare(InspectionRouteAdapter(), partial_config)
    experiment_id = loaded.record.domain_experiment_id
    projection = tmp_path / "domain_projections" / f"{experiment_id}.json"
    other_id = "0" * 64 if experiment_id != "0" * 64 else "1" * 64
    (projection.parent / f"{other_id}.json").write_bytes(projection.read_bytes())
    with pytest.raises(DomainExtensionError, match="nombre"):
        store.load(other_id)

    payload = json.loads(projection.read_text(encoding="utf-8"))
    payload["projection_context"]["vertex_mapping"].reverse()
    projection.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(DomainExtensionError, match=r"inválida|contexto"):
        store.load(experiment_id)
    assert loaded.record.domain_experiment_id == experiment_id


def test_prepare_creates_independent_experiments_for_same_config(
    tmp_path: Path, partial_config: InspectionRouteConfig
) -> None:
    store = _workspace(tmp_path)
    adapter = InspectionRouteAdapter()
    first = store.prepare(adapter, partial_config)
    second = store.prepare(adapter, partial_config)
    assert first.record.domain_experiment_id != second.record.domain_experiment_id
    assert first.record.instance_nonce != second.record.instance_nonce
    assert store.load(first.record.domain_experiment_id).record == first.record
    assert store.load(second.record.domain_experiment_id).record == second.record


def test_grouped_prepare_never_reads_or_writes_core_experiments(
    tmp_path: Path,
    partial_config: InspectionRouteConfig,
) -> None:
    (tmp_path / "experiments").mkdir()
    (tmp_path / "runs").mkdir()

    class ForbiddenCore:
        def load_experiment(self, experiment_id: str) -> None:
            raise AssertionError(experiment_id)

        def save_experiment(self, experiment_id: str, config: object) -> None:
            raise AssertionError((experiment_id, config))

    loaded = ProjectionStore(tmp_path, ForbiddenCore()).prepare(
        InspectionRouteAdapter(), partial_config
    )
    assert loaded.projected.core_config is None
    assert list((tmp_path / "experiments").iterdir()) == []
