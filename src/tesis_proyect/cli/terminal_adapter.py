from __future__ import annotations

import os
import shlex
import subprocess
import sys
from math import isfinite
from typing import TextIO

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    Task,
    TaskID,
    TaskProgressColumn,
    TextColumn,
)
from rich.text import Text

from tesis_proyect.application.inspection import RunQueryService
from tesis_proyect.models.enums import STAGE_ORDER, RunStatus, StageId
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.models.stages import (
    CandidateOutcome,
    ComparisonOutcome,
    DefinitionOutcome,
    EdgeValidationOutcome,
    ExactOutcome,
    ForestValidationOutcome,
    MetricsOutcome,
    ReferenceOutcome,
    ReportOutcome,
    StageResult,
    StructureOutcome,
)
from tesis_proyect.observation import (
    CommandFinished,
    CommandStarted,
    DiagnosticRaised,
    ExecutionNotification,
    RunFinished,
    StageFinished,
    StageProgress,
    StageStarted,
)
from tesis_proyect.persistence.workspace import Workspace

_LABELS: dict[StageId, str] = {
    StageId.DEFINE_EXPERIMENT: "Define experiment",
    StageId.LOAD_OR_GENERATE_INSTANCE: "Load or generate instance",
    StageId.VALIDATE_INSTANCE_EDGES: "Validate instance edges",
    StageId.VALIDATE_LINEAR_FOREST: "Validate linear forest",
    StageId.ANALYZE_STRUCTURE: "Analyze structure",
    StageId.RUN_EXACT_METHOD: "Run exact method",
    StageId.RUN_REFERENCE_METHOD: "Run reference method",
    StageId.COMPARE_RESULTS: "Compare results",
    StageId.COLLECT_METRICS: "Collect metrics",
    StageId.EXPORT_REPORT: "Export report",
}

_MINUTE_SECONDS = 60
_HOUR_SECONDS = 60 * _MINUTE_SECONDS
_DAY_SECONDS = 24 * _HOUR_SECONDS
_MONTH_SECONDS = 30 * _DAY_SECONDS
_YEAR_SECONDS = 365 * _DAY_SECONDS


def _quantity(value: int, singular: str, plural: str) -> str:
    number = f"{value:,}".replace(",", ".")
    return f"{number} {singular if value == 1 else plural}"


def _join_duration_parts(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} con {parts[1]}"
    return f"{parts[0]} con {parts[1]} y {parts[2]}"


def _format_subday_duration(total_seconds: int) -> str:
    if total_seconds < _MINUTE_SECONDS:
        return _quantity(total_seconds, "segundo", "segundos")
    if total_seconds < _HOUR_SECONDS:
        minutes, remaining_seconds = divmod(total_seconds, _MINUTE_SECONDS)
        parts = [_quantity(minutes, "minuto", "minutos")]
        if remaining_seconds:
            parts.append(_quantity(remaining_seconds, "segundo", "segundos"))
        return _join_duration_parts(parts)
    hours, remainder = divmod(total_seconds, _HOUR_SECONDS)
    minutes, remaining_seconds = divmod(remainder, _MINUTE_SECONDS)
    parts = [_quantity(hours, "hora", "horas")]
    if minutes:
        parts.append(_quantity(minutes, "minuto", "minutos"))
    if remaining_seconds:
        parts.append(_quantity(remaining_seconds, "segundo", "segundos"))
    return _join_duration_parts(parts)


def _format_multiday_duration(total_seconds: int) -> str:
    if total_seconds < _MONTH_SECONDS:
        days, remainder = divmod(total_seconds, _DAY_SECONDS)
        hours = remainder // _HOUR_SECONDS
        parts = [_quantity(days, "día", "días")]
        if hours:
            parts.append(_quantity(hours, "hora", "horas"))
        return _join_duration_parts(parts)
    if total_seconds < _YEAR_SECONDS:
        months, remainder = divmod(total_seconds, _MONTH_SECONDS)
        days = remainder // _DAY_SECONDS
        parts = [_quantity(months, "mes", "meses")]
        if days:
            parts.append(_quantity(days, "día", "días"))
        return _join_duration_parts(parts)
    years, remainder = divmod(total_seconds, _YEAR_SECONDS)
    months = remainder // _MONTH_SECONDS
    parts = [_quantity(years, "año", "años")]
    if months:
        parts.append(_quantity(months, "mes", "meses"))
    return _join_duration_parts(parts)


def format_human_duration(seconds: float | int) -> str:
    """Render a non-negative duration with adaptive deterministic precision."""

    total_seconds = max(0, int(seconds))
    if total_seconds < _DAY_SECONDS:
        return _format_subday_duration(total_seconds)
    return _format_multiday_duration(total_seconds)


