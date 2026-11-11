from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _invoke(*arguments: str, cwd: Path | None = None, env: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, "-m", "tesis_domain_extensions", *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
        env=env,
    )


def _prepare(workspace: Path, config: Path) -> dict[str, object]:
    result = _invoke(
        "prepare",
        "--config",
        str(config),
        "--workspace",
        str(workspace),
        "--format",
        "json",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_help_uses_domain_execution_vocabulary_in_spanish() -> None:
    help_result = _invoke("--help")
    assert help_result.returncode == 0
    assert "Lista ejecuciones validadas" in help_result.stdout
    assert "Reanuda una ejecución" in help_result.stdout
    assert "Regenera los reportes de una ejecución de dominio" in help_result.stdout
    assert "CORE run" not in help_result.stdout
    assert "terminal CORE" not in help_result.stdout


def test_prepare_reports_the_invalid_field_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = tmp_path / "layout.json"
    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_text(
            encoding="utf-8"
        )
    )
    payload["study"]["variable_component_ids"] = ["right-chain"]
    config.write_text(json.dumps(payload), encoding="utf-8")
    prepared = _invoke(
        "prepare",
        "--config",
        str(config),
        "--workspace",
        str(workspace),
        "--format",
        "json",
    )
    assert prepared.returncode == 65
    assert prepared.stdout == ""
    assert "study.variable_component_ids" in prepared.stderr
    assert "el campo no está permitido" in prepared.stderr


