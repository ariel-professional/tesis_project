"""Presentation-neutral command facade shared by the bundled CLI adapters."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from tesis_proyect.application.experiments import ExperimentService
from tesis_proyect.application.export import ReportExportService
from tesis_proyect.application.inspection import RunListing, RunQueryService
from tesis_proyect.application.operations import RunOperations
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import ArtifactRef, RunId, StructuredError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import ErrorCode, StageId
from tesis_proyect.models.execution import RunManifest
from tesis_proyect.models.factories import structured_error
from tesis_proyect.models.protocols import (
    ControlRequest,
    ControlResponse,
    EventEnvelope,
    RunInspection,
    StageInspection,
)
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.observation import (
    CommandFinished,
    CommandStarted,
    CompositeExecutionObserver,
    DiagnosticRaised,
    ExecutionNotification,
    ExecutionObserver,
    NullExecutionObserver,
    PublicEventObserver,
    ReportExported,
    RunFinished,
)
from tesis_proyect.persistence.run_repository import RunRepository
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.runner.clock import utc_timestamp


@dataclass(frozen=True)
class ExportResult:
    report: ReportSummary
    json_report: ArtifactRef
    markdown_report: ArtifactRef
    manifest: RunManifest


def classify_command_error(exc: Exception) -> tuple[ErrorCode, str]:
    """Translate an application failure to the existing public diagnostic contract."""

    if isinstance(exc, OperationalError):
        return exc.code, str(exc)
    if isinstance(exc, ValidationError):
        return ErrorCode.CONFIG_INVALID, "Input violates the public contract."
    return ErrorCode.INTERNAL_ERROR, "An internal error occurred."


class _PersistentEventObserver:
    """Persist public events as a CORE invariant, independently of presentation."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.public = PublicEventObserver(self._persist)

    def notify(self, notification: ExecutionNotification) -> None:
        self.public.notify(notification)

    def _persist(self, event: EventEnvelope) -> None:
        if event.run_id is None:
            return
        repository = RunRepository(self.workspace, event.run_id)
        try:
            config = repository.load_config()
        except OperationalError:
            return
        if not config.persistence.persist_events:
            return
        line = json.dumps(
            event.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        payload = (line + "\n").encode("utf-8")
        if len(payload) > config.integer_limits.event_max_payload_bytes:
            raise OperationalError(ErrorCode.IO_ERROR, "Event exceeds its payload limit.")
        path = self.workspace.resolve(f"{repository.layout.root}/logs/events.ndjson")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(payload)
            handle.flush()


class CoreCommands:
    """Execute CORE use cases without depending on a CLI or output transport."""

    def __init__(
        self,
        workspace: Workspace,
        *,
        observer: ExecutionObserver | None = None,
    ) -> None:
        self.workspace = workspace
        self.output = CompositeExecutionObserver(
            _PersistentEventObserver(workspace),
            observer or NullExecutionObserver(),
        )

    @classmethod
    def open(
        cls,
        workspace: Path,
        *,
        observer: ExecutionObserver | None = None,
    ) -> CoreCommands:
        return cls(Workspace.open(workspace), observer=observer)

    @property
    def workspace_root(self) -> Path:
        return self.workspace.root

    def load_experiment(self, experiment_id: str) -> ExperimentConfig:
        return ExperimentService(self.workspace).load_experiment(experiment_id)

    def short_run_reference(self, run_id: str) -> str:
        return RunQueryService(self.workspace).short_reference(run_id)

    def resolve_run_reference(self, reference: str) -> str:
        return RunQueryService(self.workspace).resolve_run_reference(reference)

    def inspect_run(self, reference: str) -> RunInspection:
        run_id = self.resolve_run_reference(reference)
        return RunQueryService(self.workspace).inspect_run(run_id)

    def report_summary(self, reference: str) -> ReportSummary:
        run_id = self.resolve_run_reference(reference)
        return RunQueryService(self.workspace).report_summary(run_id)

    def save_experiment(
        self,
        experiment_id: str,
        config: ExperimentConfig | Path,
    ) -> None:
        with self._command("save-experiment"):
            service = ExperimentService(self.workspace, observer=self.output)
            validated = service.load_config_file(config) if isinstance(config, Path) else config
            service.save_experiment(experiment_id, validated)
            self._finish("save-experiment", experiment_id=experiment_id)

    def create_run(self, experiment_id: str) -> RunManifest:
        with self._command("create-run"):
            manifest = ExperimentService(self.workspace, observer=self.output).create_run(
                experiment_id
            )
            self._finish(
                "create-run",
                run_id=manifest.run_id,
                experiment_id=experiment_id,
                manifest=manifest,
            )
            return manifest

    def list_runs(
        self,
        *,
        experiment_id: str | None = None,
        prefix: str | None = None,
    ) -> RunListing:
        with self._command("list-runs"):
            listing = RunQueryService(self.workspace).list_runs(
                experiment_id=experiment_id,
                prefix=prefix,
            )
            self._finish("list-runs")
            return listing

    def run(self, reference: str) -> RunManifest:
        with self._command("run", run_reference=reference):
            run_id = self.resolve_run_reference(reference)
            manifest = RunOperations(self.workspace, observer=self.output).run(run_id)
            self._finish("run", run_id=run_id, manifest=manifest)
            return manifest

    def resume(self, reference: str) -> RunManifest:
        with self._command("resume", run_reference=reference):
            run_id = self.resolve_run_reference(reference)
            manifest = RunOperations(self.workspace, observer=self.output).resume(run_id)
            self._finish("resume", run_id=run_id, manifest=manifest)
            return manifest

    def cancel(
        self,
        reference: str,
        *,
        reason: str | None = None,
    ) -> ControlResponse:
        with self._command("cancel", run_reference=reference):
            run_id = self.resolve_run_reference(reference)
            response = RunOperations(self.workspace, observer=self.output).cancel(
                ControlRequest(
                    schema_version="1.0.0",
                    request_id=str(uuid4()),
                    command="cancel",
                    run_id=run_id,
                    requested_at=utc_timestamp(),
                    origin="cli",
                    reason=reason,
                )
            )
            manifest = RunQueryService(self.workspace).inspect_run(run_id).run
            if response.status == "terminal":
                self.output.notify(
                    RunFinished(run_id=run_id, timestamp=utc_timestamp(), status=manifest.status)
                )
            self._finish("cancel", run_id=run_id, manifest=manifest)
            return response

    def inspect(
        self,
        reference: str,
        *,
        stage: StageId | None = None,
    ) -> RunInspection | StageInspection:
        with self._command("inspect", run_reference=reference):
            run_id = self.resolve_run_reference(reference)
            queries = RunQueryService(self.workspace)
            view: RunInspection | StageInspection
            if stage is None:
                view = queries.inspect_run(run_id)
                status = view.run.status
            else:
                view = queries.inspect_stage(run_id, stage)
                status = queries.inspect_run(run_id).run.status
            self.output.notify(
                CommandFinished(
                    command="inspect",
                    outcome="success",
                    run_id=run_id,
                    run_status=status,
                )
            )
            return view

    def export(self, reference: str) -> ExportResult:
        with self._command("export", run_reference=reference):
            run_id = self.resolve_run_reference(reference)
            report, json_ref, markdown_ref = ReportExportService(self.workspace).export(run_id)
            self.output.notify(
                ReportExported(
                    run_id=run_id,
                    timestamp=utc_timestamp(),
                    json_report=json_ref,
                    markdown_report=markdown_ref,
                )
            )
            manifest = RunQueryService(self.workspace).inspect_run(run_id).run
            self._finish("export", run_id=run_id, manifest=manifest)
            return ExportResult(
                report=report,
                json_report=json_ref,
                markdown_report=markdown_ref,
                manifest=manifest,
            )

    def _finish(
        self,
        command: str,
        *,
        run_id: str | None = None,
        experiment_id: str | None = None,
        manifest: RunManifest | None = None,
    ) -> None:
        self.output.notify(
            CommandFinished(
                command=command,
                outcome="success",
                run_id=run_id,
                experiment_id=experiment_id,
                run_status=manifest.status if manifest is not None else None,
            )
        )

    @contextmanager
    def _command(
        self,
        command: str,
        *,
        run_reference: str | None = None,
    ) -> Iterator[None]:
        self.output.notify(CommandStarted(command=command))
        try:
            yield
        except Exception as exc:
            code, message = classify_command_error(exc)
            self.output.notify(
                DiagnosticRaised(
                    run_id=self._diagnostic_run_id(run_reference),
                    timestamp=utc_timestamp(),
                    error=structured_error(code, message),
                )
            )
            self.output.notify(
                CommandFinished(command=command, outcome="error", run_id=run_reference)
            )
            raise

    @staticmethod
    def _diagnostic_run_id(reference: str | None) -> str | None:
        if reference is None:
            return None
        with suppress(ValidationError):
            return TypeAdapter(RunId).validate_python(reference)
        return None


def command_error(exc: Exception) -> StructuredError:
    code, message = classify_command_error(exc)
    return structured_error(code, message)
