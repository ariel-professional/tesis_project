"""TTY-only presentation for domain executions."""

from __future__ import annotations

import sys
from typing import TextIO

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TaskProgressColumn, TextColumn

from tesis_domain_extensions.contracts.common import MAX_SAFE_JSON_INTEGER
from tesis_proyect.models.enums import StageId
from tesis_proyect.observation import (
    ExecutionNotification,
    RunCreated,
    RunFinished,
    RunResumed,
    RunStarted,
    StageFinished,
    StageProgress,
    StageStarted,
)

_STAGE_LABELS: dict[StageId, str] = {
    StageId.DEFINE_EXPERIMENT: "verificar la definición del experimento",
    StageId.LOAD_OR_GENERATE_INSTANCE: "materializar el caso",
    StageId.VALIDATE_INSTANCE_EDGES: "validar las restricciones",
    StageId.VALIDATE_LINEAR_FOREST: "validar la estructura lineal",
    StageId.ANALYZE_STRUCTURE: "analizar la estructura",
    StageId.RUN_EXACT_METHOD: "ejecutar el método exacto",
    StageId.RUN_REFERENCE_METHOD: "ejecutar el método de referencia",
    StageId.COMPARE_RESULTS: "comparar resultados",
    StageId.COLLECT_METRICS: "reunir métricas",
    StageId.EXPORT_REPORT: "exportar el reporte",
}


class DomainTerminalObserver:
    """Render one transient domain-owned progress region from CORE notifications."""

    def __init__(self, *, stream: TextIO | None = None, enabled: bool | None = None) -> None:
        target = stream if stream is not None else sys.stderr
        detected = bool(getattr(target, "isatty", lambda: False)())
        self.enabled = detected if enabled is None else enabled
        self.console = Console(
            file=target,
            force_terminal=self.enabled,
            color_system="auto",
            legacy_windows=False,
        )
        self.progress: Progress | None = None
        self.task: TaskID | None = None
        self.generation_task: TaskID | None = None
        self.active_case: str | None = None

    def notify(self, notification: ExecutionNotification) -> None:
        if not self.enabled:
            return
        if isinstance(notification, RunCreated):
            self._update("Run creado; preparando la ejecución…")
        elif isinstance(notification, RunStarted):
            self._update("Ejecución de dominio iniciada…")
        elif isinstance(notification, RunResumed):
            self._update("Reanudando la ejecución de dominio…")
        elif isinstance(notification, StageStarted):
            self._update(
                f"Etapa {notification.ordinal}/{notification.total_stages}: "
                f"{_STAGE_LABELS[notification.stage]}…",
                completed=0,
                total=None,
            )
        elif isinstance(notification, StageProgress):
            self._update(
                f"Procesando {_STAGE_LABELS[notification.stage]}…",
                completed=notification.completed,
                total=notification.total,
            )
        elif isinstance(notification, StageFinished):
            self._update(
                f"Etapa {notification.ordinal}/{notification.total_stages} "
                f"finalizada: {notification.status.value}"
            )
        elif isinstance(notification, RunFinished):
            self._update(f"Ejecución finalizada: {notification.status.value}")

    def set_status(self, message: str) -> None:
        if self.enabled:
            self._update(message)

    def generation_started(self, total: int) -> None:
        if self.enabled:
            self._update_generation(completed=0, total=total)

    def generation_progress(
        self, completed: int, total: int, valid_selections: int | None = None
    ) -> None:
        del valid_selections
        if self.enabled:
            self._update_generation(completed=completed, total=total)

    def core_case_started(
        self,
        ordinal: int,
        description: str,
        core_run_id: str | None = None,
        design_id: str | None = None,
    ) -> None:
        del core_run_id, design_id
        if self.enabled:
            self.active_case = f"Caso CORE {ordinal} \u2014 {description}"
            self._update("Preparando etapas CORE\u2026")

    def close(self) -> None:
        if self.progress is not None:
            self.progress.stop()
        self.progress = None
        self.task = None
        self.generation_task = None
        self.active_case = None

    @staticmethod
    def _safe_progress(completed: int, total: int) -> bool:
        return 0 <= completed <= MAX_SAFE_JSON_INTEGER and 0 <= total <= MAX_SAFE_JSON_INTEGER

    @staticmethod
    def _magnitude(value: int) -> str:
        if value == 0:
            return "0"
        return f"2^{value.bit_length() - 1}"

    def _update_generation(self, *, completed: int, total: int) -> None:
        if self._safe_progress(completed, total):
            description = "Combinaciones evaluadas"
            safe_completed: int | None = completed
            safe_total: int | None = total
        else:
            description = (
                "Combinaciones evaluadas: "
                f"avance de orden {self._magnitude(completed)}; "
                f"total de orden {self._magnitude(total)}; porcentaje no disponible"
            )
            safe_completed = 0
            safe_total = None
        if self.progress is None:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console,
                transient=True,
            )
            self.progress.start()
        if self.generation_task is None:
            self.generation_task = self.progress.add_task(description, total=safe_total)
        self.progress.update(
            self.generation_task,
            description=description,
            completed=safe_completed,
            total=safe_total,
        )

    def _update(
        self,
        description: str,
        *,
        completed: int | None = None,
        total: int | None = None,
    ) -> None:
        if self.active_case is not None:
            description = f"{self.active_case} \u2014 {description}"
        if (
            completed is not None
            and total is not None
            and not self._safe_progress(completed, total)
        ):
            completed = 0
            total = None
        if self.progress is None:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console,
                transient=True,
            )
            self.progress.start()
            self.task = self.progress.add_task(description, total=total)
            if completed is not None:
                self.progress.update(self.task, completed=completed)
            return
        if self.task is None:
            self.task = self.progress.add_task(description, total=total)
        self.progress.update(
            self.task,
            description=description,
            completed=completed if completed is not None else 0,
            total=total,
        )
