from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tesis_domain_extensions.application import DomainApplication
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_proyect.application.commands import CoreCommands


def _prepared_run(tmp_path: Path, config_path: Path) -> tuple[DomainApplication, str, str]:
    application = DomainApplication(tmp_path, CoreCommands.open(tmp_path))
    summary = application.prepare(config_path)
    domain_run = application.reserve_grouped_run(summary.domain_experiment_id)
    return application, str(domain_run.domain_run_id), summary.domain_experiment_id


def test_delete_run_removes_only_its_experiment_and_keeps_template(
    tmp_path: Path, example_root: Path
) -> None:
    config_path = example_root / "comparison.json"
    application, run_id, experiment_id = _prepared_run(tmp_path, config_path)
    template_path = tmp_path / "domain_templates" / f"{experiment_id}.json"
    template_path.parent.mkdir()
    template_path.write_bytes((example_root / "comparison.json").read_bytes())

    response = application.delete_domain_run(run_id)

    assert response == {
        "deleted_domain_run_id": run_id,
        "deleted_domain_experiment": experiment_id,
        "preserved_template": True,
    }
    assert not (tmp_path / "domain_runs" / run_id).exists()
    assert not (tmp_path / "domain_projections" / f"{experiment_id}.json").exists()
    assert template_path.is_file()


def test_delete_preserves_projection_referenced_by_another_run(
    tmp_path: Path, example_root: Path
) -> None:
    application, first_run, experiment_id = _prepared_run(
        tmp_path, example_root / "comparison.json"
    )
    second = application.reserve_grouped_run(experiment_id)
    result = application.delete_domain_run(first_run)

    assert result["deleted_domain_experiment"] is None
    assert (tmp_path / "domain_projections" / f"{experiment_id}.json").is_file()
    assert (
        application.store.load_domain_run(str(second.domain_run_id))[0].domain_experiment_id
        == experiment_id
    )


def test_delete_rejects_active_run_without_removing_files(
    tmp_path: Path, example_root: Path
) -> None:
    application, run_id, experiment_id = _prepared_run(tmp_path, example_root / "comparison.json")
    manifest, _ = application.store.load_domain_run(run_id)
    application.store.write_domain_run(manifest.model_copy(update={"status": "running"}))

    with pytest.raises(DomainExtensionError, match="activa"):
        application.delete_domain_run(run_id)

    assert (tmp_path / "domain_runs" / run_id).is_dir()
    assert (tmp_path / "domain_projections" / f"{experiment_id}.json").is_file()


def test_delete_rejects_unknown_run_without_creating_an_operation(tmp_path: Path) -> None:
    application = DomainApplication(tmp_path, CoreCommands.open(tmp_path))

    with pytest.raises(DomainExtensionError, match="No se encontró"):
        application.delete_domain_run("12345678-1234-4234-8234-123456789abc")

    assert not (tmp_path / ".domain_deletion_operations").exists()


def test_delete_completed_run_removes_exclusive_core_attempts_and_experiment(
    tmp_path: Path,
) -> None:
    config_path = Path("examples/domains/inspection-route/comparison.json")
    application = DomainApplication(tmp_path, CoreCommands.open(tmp_path))
    prepared = application.prepare(config_path)
    interpreted = application.run(prepared.domain_experiment_id)
    core_run_ids = {
        attempt.core_run_id for case in interpreted.manifest.cases for attempt in case.attempts
    }
    core_experiment_ids = {case.core_experiment_id for case in interpreted.manifest.cases}
    assert core_run_ids

    response = application.delete_domain_run(interpreted.manifest.domain_run_id)

    assert response["deleted_domain_experiment"] == prepared.domain_experiment_id
    assert all(not (tmp_path / "runs" / run_id).exists() for run_id in core_run_ids)
    assert all(
        not (tmp_path / "experiments" / f"{experiment_id}.json").exists()
        for experiment_id in core_experiment_ids
    )