def test_prepare_is_autonomous_and_list_supports_prefix_and_ndjson(
    tmp_path: Path,
    example_root: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "domain.json"
    shutil.copy2(example_root / "comparison.json", source)
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["execution"]["persistence"]["persist_events"] = True
    source.write_text(json.dumps(payload), encoding="utf-8")
    prepared = _prepare(workspace, source)
    source.unlink()

    listing = _invoke(
        "list-experiments",
        "--workspace",
        str(workspace),
        "--domain",
        "inspection-route",
        "--prefix",
        str(prepared["domain_experiment_id"])[0],
        "--format",
        "ndjson",
    )
    assert listing.returncode == 0, listing.stderr
    listed_experiment = json.loads(listing.stdout)
    assert listed_experiment["domain_experiment_id"] == prepared["domain_experiment_id"]
    assert listed_experiment["domain"]["id"] == "inspection-route"

    run = _invoke(
        "run",
        str(prepared["reference"]),
        "--workspace",
        str(workspace),
        "--format",
        "json",
    )
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["comparison_status"] == "conclusive"
    first_core_run = result["scenarios"][0]["core_run_id"]
    events = workspace / "runs" / first_core_run / "logs" / "events.ndjson"
    assert events.is_file()


def test_run_is_repeatable_and_render_does_not_run_pipeline(
    tmp_path: Path,
    example_root: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepared = _prepare(workspace, example_root / "comparison.json")
    runs = []
    for _ in range(2):
        process = _invoke(
            "run",
            str(prepared["reference"]),
            "--workspace",
            str(workspace),
            "--format",
            "json",
        )
        assert process.returncode == 0, process.stderr
        runs.append(json.loads(process.stdout)["execution"]["domain_run_id"])
    assert runs[0] != runs[1]

    listing = _invoke(
        "list-runs",
        "--experiment",
        str(prepared["reference"]),
        "--domain",
        "inspection-route",
        "--workspace",
        str(workspace),
        "--format",
        "ndjson",
    )
    assert listing.returncode == 0, listing.stderr
    rows = [json.loads(line) for line in listing.stdout.splitlines()]
    assert {row["run_id"] for row in rows} == set(runs)
    assert all(
        set(row)
        == {
            "schema_version",
            "run_reference",
            "run_id",
            "domain_experiment_reference",
            "domain_experiment_id",
            "domain",
            "display_name",
            "status",
            "created_at",
            "updated_at",
        }
        for row in rows
    )

    first_result = json.loads(
        (workspace / "domain_runs" / runs[0] / "result.json").read_text(encoding="utf-8")
    )
    core_run_id = first_result["scenarios"][0]["core_run_id"]
    pipeline = workspace / "runs" / core_run_id / "pipeline.json"
    before = pipeline.read_bytes()
    rendered = _invoke(
        "render",
        runs[0][:8],
        "--workspace",
        str(workspace),
        "--format",
        "json",
    )
    assert rendered.returncode == 0, rendered.stderr
    assert pipeline.read_bytes() == before
    assert '"comparison_status":"conclusive"' in rendered.stdout

    resumed = _invoke(
        "resume",
        runs[0][:8],
        "--workspace",
        str(workspace),
        "--format",
        "json",
    )
    assert resumed.returncode == 0, resumed.stderr

    rendered_human = _invoke("render", runs[0][:8], "--workspace", str(workspace))
    assert rendered_human.returncode == 0, rendered_human.stderr
    assert "Informe de dominio regenerado:" in rendered_human.stdout
    assert "Próximo comando:" not in rendered_human.stdout

    resumed_human = _invoke("resume", runs[0][:8], "--workspace", str(workspace))
    assert resumed_human.returncode == 0, resumed_human.stderr
    assert "Run de dominio reanudado e interpretado:" in resumed_human.stdout
    assert resumed_human.stdout.count("Próximo comando:") == 1


def test_resume_diagnoses_an_experiment_reference_and_lists_its_runs(
    tmp_path: Path,
    example_root: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepared = _prepare(workspace, example_root / "comparison.json")
    executed = _invoke(
        "run",
        str(prepared["reference"]),
        "--workspace",
        str(workspace),
        "--format",
        "json",
    )
    assert executed.returncode == 0, executed.stderr
    run_id = json.loads(executed.stdout)["execution"]["domain_run_id"]

    resumed = _invoke(
        "resume",
        str(prepared["reference"]),
        "--workspace",
        str(workspace),
    )
    assert resumed.returncode == 64
    assert "identifica un experimento de dominio, no un run" in resumed.stderr
    assert run_id[:8] in resumed.stderr
    assert "list-runs" in resumed.stderr
    assert "tesis-domain resume RUN_REF" in resumed.stderr

    rendered = _invoke(
        "render",
        str(prepared["reference"]),
        "--workspace",
        str(workspace),
    )
    assert rendered.returncode == 64
    assert "El comando 'render' requiere una referencia de run" in rendered.stderr
    assert "tesis-domain render RUN_REF" in rendered.stderr
    assert "tesis-domain resume RUN_REF" not in rendered.stderr


@pytest.mark.parametrize("command", ["resume", "render"])
def test_grouped_experiment_reference_lists_its_domain_run(
    tmp_path: Path,
    command: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    prepared = _prepare(
        workspace,
        Path("examples/domains/single-row-facility-layout/comparison.json"),
    )
    executed = _invoke(
        "run",
        str(prepared["reference"]),
        "--workspace",
        str(workspace),
        "--format",
        "json",
    )
    assert executed.returncode == 0, executed.stderr
    domain_run_id = json.loads(executed.stdout)["execution"]["domain_run_id"]
    rejected = _invoke(
        command,
        str(prepared["reference"]),
        "--workspace",
        str(workspace),
    )
    assert rejected.returncode == 64
    assert "Runs asociados:" in rejected.stderr
    assert domain_run_id[:8] in rejected.stderr
    assert "todavía no tiene runs" not in rejected.stderr


def test_cli_rejects_legacy_bundle_flow_and_ad_hoc_core_runs(
    tmp_path: Path,
    example_root: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    rejected = _invoke(
        "run",
        "--config",
        str(example_root / "comparison.json"),
        "--bundle",
        str(tmp_path / "bundle"),
        "--experiment",
        "legacy",
        "--workspace",
        str(workspace),
    )
    assert rejected.returncode == 64

    core_config = workspace / "core.json"
    projected = _prepare(workspace, example_root / "comparison.json")
    domain_run = _invoke(
        "run",
        str(projected["reference"]),
        "--workspace",
        str(workspace),
        "--format",
        "json",
    )
    assert domain_run.returncode == 0, domain_run.stderr
    experiment_path = next((workspace / "experiments").glob("*.json"))
    core_config.write_bytes(experiment_path.read_bytes())
    environment = os.environ.copy()
    created = subprocess.run(
        [
            sys.executable,
            "-m",
            "tesis_proyect",
            "--workspace",
            str(workspace),
            "save-experiment",
            "--id",
            "ad-hoc",
            "--config",
            str(core_config),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    assert created.returncode == 0, created.stderr
    run_created = subprocess.run(
        [
            sys.executable,
            "-m",
            "tesis_proyect",
            "--workspace",
            str(workspace),
            "create-run",
            "--experiment",
            "ad-hoc",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert run_created.returncode == 0, run_created.stderr
    run_id = next(
        json.loads(line)["run_id"]
        for line in run_created.stdout.splitlines()
        if json.loads(line).get("event") == "run_created"
    )
    rendered = _invoke("render", run_id, "--workspace", str(workspace))
    assert rendered.returncode != 0
    assert "experimento de dominio" in rendered.stderr.lower()


def test_list_domains_and_prepare_human_output(
    tmp_path: Path,
    example_root: Path,
) -> None:
    listing = _invoke("list-domains", "--format", "json")
    assert listing.returncode == 0
    assert '"id":"inspection-route"' in listing.stdout
    assert '"id":"single-row-facility-layout"' in listing.stdout
    human_domains = _invoke("list-domains")
    assert human_domains.returncode == 0
    assert "inspection-route" in human_domains.stdout
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    empty_experiments = _invoke("list-experiments", "--workspace", str(workspace))
    empty_runs = _invoke("list-runs", "--workspace", str(workspace))
    assert "No se encontraron experimentos" in empty_experiments.stdout
    assert "No se encontraron runs" in empty_runs.stdout

    prepared = _invoke(
        "prepare",
        "--config",
        str(example_root / "comparison.json"),
        "--workspace",
        str(workspace),
    )
    assert prepared.returncode == 0, prepared.stderr
    assert "Referencia del experimento:" in prepared.stdout
    assert "tesis-domain run" in prepared.stdout
    assert "Command:" not in prepared.stdout
    assert "Next command:" not in prepared.stdout
    assert prepared.stdout.count("Próximo comando:") == 1

    experiment_listing = _invoke("list-experiments", "--workspace", str(workspace))
    assert experiment_listing.returncode == 0
    assert "EXPERIMENTO_REF" in experiment_listing.stdout
    reference = next(
        line.split(":", maxsplit=1)[1].strip()
        for line in prepared.stdout.splitlines()
        if line.startswith("Referencia del experimento:")
    )
    executed = _invoke("run", reference, "--workspace", str(workspace))
    assert executed.returncode == 0, executed.stderr
    assert "ID del run:" in executed.stdout
    assert executed.stdout.count("Próximo comando:") == 1
    run_listing = _invoke("list-runs", "--workspace", str(workspace))
    assert run_listing.returncode == 0
    assert "RUN_REF" in run_listing.stdout
    assert "DOMINIO" in experiment_listing.stdout
    assert "DOMINIO" in run_listing.stdout

    obsolete_filter = _invoke(
        "list-domain-experiments",
        "--workspace",
        str(workspace),
    )
    assert obsolete_filter.returncode == 64

    obsolete_runs = _invoke("list-domain-runs", "--workspace", str(workspace))
    assert obsolete_runs.returncode == 64
