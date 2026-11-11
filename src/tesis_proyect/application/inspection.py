from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import ExperimentId, RunId
from tesis_proyect.models.enums import ErrorCode, StageId
from tesis_proyect.models.execution import RunManifest
from tesis_proyect.models.protocols import RunInspection, StageInspection
from tesis_proyect.models.reports import ReportSummary
from tesis_proyect.persistence.run_repository import RunRepository
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.reporting.builder import ReportBuilder

_RUN_ID_ADAPTER = TypeAdapter(RunId)
_EXPERIMENT_ID_ADAPTER = TypeAdapter(ExperimentId)
_CANONICAL_HYPHEN_POSITIONS = frozenset({8, 12, 16, 20})


@dataclass(frozen=True)
class ListedRun:
    reference: str
    manifest: RunManifest


@dataclass(frozen=True)
class RunListing:
    runs: tuple[ListedRun, ...]
    warnings: tuple[str, ...]


def normalize_run_prefix(value: str, *, minimum_length: int) -> str:
    """Validate a CLI UUID prefix and return lowercase hexadecimal digits only."""

    if not value:
        raise ValueError("Run ID prefix must not be empty.")
    compact: list[str] = []
    hyphen_positions: set[int] = set()
    for character in value:
        if character == "-":
            if len(compact) not in _CANONICAL_HYPHEN_POSITIONS or len(compact) in hyphen_positions:
                raise ValueError("Run ID prefix has a hyphen outside a canonical UUID position.")
            hyphen_positions.add(len(compact))
            continue
        if character.lower() not in "0123456789abcdef":
            raise ValueError("Run ID prefix must contain only hexadecimal characters.")
        compact.append(character.lower())
    if len(compact) < minimum_length:
        raise ValueError(
            f"Run ID prefix must contain at least {minimum_length} hexadecimal character(s)."
        )
    if len(compact) > 32:
        raise ValueError("Run ID prefix must contain at most 32 hexadecimal characters.")
    return "".join(compact)


def validate_experiment_id(value: str) -> str:
    """Return a canonical experiment filter or a concise validation failure."""

    try:
        return _EXPERIMENT_ID_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ValueError("Experiment filter is not a valid experiment ID.") from exc


def _compact_run_id(run_id: str) -> str:
    return run_id.replace("-", "")


def _is_temporary_run_name(name: str) -> bool:
    return name.startswith(".") and ".creating-" in name


