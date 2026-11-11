from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, NoReturn

import typer
from pydantic import BaseModel
from typer._click.exceptions import Exit, UsageError

from tesis_proyect.application.commands import CoreCommands, classify_command_error
from tesis_proyect.application.inspection import (
    normalize_run_prefix,
    validate_experiment_id,
)
from tesis_proyect.application.workspace_selection import (
    MultipleWorkspacesError,
    WorkspaceScanWarning,
    WorkspaceSelectionError,
    select_and_open_workspace,
)
from tesis_proyect.cli import clipboard
from tesis_proyect.cli.event_adapter import EventSink, PublicEventObserver
from tesis_proyect.cli.terminal_adapter import TerminalUiObserver
from tesis_proyect.models.enums import ErrorCode, StageId
from tesis_proyect.models.protocols import RunInspection
from tesis_proyect.observation import (
    BestEffortExecutionObserver,
    CompositeExecutionObserver,
    ExecutionObserver,
)
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.reporting.render import (
    render_run_inspection_human,
    render_run_listing_human,
    render_stage_inspection_human,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
    pretty_exceptions_enable=False,
)


class OutputFormat(StrEnum):
    HUMAN = "human"
    NDJSON = "ndjson"


@dataclass(frozen=True)
class CliState:
    workspace: Workspace