def test_delete_supports_archived_checkpointed_high_performance_run(
    tmp_path: Path,
) -> None:
    config = json.loads(
        Path("examples/domains/single-row-facility-layout/v2-complete.json").read_bytes()
    )
    config["schema_version"] = "2.1.0"
    config["domain"]["version"] = "2.1.0"
    config["execution"]["mode"] = "high_performance"
    config_path = tmp_path / "fast-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    application = DomainApplication(tmp_path, CoreCommands.open(tmp_path))
    prepared = application.prepare(config_path)
    reserved = application.reserve_grouped_run(prepared.domain_experiment_id)
    manifest, _ = application.store.load_domain_run(str(reserved.domain_run_id))
    projection, _ = application.store._read_projection(prepared.domain_experiment_id)
    legacy_config = projection.domain_config.model_dump(mode="json")
    legacy_execution = dict(legacy_config["execution"])
    del legacy_execution["mode"]
    legacy_execution["strategy"] = "direct_exact_checkpointed"
    legacy_config["execution"] = legacy_execution
    legacy_experiment_id = hashlib.sha256(
        json.dumps(legacy_config, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()
    legacy_projection = projection.model_dump(mode="json")
    legacy_projection["domain_experiment_id"] = legacy_experiment_id
    legacy_projection.pop("instance_nonce")
    legacy_projection["domain_config"] = legacy_config
    legacy_projection["projection_context"]["schema_version"] = "2.0.0"
    projection_path = tmp_path / "domain_projections" / f"{prepared.domain_experiment_id}.json"
    projection_path.unlink()
    (tmp_path / "domain_projections" / f"{legacy_experiment_id}.json").write_text(
        json.dumps(legacy_projection), encoding="utf-8"
    )
    artifact = {
        "path": "result.json",
        "schema_id": "single-row-facility-layout-result@2.1.0",
        "media_type": "application/json",
        "encoding": "utf-8",
        "compression": "none",
        "records": 1,
        "stored_size_bytes": 1,
        "uncompressed_size_bytes": 1,
        "sha256": f"sha256:{'a' * 64}",
    }
    archived_manifest = {
        "schema_version": "2.1.0",
        "domain_run_id": manifest.domain_run_id,
        "domain_experiment_id": legacy_experiment_id,
        "domain": manifest.domain.model_dump(mode="json"),
        "display_name": manifest.display_name,
        "status": "completed",
        "generator_cursor": manifest.generator_cursor,
        "generation": manifest.generation.model_dump(mode="json"),
        "strategy": "direct_exact_checkpointed",
        "checkpoint_sequence": 1,
        "chunks": [
            {
                "sequence": 0,
                "cursor_start": 0,
                "cursor_end": 1,
                "cases": {**artifact, "path": "chunks/cases.ndjson"},
                "forests": {**artifact, "path": "chunks/forests.ndjson"},
            }
        ],
        "result": artifact,
        "created_at": manifest.created_at,
        "updated_at": manifest.updated_at,
    }
    run_path = tmp_path / "domain_runs" / manifest.domain_run_id / "domain_run.json"
    run_path.write_text(json.dumps(archived_manifest), encoding="utf-8")
    preserved_template = tmp_path / "domain_templates" / f"{legacy_experiment_id}.json"
    preserved_template.parent.mkdir(exist_ok=True)
    preserved_template.write_text(json.dumps(legacy_config), encoding="utf-8")
    legacy_template = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    legacy_template["unrecognized_historical_property"] = True
    templates_root = tmp_path / "domain_templates"
    templates_root.mkdir(exist_ok=True)
    (templates_root / "unrelated-historical-template.json").write_text(
        json.dumps(legacy_template), encoding="utf-8"
    )

    deleted = application.delete_domain_run(manifest.domain_run_id)

    assert deleted["deleted_domain_run_id"] == manifest.domain_run_id
    assert deleted["deleted_domain_experiment"] == legacy_experiment_id
    assert deleted["preserved_template"] is True
    assert not run_path.parent.exists()
    assert not (tmp_path / "domain_projections" / f"{prepared.domain_experiment_id}.json").exists()
    assert not (tmp_path / "domain_projections" / f"{legacy_experiment_id}.json").exists()
    assert preserved_template.is_file()


def test_delete_preserves_attachment_referenced_by_preserved_template(
    tmp_path: Path,
) -> None:
    config = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    attachment_data = b"durable evidence"
    digest = hashlib.sha256(attachment_data).hexdigest()
    config["study"]["attachments"] = [
        {
            "kind": "file",
            "sha256": digest,
            "name": "evidence.pdf",
            "media_type": "application/pdf",
            "size_bytes": len(attachment_data),
        }
    ]
    attachment = tmp_path / "domain_attachments" / digest
    attachment.parent.mkdir()
    attachment.write_bytes(attachment_data)
    config_path = tmp_path / "draft.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    application = DomainApplication(tmp_path, CoreCommands.open(tmp_path))
    prepared = application.prepare(config_path)
    run = application.reserve_grouped_run(prepared.domain_experiment_id)
    template = tmp_path / "domain_templates" / f"{prepared.domain_experiment_id}.json"
    template.parent.mkdir()
    template.write_text(json.dumps(config), encoding="utf-8")

    result = application.delete_domain_run(run.domain_run_id)

    assert result["preserved_template"] is True
    assert attachment.is_file()


def test_interrupted_delete_resumes_from_persisted_inventory(
    tmp_path: Path, example_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application, run_id, experiment_id = _prepared_run(tmp_path, example_root / "comparison.json")
    service = application.deletion
    apply_inventory = service._apply

    def interrupt_after_projection(inventory: object) -> None:
        from tesis_domain_extensions.deletion import DeletionOperation

        operation = DeletionOperation.model_validate(inventory)
        apply_inventory(operation.model_copy(update={"destinations": operation.destinations[:-1]}))
        raise OSError("interrupted")

    monkeypatch.setattr(service, "_apply", interrupt_after_projection)
    with pytest.raises(OSError, match="interrupted"):
        application.delete_domain_run(run_id)
    assert not (tmp_path / "domain_projections" / f"{experiment_id}.json").exists()
    assert (tmp_path / "domain_runs" / run_id).is_dir()

    DomainApplication(tmp_path, CoreCommands.open(tmp_path))

    assert not (tmp_path / "domain_runs" / run_id).exists()
    assert not list((tmp_path / ".domain_deletion_operations").glob("*.json"))


def test_symlink_in_run_tree_fails_before_any_deletion(tmp_path: Path, example_root: Path) -> None:
    application, run_id, experiment_id = _prepared_run(tmp_path, example_root / "comparison.json")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "domain_runs" / run_id / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")

    with pytest.raises(DomainExtensionError, match="enlace simbólico"):
        application.delete_domain_run(run_id)

    assert (tmp_path / "domain_runs" / run_id).is_dir()
    assert (tmp_path / "domain_projections" / f"{experiment_id}.json").is_file()
