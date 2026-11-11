from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, NoReturn, cast

import typer
from typer._click.exceptions import Exit, UsageError

from tesis_domain_extensions.application import DomainApplication, InterpretedRun
from tesis_domain_extensions.catalog import SUPPORTED_DOMAINS
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.terminal_adapter import DomainTerminalObserver
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.application.workspace_selection import (
    MultipleWorkspacesError,
    WorkspaceScanWarning,
    WorkspaceSelectionError,
    select_workspace,
)
from tesis_proyect.observation import BestEffortExecutionObserver

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)


class OutputFormat(StrEnum):
    HUMAN = "human"
    JSON = "json"


class ListingFormat(StrEnum):
    HUMAN = "human"
    NDJSON = "ndjson"


class ResultOperation(StrEnum):
    RUN = "run"
    RESUME = "resume"
    RENDER = "render"


WorkspaceOption = Annotated[
    Path | None,
    typer.Option(
        "--workspace",
        envvar="TESIS_PROYECT_WORKSPACE",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
]


@dataclass(frozen=True)
class DomainRuntime:
    application: DomainApplication
    terminal: DomainTerminalObserver


def _json_stdout(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    typer.echo(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def _fail(error: DomainExtensionError) -> NoReturn:
    typer.echo(str(error), err=True)
    raise typer.Exit(error.exit_code)


def _select_cli_workspace(explicit: Path | None) -> Path:
    def warn(item: WorkspaceScanWarning) -> None:
        typer.echo(f"Advertencia: no se pudo inspeccionar {item.path}: {item.error}", err=True)

    try:
        return select_workspace(explicit, warning=warn)
    except MultipleWorkspacesError as exc:
        choices = "\n".join(f"  {candidate.relative_to(exc.root)}" for candidate in exc.candidates)
        example = exc.candidates[0].relative_to(exc.root)
        raise DomainExtensionError(
            "Se encontraron múltiples workspaces:\n"
            f"{choices}\n\nSeleccione uno explícitamente:\n"
            f'  tesis-domain COMANDO --workspace "{example}"',
            exit_code=64,
        ) from exc
    except WorkspaceSelectionError as exc:
        raise DomainExtensionError(str(exc), exit_code=64) from exc


@contextmanager
def _runtime(workspace: Path) -> Iterator[DomainRuntime]:
    terminal = DomainTerminalObserver()
    observer = BestEffortExecutionObserver(terminal)
    core = CoreCommands.open(workspace, observer=observer)
    try:
        yield DomainRuntime(
            application=DomainApplication(workspace, core, progress_observer=terminal),
            terminal=terminal,
        )
    finally:
        terminal.close()


def _workspace_argument(workspace: Path) -> str:
    return f'--workspace "{workspace}"'


def _emit_result(
    interpreted: InterpretedRun,
    workspace: Path,
    output_format: OutputFormat,
    operation: ResultOperation,
) -> None:
    if output_format == OutputFormat.JSON:
        _json_stdout(interpreted.result)
        return
    result = cast(Any, interpreted.result)
    adapter = SUPPORTED_DOMAINS[(result.domain.id, result.domain.version)]
    heading = {
        ResultOperation.RUN: "Ejecución de dominio completada",
        ResultOperation.RESUME: "Run de dominio reanudado e interpretado",
        ResultOperation.RENDER: "Informe de dominio regenerado",
    }[operation]
    typer.echo(f"{heading}:")
    typer.echo(adapter.render_human(interpreted.result), nl=False)
    execution_id = getattr(
        interpreted.manifest,
        "run_id",
        getattr(interpreted.manifest, "domain_run_id", None),
    )
    typer.echo(f"\nID del run: {execution_id}")
    typer.echo(f"Referencia del run: {interpreted.run_reference}")
    typer.echo(f"Referencia del experimento: {interpreted.domain_experiment_reference}")
    typer.echo(f"Informe: {interpreted.report_path}")
    if operation != ResultOperation.RENDER:
        typer.echo("Próximo comando:")
        typer.echo(
            f"  tesis-domain render {interpreted.run_reference} {_workspace_argument(workspace)}"
        )


@app.command("list-domains")
def list_domains(
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.HUMAN,
) -> None:
    """Lista los adaptadores de dominio incluidos en la distribución."""

    rows = [
        {
            "id": adapter.domain_id,
            "version": adapter.version,
            "description": adapter.description,
            "primary_measure": adapter.primary_measure.model_dump(mode="json"),
        }
        for adapter in SUPPORTED_DOMAINS.values()
    ]
    if output_format == OutputFormat.JSON:
        _json_stdout({"domains": rows})
        return
    typer.echo("DOMINIO                     VERSIÓN  MEDIDA                         DESCRIPCIÓN")
    for row in rows:
        measure = cast(dict[str, str], row["primary_measure"])
        typer.echo(f"{row['id']:<27} {row['version']:<8} {measure['id']:<30} {row['description']}")


@app.command("prepare")
def prepare(
    config_path: Annotated[
        Path,
        typer.Option("--config", exists=True, dir_okay=False, resolve_path=True),
    ],
    workspace: WorkspaceOption = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.HUMAN,
) -> None:
    """Valida y persiste un experimento de dominio reutilizable."""

    try:
        selected = _select_cli_workspace(workspace)
        with _runtime(selected) as runtime:
            runtime.terminal.set_status("Preparando el experimento de dominio…")
            summary = runtime.application.prepare(config_path)
    except DomainExtensionError as exc:
        _fail(exc)
    if output_format == OutputFormat.JSON:
        _json_stdout(summary)
        return
    typer.echo(
        "\n".join(
            [
                f"Experimento de dominio preparado: {summary.display_name}",
                f"Dominio: {summary.domain.id}@{summary.domain.version}",
                f"ID del experimento: {summary.domain_experiment_id}",
                f"Referencia del experimento: {summary.reference}",
                "Próximo comando:",
                f"  tesis-domain run {summary.reference} {_workspace_argument(selected)}",
            ]
        )
    )


@app.command("list-experiments")
def list_experiments(
    workspace: WorkspaceOption = None,
    domain_id: Annotated[str | None, typer.Option("--domain")] = None,
    prefix: Annotated[str | None, typer.Option("--prefix")] = None,
    output_format: Annotated[ListingFormat, typer.Option("--format")] = ListingFormat.HUMAN,
) -> None:
    """Lista experimentos de dominio validados."""

    try:
        selected = _select_cli_workspace(workspace)
        with _runtime(selected) as runtime:
            listing = runtime.application.list_experiments(
                domain_id=domain_id,
                prefix=prefix,
            )
    except DomainExtensionError as exc:
        _fail(exc)
    for warning in listing.warnings:
        typer.echo(warning, err=True)
    if output_format == ListingFormat.NDJSON:
        for item in listing.experiments:
            _json_stdout(item)
        return
    if not listing.experiments:
        typer.echo("No se encontraron experimentos de dominio.")
        return
    typer.echo("EXPERIMENTO_REF  DOMINIO                      CREADO                    NOMBRE")
    for item in listing.experiments:
        domain = f"{item.domain.id}@{item.domain.version}"
        typer.echo(f"{item.reference:<16} {domain:<28} {item.created_at:<24} {item.display_name}")


@app.command("list-runs")
def list_runs(
    workspace: WorkspaceOption = None,
    experiment: Annotated[str | None, typer.Option("--experiment")] = None,
    domain_id: Annotated[str | None, typer.Option("--domain")] = None,
    prefix: Annotated[str | None, typer.Option("--prefix")] = None,
    output_format: Annotated[ListingFormat, typer.Option("--format")] = ListingFormat.HUMAN,
) -> None:
    """Lista ejecuciones validadas asociadas a experimentos de dominio."""

    try:
        selected = _select_cli_workspace(workspace)
        with _runtime(selected) as runtime:
            listing = runtime.application.list_runs(
                experiment_reference=experiment,
                domain_id=domain_id,
                prefix=prefix,
            )
    except DomainExtensionError as exc:
        _fail(exc)
    for warning in listing.warnings:
        typer.echo(warning, err=True)
    if output_format == ListingFormat.NDJSON:
        for item in listing.runs:
            _json_stdout(item)
        return
    if not listing.runs:
        typer.echo("No se encontraron runs de dominio.")
        return
    typer.echo(
        "RUN_REF   ESTADO      CREADO                    EXPERIMENTO_REF  "
        "DOMINIO             NOMBRE"
    )
    for item in listing.runs:
        typer.echo(
            f"{item.run_reference:<9} {item.status:<11} {item.created_at:<24} "
            f"{item.domain_experiment_reference:<16} {item.domain.id:<19} {item.display_name}"
        )


@app.command("run")
def run_domain(
    domain_experiment_reference: Annotated[str, typer.Argument(metavar="DOMAIN_EXPERIMENT_REF")],
    workspace: WorkspaceOption = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.HUMAN,
) -> None:
    """Crea, ejecuta e interpreta una ejecución de un experimento preparado."""

    try:
        selected = _select_cli_workspace(workspace)
        with _runtime(selected) as runtime:
            theoretical = runtime.application.theoretical_combinations(domain_experiment_reference)
            runtime.terminal.generation_started(theoretical)
            interpreted = runtime.application.run(domain_experiment_reference)
    except DomainExtensionError as exc:
        _fail(exc)
    _emit_result(interpreted, selected, output_format, ResultOperation.RUN)


@app.command("resume")
def resume_domain(
    run_reference: Annotated[str, typer.Argument(metavar="RUN_REF")],
    workspace: WorkspaceOption = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.HUMAN,
) -> None:
    """Reanuda una ejecución asociada a un experimento de dominio."""

    try:
        selected = _select_cli_workspace(workspace)
        with _runtime(selected) as runtime:
            runtime.terminal.set_status("Verificando el run de dominio…")
            interpreted = runtime.application.resume(run_reference)
    except DomainExtensionError as exc:
        _fail(exc)
    _emit_result(interpreted, selected, output_format, ResultOperation.RESUME)


@app.command("render")
def render_domain(
    run_reference: Annotated[str, typer.Argument(metavar="RUN_REF")],
    workspace: WorkspaceOption = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.HUMAN,
) -> None:
    """Regenera los reportes de una ejecución de dominio terminal."""

    try:
        selected = _select_cli_workspace(workspace)
        with _runtime(selected) as runtime:
            runtime.terminal.set_status("Regenerando la interpretación de dominio…")
            interpreted = runtime.application.render(run_reference)
    except DomainExtensionError as exc:
        _fail(exc)
    _emit_result(interpreted, selected, output_format, ResultOperation.RENDER)


def main() -> None:
    """Run the domain adaptation command-line interface."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        result = app(standalone_mode=False)
        if isinstance(result, int) and result != 0:
            raise SystemExit(result)
    except UsageError as exc:
        typer.echo(f"Error de uso: {exc}", err=True)
        raise SystemExit(64) from exc
    except Exit as exc:
        raise SystemExit(exc.exit_code) from exc


if __name__ == "__main__":
    main()