@app.callback()
def root(
    context: typer.Context,
    workspace: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            envvar="TESIS_PROYECT_WORKSPACE",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Operate an Increment 1 experimental workspace."""
    context.obj = CliState(_select_cli_workspace(workspace))


def _select_cli_workspace(explicit: Path | None) -> Workspace:
    def warn(item: WorkspaceScanWarning) -> None:
        typer.echo(f"Warning: could not inspect {item.path}: {item.error}", err=True)

    try:
        return select_and_open_workspace(explicit, warning=warn)
    except MultipleWorkspacesError as exc:
        choices = "\n".join(f"  {candidate.relative_to(exc.root)}" for candidate in exc.candidates)
        example = exc.candidates[0].relative_to(exc.root)
        raise UsageError(
            "Multiple workspaces were found:\n"
            f"{choices}\n\nSelect one explicitly:\n"
            f'  tesis-proyect --workspace "{example}" COMMAND'
        ) from exc
    except WorkspaceSelectionError as exc:
        raise UsageError(str(exc)) from exc


def _state(context: typer.Context) -> CliState:
    state = context.obj
    if not isinstance(state, CliState):
        raise RuntimeError("CLI workspace state is unavailable")
    return state


def _observers(workspace: Workspace) -> tuple[ExecutionObserver, TerminalUiObserver]:
    terminal = TerminalUiObserver(workspace)
    observer = CompositeExecutionObserver(
        PublicEventObserver(EventSink().emit),
        BestEffortExecutionObserver(terminal),
    )
    return observer, terminal


def _json_line(value: object) -> None:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", by_alias=True)
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def _prefix_option(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        normalize_run_prefix(value, minimum_length=1)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    return value


def _experiment_option(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return validate_experiment_id(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _run_reference_argument(value: str) -> str:
    try:
        normalize_run_prefix(value, minimum_length=8)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    return value


def _exit_code(code: ErrorCode) -> int:
    if code in {ErrorCode.NOT_FOUND}:
        return 66
    if code in {ErrorCode.RUN_CONTROL_UNAVAILABLE}:
        return 69
    if code in {ErrorCode.IO_ERROR, ErrorCode.RUN_LOCK_UNAVAILABLE}:
        return 74
    if code in {ErrorCode.RUN_ALREADY_ACTIVE}:
        return 75
    if code in {ErrorCode.CONFIG_INVALID, ErrorCode.VERSION_UNSUPPORTED}:
        return 78
    if code in {
        ErrorCode.SCHEMA_INVALID,
        ErrorCode.INPUT_TOO_LARGE,
        ErrorCode.INPUT_BOM_FORBIDDEN,
        ErrorCode.INPUT_DECODE_FAILED,
        ErrorCode.INPUT_JSON_INVALID,
        ErrorCode.PATH_OUTSIDE_WORKSPACE,
        ErrorCode.INTEGRITY_ERROR,
        ErrorCode.RUN_STATE_INVALID,
    }:
        return 65
    return 70


def _fail(
    exc: Exception,
) -> NoReturn:
    code, message = classify_command_error(exc)
    typer.echo(message, err=True)
    raise typer.Exit(_exit_code(code))


@contextmanager
def _command_scope(
    workspace: Workspace,
) -> Iterator[CoreCommands]:
    observer, terminal = _observers(workspace)
    try:
        yield CoreCommands(workspace, observer=observer)
    except Exception as exc:
        _fail(exc)
    finally:
        terminal.close()


@app.command("save-experiment")
def save_experiment(
    context: typer.Context,
    experiment_id: Annotated[str, typer.Option("--id")],
    config: Annotated[Path, typer.Option("--config", exists=True, dir_okay=False)],
) -> None:
    """Validate and save an immutable reusable experiment."""
    workspace = _state(context).workspace
    with _command_scope(workspace) as commands:
        commands.save_experiment(experiment_id, config)


@app.command("create-run")
def create_run(
    context: typer.Context,
    experiment: Annotated[str, typer.Option("--experiment")],
    copy_run_id: Annotated[bool, typer.Option("--copy-run-id")] = False,
) -> None:
    """Create a run from a saved experiment."""
    workspace = _state(context).workspace
    with _command_scope(workspace) as commands:
        manifest = commands.create_run(experiment)
        if copy_run_id:
            try:
                clipboard.system_clipboard.copy(manifest.run_id)
            except Exception:
                typer.echo(
                    f"Warning: Run {manifest.run_id} was created, but its ID could not be "
                    "copied to the clipboard.",
                    err=True,
                )
            else:
                typer.echo("Run ID copied to clipboard.", err=True)


@app.command("list-runs")
def list_runs(
    context: typer.Context,
    experiment: Annotated[
        str | None,
        typer.Option("--experiment", callback=_experiment_option),
    ] = None,
    prefix: Annotated[
        str | None,
        typer.Option("--prefix", callback=_prefix_option),
    ] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.HUMAN,
) -> None:
    """List validated runs without mutating workspace evidence."""
    workspace = _state(context).workspace
    with _command_scope(workspace) as commands:
        listing = commands.list_runs(
            experiment_id=experiment,
            prefix=prefix,
        )
        for warning in listing.warnings:
            typer.echo(warning, err=True)
        if output_format == OutputFormat.NDJSON:
            for item in listing.runs:
                _json_line(item.manifest)
        else:
            typer.echo(
                render_run_listing_human(
                    [(item.reference, item.manifest) for item in listing.runs]
                ),
                nl=False,
            )


@app.command("run")
def run_command(
    context: typer.Context,
    run_reference: Annotated[
        str, typer.Argument(callback=_run_reference_argument, metavar="RUN_REF")
    ],
) -> None:
    """Execute a created run."""
    workspace = _state(context).workspace
    with _command_scope(workspace) as commands:
        commands.run(run_reference)


@app.command("resume")
def resume_command(
    context: typer.Context,
    run_reference: Annotated[
        str, typer.Argument(callback=_run_reference_argument, metavar="RUN_REF")
    ],
) -> None:
    """Resume a failed or interrupted run."""
    workspace = _state(context).workspace
    with _command_scope(workspace) as commands:
        commands.resume(run_reference)


@app.command("cancel")
def cancel_command(
    context: typer.Context,
    run_reference: Annotated[
        str, typer.Argument(callback=_run_reference_argument, metavar="RUN_REF")
    ],
) -> None:
    """Request idempotent run cancellation."""
    workspace = _state(context).workspace
    with _command_scope(workspace) as commands:
        commands.cancel(run_reference)


@app.command("inspect")
def inspect_command(
    context: typer.Context,
    run_reference: Annotated[
        str, typer.Argument(callback=_run_reference_argument, metavar="RUN_REF")
    ],
    stage: Annotated[StageId | None, typer.Option("--stage")] = None,
    output_format: Annotated[OutputFormat, typer.Option("--format")] = OutputFormat.HUMAN,
) -> None:
    """Read one run or stage view without mutation."""
    workspace = _state(context).workspace
    with _command_scope(workspace) as commands:
        view = commands.inspect(run_reference, stage=stage)
        if isinstance(view, RunInspection):
            if output_format == OutputFormat.NDJSON:
                _json_line(view)
            else:
                typer.echo(
                    render_run_inspection_human(view, commands.report_summary(view.run.run_id))
                )
        else:
            if output_format == OutputFormat.NDJSON:
                _json_line(view)
            else:
                typer.echo(render_stage_inspection_human(view))


@app.command("export")
def export_command(
    context: typer.Context,
    run_reference: Annotated[
        str, typer.Argument(callback=_run_reference_argument, metavar="RUN_REF")
    ],
) -> None:
    """Regenerate reports from terminal evidence only."""
    workspace = _state(context).workspace
    with _command_scope(workspace) as commands:
        commands.export(run_reference)


def main() -> None:
    """Run the public command-line interface with sysexits-compatible usage errors."""
    try:
        result = app(standalone_mode=False)
        if isinstance(result, int) and result != 0:
            raise SystemExit(result)
    except UsageError as exc:
        typer.echo(f"Usage error: {exc}", err=True)
        raise SystemExit(64) from exc
    except Exit as exc:
        raise SystemExit(exc.exit_code) from exc


if __name__ == "__main__":
    main()
