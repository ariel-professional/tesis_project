"""Report export use case."""

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import ArtifactRef
from tesis_proyect.models.enums import ErrorCode, RunStatus
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.persistence.run_repository import RunRepository
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.reporting.builder import ReportBuilder
from tesis_proyect.reporting.render import render_json, render_markdown
from tesis_proyect.runner.locking import RunExecutionLock


class ReportExportService:
    """Regenerate reports for a terminal run under the run lock."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def export(self, run_id: str) -> tuple[ReportSummary, ArtifactRef, ArtifactRef]:
        repository = RunRepository(self.workspace, run_id)
        with RunExecutionLock(self.workspace.resolve(repository.layout.lock, must_exist=True)):
            manifest = repository.load_manifest()
            if manifest.status not in {
                RunStatus.COMPLETED,
                RunStatus.FAILED,
                RunStatus.CANCELLED,
            }:
                raise OperationalError(
                    ErrorCode.RUN_STATE_INVALID, "Export requires a terminal run."
                )
            report = ReportBuilder(repository).build()
            json_ref = repository.store.write_bytes(
                repository.layout.report("result.json"), render_json(report)
            )
            markdown_ref = repository.store.write_bytes(
                repository.layout.report("report.md"), render_markdown(report).encode("utf-8")
            )
            return report, json_ref, markdown_ref