class _HumanDurationColumn(ProgressColumn):
    def __init__(self, label: str, *, remaining: bool = False) -> None:
        super().__init__()
        self.label = label
        self.remaining = remaining

    def render(self, task: Task) -> Text:
        if self.remaining:
            duration = task.time_remaining
            style = "progress.remaining"
            if duration is None or not isfinite(duration):
                return Text(f"{self.label}: calculando…", style=style)
        else:
            duration = task.finished_time if task.finished else task.elapsed
            style = "progress.elapsed"
            if duration is None or not isfinite(duration):
                duration = 0
        return Text(f"{self.label}: {format_human_duration(duration)}", style=style)


class TerminalUiObserver:
    """Best-effort interactive terminal presentation for execution notifications."""

    def __init__(
        self,
        workspace: Workspace,
        *,
        stream: TextIO | None = None,
        enabled: bool | None = None,
        queries: RunQueryService | None = None,
    ) -> None:
        target = stream if stream is not None else sys.stderr
        detected = bool(getattr(target, "isatty", lambda: False)())
        self.enabled = detected if enabled is None else enabled
        self.workspace = workspace
        self.queries = queries or RunQueryService(workspace)
        self.console = Console(
            file=target,
            force_terminal=self.enabled,
            color_system="auto",
            legacy_windows=False,
        )
        self.transient_progress = stream is None
        self.progress: Progress | None = None
        self.progress_task: TaskID | None = None

    def notify(self, notification: ExecutionNotification) -> None:
        if not self.enabled:
            return
        if isinstance(notification, CommandStarted):
            self.console.print(f"[bold]Command:[/bold] {notification.command}")
            self.console.print("Status: running")
        elif isinstance(notification, StageStarted):
            self._stage_started(notification)
        elif isinstance(notification, StageProgress):
            self._stage_progress(notification)
        elif isinstance(notification, StageFinished):
            self._stage_finished(notification)
        elif isinstance(notification, RunFinished):
            self._run_finished(notification)
        elif isinstance(notification, CommandFinished):
            self._command_finished(notification)
        elif isinstance(notification, DiagnosticRaised):
            self._stop_progress()

    def close(self) -> None:
        self._stop_progress()

    def _stage_started(self, notice: StageStarted) -> None:
        self._stop_progress()
        self.console.print()
        self.console.print(
            f"[bold]Stage {notice.ordinal}/{notice.total_stages} — {_LABELS[notice.stage]}[/bold]"
        )
        self.console.print("Status: running")
        self.console.print(f"Attempt: {notice.attempt}")
        if notice.stage in {StageId.RUN_EXACT_METHOD, StageId.RUN_REFERENCE_METHOD}:
            self.progress = Progress(
                TextColumn("Progress:"),
                BarColumn(),
                TaskProgressColumn(),
                _HumanDurationColumn("Transcurrido"),
                _HumanDurationColumn("Restante estimado", remaining=True),
                console=self.console,
                transient=self.transient_progress,
            )
            self.progress.start()
            self.progress_task = self.progress.add_task("counting", total=None)

    def _stage_progress(self, notice: StageProgress) -> None:
        if self.progress is None or self.progress_task is None:
            return
        total = float(notice.total) if notice.total is not None else None
        self.progress.update(self.progress_task, completed=notice.completed, total=total)

    def _stage_finished(self, notice: StageFinished) -> None:
        self._stop_progress()
        result = self.queries.inspect_stage(notice.run_id, notice.stage).result
        heading = f"Stage {notice.ordinal}/{notice.total_stages} finished — {notice.status.value}"
        self.console.print(f"[bold]{heading}[/bold]")
        self.console.print(f"Result: {self._stage_summary(notice.run_id, result)}")
        if notice.ordinal < notice.total_stages:
            next_stage = STAGE_ORDER[notice.ordinal]
            self.console.print(
                f"Next: Stage {notice.ordinal + 1}/{notice.total_stages} — {_LABELS[next_stage]}"
            )
        else:
            self.console.print("Next: Finish run")

    def _stage_summary(self, run_id: str, result: StageResult) -> str:
        if result.error is not None:
            return f"{result.error.code} — {result.error.message}"
        attempt = result.attempts[-1]
        if attempt.skip is not None:
            return f"{attempt.skip.code} — {attempt.skip.message}"
        report = self.queries.report_summary(run_id)
        summary = self._outcome_summary(result, report)
        return summary or f"Stage finished with status {result.status.value}."

    def _outcome_summary(self, result: StageResult, report: ReportSummary) -> str | None:
        outcome = result.outcome
        if isinstance(outcome, DefinitionOutcome):
            return "Experiment configuration and run hash verified."
        if isinstance(outcome, CandidateOutcome):
            return "Instance candidate materialized."
        if isinstance(outcome, EdgeValidationOutcome):
            count = len(report.instance.edges) if report.instance is not None else 0
            return f"{count} edges validated and normalized; canonical instance created."
        if isinstance(outcome, ForestValidationOutcome):
            return "The instance is acyclic and has maximum degree 2."
        if isinstance(outcome, StructureOutcome):
            return self._structure_summary(report)
        if isinstance(outcome, (ExactOutcome, ReferenceOutcome)):
            return self._counting_summary(outcome, report)
        if isinstance(outcome, ComparisonOutcome):
            return self._comparison_summary(report)
        if isinstance(outcome, MetricsOutcome):
            return f"Metrics consolidated for {len(outcome.stages)} stage attempts."
        if isinstance(outcome, ReportOutcome):
            return (
                f"Reports generated: {outcome.json_report.path} and {outcome.markdown_report.path}."
            )
        return None

    @staticmethod
    def _structure_summary(report: ReportSummary) -> str | None:
        structure = report.structure
        if structure is None:
            return None
        return (
            f"Case {structure.case_type}; {len(structure.components)} components; "
            f"{structure.free_vertex_count} free vertices; {structure.blocks} blocks."
        )

    @staticmethod
    def _comparison_summary(report: ReportSummary) -> str | None:
        comparison = report.comparison
        if comparison is None:
            return None
        if comparison.status == "not_applicable":
            return "No exact/reference comparison was applicable."
        return (
            f"{comparison.status.value.replace('_', ' ').title()} — exact "
            f"{comparison.value_exact}; reference {comparison.value_reference}."
        )

    @staticmethod
    def _counting_summary(
        outcome: ExactOutcome | ReferenceOutcome, report: ReportSummary
    ) -> str | None:
        counting = (
            report.methods.exact if isinstance(outcome, ExactOutcome) else report.methods.reference
        )
        name = "Exact" if isinstance(outcome, ExactOutcome) else "Reference"
        if counting is None or counting.status != "success":
            return None
        examined = counting.metrics.candidates_examined
        suffix = f" after examining {examined} candidates" if examined is not None else ""
        return f"{name} method counted {counting.value} undirected paths{suffix}."

    def _run_finished(self, notice: RunFinished) -> None:
        self._stop_progress()
        report = self.queries.report_summary(notice.run_id)
        self.console.print()
        self.console.print(f"[bold]Run finished — {notice.status.value}[/bold]")
        if report.diagnostics:
            first = report.diagnostics[0]
            self.console.print(f"Result: {first.code} — {first.message}")
        elif report.methods.reference is not None and report.methods.reference.status == "success":
            exact = report.methods.exact
            exact_text = "exact method unavailable"
            if exact is not None and exact.status == "success":
                exact_text = f"exact count {exact.value}"
            comparison = (
                report.comparison.status.value if report.comparison is not None else "unavailable"
            )
            self.console.print(
                f"Result: Reference count {report.methods.reference.value}; {exact_text}; "
                f"comparison {comparison}."
            )
        else:
            self.console.print("Result: No conclusive scientific result is available.")
        self.console.print(f"Report: runs/{notice.run_id}/reports/report.md")
        self._next_command("inspect", notice.run_id, "--format", "human")

    def _command_finished(self, notice: CommandFinished) -> None:
        if notice.command in {"run", "resume"}:
            return
        self.console.print()
        self.console.print(f"[bold]{notice.command} finished — {notice.outcome}[/bold]")
        if notice.command == "save-experiment" and notice.experiment_id is not None:
            self.console.print(f"Result: Experiment {notice.experiment_id} saved.")
            self._next_command("create-run", "--experiment", notice.experiment_id)
        elif notice.command == "create-run" and notice.run_id is not None:
            self.console.print(f"Result: Run {notice.run_id} created.")
            reference = self.queries.short_reference(notice.run_id)
            self.console.print(f"Short reference: {reference}")
            self._next_command("run", reference)
        elif notice.command == "export" and notice.run_id is not None:
            self.console.print("Result: JSON and Markdown reports regenerated.")
            self._next_command("inspect", notice.run_id, "--format", "human")
        elif notice.run_id is not None:
            if notice.command == "inspect" and notice.run_status == RunStatus.CREATED:
                self._next_command("run", notice.run_id)
            elif notice.command == "inspect" and notice.run_status == RunStatus.FAILED:
                self._next_command("resume", notice.run_id)
            elif notice.command == "inspect" and notice.run_status == RunStatus.RUNNING:
                self._next_command("inspect", notice.run_id, "--format", "human")
            elif notice.command == "inspect":
                self._next_command("export", notice.run_id)
            else:
                self._next_command("inspect", notice.run_id, "--format", "human")

    def _next_command(self, *arguments: str) -> None:
        tokens = ["tesis-proyect", "--workspace", str(self.workspace.root), *arguments]
        command = subprocess.list2cmdline(tokens) if os.name == "nt" else shlex.join(tokens)
        self.console.print("\n[bold]Next command:[/bold]")
        self.console.print(command, markup=False)

    def _stop_progress(self) -> None:
        if self.progress is not None:
            self.progress.stop()
        self.progress = None
        self.progress_task = None