class RunQueryService:
    """Read confirmed run evidence without mutating the workspace."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def inspect_run(self, run_id: str) -> RunInspection:
        repository = RunRepository(self.workspace, run_id)
        return RunInspection(
            schema_version="1.0.0",
            view="run",
            run=repository.load_manifest(),
            pipeline=repository.load_pipeline(),
        )

    def inspect_stage(self, run_id: str, stage: StageId) -> StageInspection:
        result = RunRepository(self.workspace, run_id).load_stage(stage)
        return StageInspection(
            schema_version="1.0.0", view="stage", run_id=run_id, stage=stage, result=result
        )

    def report_summary(self, run_id: str) -> ReportSummary:
        return ReportBuilder(RunRepository(self.workspace, run_id)).build()

    def resolve_run_reference(self, reference: str) -> str:
        """Resolve an exact UUID cheaply or a unique compact prefix by directory name."""

        try:
            return _RUN_ID_ADAPTER.validate_python(reference)
        except ValidationError:
            prefix = normalize_run_prefix(reference, minimum_length=8)
        matches = [
            run_id
            for run_id in self._canonical_run_ids()
            if _compact_run_id(run_id).startswith(prefix)
        ]
        if not matches:
            raise OperationalError(ErrorCode.NOT_FOUND, "Run was not found.")
        if len(matches) > 1:
            raise OperationalError(
                ErrorCode.ID_COLLISION,
                f"Run reference '{reference}' is ambiguous; use list-runs --prefix "
                f'"{reference}" and provide more characters.',
            )
        return matches[0]

    def short_reference(self, run_id: str) -> str:
        """Return the shortest currently unique compact reference, with eight digits minimum."""

        run_ids = self._canonical_run_ids()
        if run_id not in run_ids:
            run_ids.append(run_id)
        return self._short_references(run_ids)[run_id]

    def list_runs(
        self,
        *,
        experiment_id: str | None = None,
        prefix: str | None = None,
    ) -> RunListing:
        """List validated manifests, omitting damaged candidates with human warnings."""

        normalized_prefix = (
            normalize_run_prefix(prefix, minimum_length=1) if prefix is not None else None
        )
        validated_experiment = (
            validate_experiment_id(experiment_id) if experiment_id is not None else None
        )
        entries = self._run_entries()
        canonical_ids = self._canonical_ids(entries)
        references = self._short_references(canonical_ids)
        manifests: list[RunManifest] = []
        warnings: list[str] = []
        for entry in entries:
            if _is_temporary_run_name(entry.name):
                continue
            if normalized_prefix is not None and not _compact_run_id(entry.name).lower().startswith(
                normalized_prefix
            ):
                continue
            warning = self._entry_warning(entry)
            if warning is not None:
                warnings.append(warning)
                continue
            try:
                run_id = _RUN_ID_ADAPTER.validate_python(entry.name)
                manifest = RunRepository(self.workspace, run_id).load_manifest()
            except (OperationalError, ValidationError):
                warnings.append(
                    f"Warning: skipped runs/{entry.name}: run.json is missing or invalid."
                )
                continue
            if manifest.run_id != run_id:
                warnings.append(
                    f"Warning: skipped runs/{entry.name}: manifest run ID does not match "
                    "its directory."
                )
                continue
            if validated_experiment is not None and manifest.experiment_id != validated_experiment:
                continue
            manifests.append(manifest)
        manifests.sort(key=lambda manifest: manifest.run_id)
        manifests.sort(key=lambda manifest: manifest.created_at, reverse=True)
        return RunListing(
            runs=tuple(
                ListedRun(reference=references[manifest.run_id], manifest=manifest)
                for manifest in manifests
            ),
            warnings=tuple(warnings),
        )

    def _run_entries(self) -> list[Path]:
        runs = self.workspace.resolve("runs")
        if not runs.exists():
            return []
        if not runs.is_dir():
            raise OperationalError(ErrorCode.IO_ERROR, "Workspace runs path is not a directory.")
        try:
            return sorted(runs.iterdir(), key=lambda entry: entry.name)
        except OSError as exc:
            raise OperationalError(
                ErrorCode.IO_ERROR, "Run directories could not be listed."
            ) from exc

    def _canonical_run_ids(self) -> list[str]:
        return self._canonical_ids(self._run_entries())

    @staticmethod
    def _canonical_ids(entries: list[Path]) -> list[str]:
        result: list[str] = []
        for entry in entries:
            if _is_temporary_run_name(entry.name) or entry.is_symlink() or not entry.is_dir():
                continue
            try:
                result.append(_RUN_ID_ADAPTER.validate_python(entry.name))
            except ValidationError:
                continue
        return result

    @staticmethod
    def _entry_warning(entry: Path) -> str | None:
        relative = f"runs/{entry.name}"
        if entry.is_symlink():
            return f"Warning: skipped {relative}: path is a symlink."
        if not entry.is_dir():
            return f"Warning: skipped {relative}: entry is not a directory."
        try:
            _RUN_ID_ADAPTER.validate_python(entry.name)
        except ValidationError:
            return f"Warning: skipped {relative}: directory name is not a canonical run ID."
        return None

    @staticmethod
    def _short_references(run_ids: list[str]) -> dict[str, str]:
        compact = {run_id: _compact_run_id(run_id) for run_id in run_ids}
        counts = Counter(
            value[:length] for value in compact.values() for length in range(8, len(value) + 1)
        )
        references: dict[str, str] = {}
        for run_id, value in compact.items():
            references[run_id] = next(
                value[:length] for length in range(8, len(value) + 1) if counts[value[:length]] == 1
            )
        return references
