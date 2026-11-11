"""Domain use cases coordinated independently from either CLI adapter."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Literal, NoReturn, cast
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from tesis_domain_extensions.adapters import (
    CaseGenerationStatistics,
    DomainAdapter,
    GroupedExecutionProgressObserver,
    NullGroupedExecutionProgressObserver,
    ProjectedCase,
)
from tesis_domain_extensions.catalog import resolve_adapter
from tesis_domain_extensions.contracts.common import CoreRunAttempt, large_non_negative_integer
from tesis_domain_extensions.contracts.projection import (
    DomainExperimentSummaryBase,
    DomainRunSummaryBase,
)
from tesis_domain_extensions.deletion import DomainRunDeletionService
from tesis_domain_extensions.errors import DomainExtensionError, DomainRunCancelled
from tesis_domain_extensions.projection_store import (
    LoadedProjection,
    ProjectionListing,
    ProjectionStore,
)
from tesis_proyect.application.commands import CoreCommands
from tesis_proyect.application.inspection import RunListing
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode, StageStatus
from tesis_proyect.models.execution import RunManifest
from tesis_proyect.models.protocols import StageInspection
from tesis_proyect.runner.locking import WorkspaceWriteLock


@dataclass(frozen=True)
class InterpretedRun:
    result: BaseModel
    manifest: Any
    run_reference: str
    domain_experiment_reference: str
    report_path: Path


@dataclass(frozen=True)
class DomainRunListing:
    runs: tuple[DomainRunSummaryBase, ...]
    warnings: tuple[str, ...]


class DomainApplication:
    def __init__(
        self,
        workspace: Path,
        core: CoreCommands,
        *,
        progress_observer: GroupedExecutionProgressObserver | None = None,
        is_cancel_requested: Callable[[], bool] | None = None,
        template_roots: tuple[Path, ...] = (),
    ) -> None:
        self.workspace = workspace
        self.core = core
        self.store = ProjectionStore(workspace, core)
        self.deletion = DomainRunDeletionService(self.store, template_roots)
        self.deletion.recover_pending()
        self.progress_observer = progress_observer or NullGroupedExecutionProgressObserver()
        self.is_cancel_requested = is_cancel_requested or (lambda: False)
        self._active_core_lock = Lock()
        self._active_core_run_id: str | None = None
        self._fast_result_reader_lock = Lock()
        self._fast_result_reader_cache: tuple[str, tuple[tuple[str, str, str], ...], Any] | None = (
            None
        )
        self._fast_result_plot_projection_cache: tuple[tuple[object, ...], Any] | None = None
        self._derived_metrics_cache: tuple[tuple[str, str, str], dict[str, Any]] | None = None

    def validate_payload(self, payload: bytes) -> BaseModel:
        adapter = resolve_adapter(payload)
        return adapter.parse_config(payload)

    def prepare_payload(self, payload: bytes) -> DomainExperimentSummaryBase:
        try:
            adapter = resolve_adapter(payload)
            config = adapter.parse_config(payload)
            return self._summary(self.store.prepare(adapter, config))
        except DomainExtensionError:
            raise
        except (OperationalError, ValidationError, ValueError) as exc:
            raise self._core_error(exc) from exc

    def delete_domain_run(self, domain_run_id: str) -> dict[str, object]:
        """Delete one explicitly selected domain run and its exclusive evidence."""

        result = self.deletion.delete(domain_run_id)
        with self._fast_result_reader_lock:
            if (
                self._fast_result_reader_cache is not None
                and self._fast_result_reader_cache[0] == domain_run_id
            ):
                self._fast_result_reader_cache[2].close()
                self._fast_result_reader_cache = None
            if self._fast_result_plot_projection_cache is not None:
                cache_key = self._fast_result_plot_projection_cache[0]
                if cache_key and cache_key[0] == domain_run_id:
                    self._fast_result_plot_projection_cache = None
            if (
                self._derived_metrics_cache is not None
                and self._derived_metrics_cache[0][0] == domain_run_id
            ):
                self._derived_metrics_cache = None
        return result

    def estimate_payload(self, payload: bytes) -> int:
        adapter = resolve_adapter(payload)
        config = adapter.parse_config(payload)
        adapter.project(config)
        return adapter.theoretical_combinations(config)

    def reserve_grouped_run(self, experiment_reference: str) -> BaseModel:
        loaded = self.store.resolve(experiment_reference)
        if not loaded.adapter.grouped_execution:
            raise DomainExtensionError("El experimento no usa ejecución agrupada.")
        return self._reserve_grouped_run(loaded)

    def execute_grouped_run(self, run_reference: str) -> InterpretedRun:
        return self._execute_grouped_operation(run_reference, resume=False)

    def _execute_grouped_operation(self, reference: str, *, resume: bool) -> InterpretedRun:
        with self.store.domain_execution(reference) as (manifest, adapter):
            if not resume and manifest.status != "created":
                raise DomainExtensionError("Sólo una ejecución creada puede iniciarse.")
            loaded = self.store.load(manifest.domain_experiment_id)
            if adapter is not loaded.adapter:
                raise DomainExtensionError("La ejecución usa otro adaptador de dominio.")
            try:
                manifest = self._activate_grouped_run(adapter, manifest)
                if getattr(manifest, "mode", "standard") == "high_performance":
                    return self._execute_fast_run(loaded, manifest)
                return self._execute_grouped_run(loaded, manifest)
            except DomainRunCancelled:
                raise
            except Exception:
                current, _ = self.store.load_domain_run(manifest.domain_run_id)
                if current.status == "running":
                    self.store.write_domain_run(
                        self._update_group_manifest(adapter, current, status="failed")
                    )
                raise

    def cancel_active_core(self, *, reason: str | None = None) -> str | None:
        with self._active_core_lock:
            run_id = self._active_core_run_id
        if run_id is not None:
            self.core.cancel(run_id, reason=reason)
        return run_id

    def fail_interrupted_high_performance_runs(self) -> int:
        """Mark unfinished direct runs from a previous gateway process as failed."""

        with WorkspaceWriteLock(self.workspace / ".domain-write.lock"):
            return self._fail_interrupted_high_performance_runs()

    def _fail_interrupted_high_performance_runs(self) -> int:
        failed = 0
        for manifest, adapter in self.store.list_domain_runs():
            if getattr(
                manifest, "mode", "standard"
            ) != "high_performance" or manifest.status not in {"created", "running"}:
                continue
            if self.store.domain_run_active(manifest.domain_run_id):
                continue
            run_model = adapter.domain_run_model
            if run_model is None or "failure_reason" not in run_model.model_fields:
                continue
            interrupted = manifest.model_copy(
                update={
                    "status": "failed",
                    "failure_reason": "interrupted",
                    "fast_counters": {},
                    "fast_artifacts": {},
                    "active_started_at": None,
                    "updated_at": self.store.clock(),
                }
            )
            self.store.write_domain_run(interrupted)
            failed += 1
        return failed

    def cancel_interrupted_grouped_run(
        self, run_reference: str, *, reason: str | None = None
    ) -> BaseModel:
        with self.store.domain_execution(run_reference) as (manifest, adapter):
            if manifest.status == "completed":
                raise DomainExtensionError("Una ejecución completada no puede cancelarse.")
            cases = list(manifest.cases)
            for index in range(len(cases) - 1, -1, -1):
                item = cases[index]
                if item.status == "completed":
                    continue
                current = item.attempts[-1]
                if current.status == "running":
                    self.core.cancel(current.core_run_id, reason=reason)
                    core_status = self.core.inspect_run(current.core_run_id).run.status.value
                    cases[index] = self._replace_current_attempt_status(item, core_status)
                break
            cancelled = self._update_group_manifest(
                adapter, manifest, status="cancelled", cases=cases
            )
            self.store.write_domain_run(cancelled)
            return cast(BaseModel, cancelled)

    def prepare(self, config_path: Path) -> DomainExperimentSummaryBase:
        try:
            adapter, config = self._load_config(config_path)
            loaded = self.store.prepare(adapter, config)
            return self._summary(loaded)
        except DomainExtensionError:
            raise
        except (OperationalError, ValidationError, ValueError) as exc:
            raise self._core_error(exc) from exc

    def list_experiments(
        self,
        *,
        domain_id: str | None,
        prefix: str | None,
    ) -> ProjectionListing:
        try:
            return self.store.list_experiments(domain_id=domain_id, prefix=prefix)
        except DomainExtensionError:
            raise
        except (OperationalError, ValidationError, ValueError) as exc:
            raise self._core_error(exc) from exc

    def list_runs(
        self,
        *,
        experiment_reference: str | None,
        domain_id: str | None,
        prefix: str | None,
    ) -> DomainRunListing:
        try:
            experiment_id = None
            if experiment_reference is not None:
                experiment_id = self.store.resolve(experiment_reference).record.domain_experiment_id
            core_listing = self.core.list_runs(experiment_id=experiment_id, prefix=prefix)
            return self._domain_run_listing(
                core_listing,
                domain_id=domain_id,
                experiment_id=experiment_id,
                prefix=prefix,
            )
        except DomainExtensionError:
            raise
        except (OperationalError, ValidationError, ValueError) as exc:
            raise self._core_error(exc) from exc

    def theoretical_combinations(self, experiment_reference: str) -> int:
        try:
            loaded = self.store.resolve(experiment_reference)
            return loaded.adapter.theoretical_combinations(loaded.record.domain_config)
        except DomainExtensionError:
            raise
        except (OperationalError, ValidationError, ValueError) as exc:
            raise self._core_error(exc) from exc

    def run(self, experiment_reference: str) -> InterpretedRun:
        run_id: str | None = None
        try:
            loaded = self.store.resolve(experiment_reference)
            if loaded.adapter.grouped_execution:
                return self._start_grouped_run(loaded)
            manifest = self.core.create_run(loaded.record.domain_experiment_id)
            run_id = manifest.run_id
            self.core.run(run_id)
            return self._interpret(run_id)
        except DomainExtensionError:
            raise
        except (OperationalError, ValidationError, ValueError) as exc:
            if run_id is not None:
                reference = self.core.short_run_reference(run_id)
                raise DomainExtensionError(
                    "El run fue creado pero no pudo completarse.\n"
                    "Continúe la ejecución con:\n"
                    f'  tesis-domain resume {reference} --workspace "{self.workspace}"',
                    exit_code=self._core_exit_code(exc),
                ) from exc
            raise self._core_error(exc) from exc

    def resume(self, run_reference: str) -> InterpretedRun:
        try:
            grouped = self._optional_grouped_run(run_reference)
            if grouped is not None:
                manifest, _adapter = grouped
                if getattr(manifest, "mode", "standard") == "high_performance":
                    raise DomainExtensionError(
                        "Las ejecuciones de alto rendimiento no se pueden reanudar; "
                        "inicie una nueva ejecución."
                    )
                return self._execute_grouped_operation(manifest.domain_run_id, resume=True)
            manifest = self._domain_run_manifest(run_reference, command="resume")
            self.core.resume(manifest.run_id)
            return self._interpret(manifest.run_id)
        except DomainExtensionError:
            raise
        except (OperationalError, ValidationError, ValueError) as exc:
            raise self._core_error(exc) from exc

    def render(self, run_reference: str) -> InterpretedRun:
        try:
            grouped = self._optional_grouped_run(run_reference)
            if grouped is not None:
                with self.store.domain_execution(run_reference) as (manifest, adapter):
                    if getattr(manifest, "mode", "standard") == "high_performance":
                        return self._render_fast_run(manifest, adapter)
                    loaded = self.store.load(manifest.domain_experiment_id)
                    return self._render_grouped_run(loaded, manifest)
            manifest = self._domain_run_manifest(run_reference, command="render")
            return self._interpret(manifest.run_id)
        except DomainExtensionError:
            raise
        except (OperationalError, ValidationError, ValueError) as exc:
            raise self._core_error(exc) from exc

    def confirmed_result(self, run_reference: str) -> BaseModel:
        """Return the immutable result committed by a completed grouped execution."""

        result, _ = self.confirmed_result_document(run_reference)
        return result

    def confirmed_result_document(self, run_reference: str) -> tuple[BaseModel, bytes]:
        """Return a confirmed result and the exact immutable JSON used to validate it."""

        manifest, adapter = self.store.load_domain_run(run_reference)
        if manifest.status != "completed":
            raise DomainExtensionError("La ejecución todavía no tiene un resultado confirmado.")
        result, payload = self.store.load_domain_result_document(manifest.domain_run_id, adapter)
        execution = cast(Any, result).execution
        if isinstance(execution, Mapping):
            result_run_id = execution.get("domain_run_id")
            result_experiment_id = execution.get("domain_experiment_id")
        else:
            result_run_id = execution.domain_run_id
            result_experiment_id = execution.domain_experiment_id
        if (
            result_run_id != manifest.domain_run_id
            or result_experiment_id != manifest.domain_experiment_id
        ):
            raise DomainExtensionError("El resultado confirmado no corresponde a la ejecución.")
        return result, payload

    def query_fast_result(
        self, run_reference: str, operation: str, params: Mapping[str, object]
    ) -> object:
        manifest, adapter = self.store.load_domain_run(run_reference)
        if (
            manifest.status != "completed"
            or getattr(manifest, "mode", "standard") != "high_performance"
        ):
            raise DomainExtensionError("La consulta requiere un resultado rápido confirmado.")
        query = getattr(adapter, "query_high_performance", None)
        if not callable(query):
            raise DomainExtensionError("El adaptador no ofrece consultas indexadas.")
        with self._fast_result_reader_lock:
            return query(self, manifest, adapter, operation, params)

    def query_result_metrics(  # noqa: C901 - validation and verified-reader routing stay together
        self, run_reference: str, params: Mapping[str, object]
    ) -> object:
        """Analyze only a completed SRFL 2.x result, without changing its evidence."""
        from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v2 import (
            SingleRowFacilityLayoutResultV2,
        )
        from tesis_domain_extensions.domains.single_row_facility_layout.contracts_v21 import (
            FastResultSummaryV21,
            SingleRowFacilityLayoutResultV21,
        )
        from tesis_domain_extensions.domains.single_row_facility_layout.metrics import (
            analyze_metric,
        )

        manifest, adapter = self.store.load_domain_run(run_reference)
        if (
            manifest.status != "completed"
            or manifest.domain.id != "single-row-facility-layout"
            or manifest.domain.version not in {"2.0.0", "2.1.0"}
        ):
            raise DomainExtensionError("Las métricas requieren un resultado SRFL 2.x confirmado.")
        metric_id = str(params.get("metric_id", ""))
        design_id = params.get("design_id")
        if design_id is not None and not isinstance(design_id, str):
            raise DomainExtensionError("El diseño solicitado es inválido.")
        if metric_id != "shared-design-patterns" and design_id is None:
            raise DomainExtensionError("La métrica requiere un diseño confirmado.")
        cursor_value = params.get("cursor", 0)
        if type(cursor_value) is not int:
            raise DomainExtensionError("cursor inválido")
        cursor = cursor_value
        designs: list[Any]
        try:
            result: Any = self.store.load_domain_result(manifest.domain_run_id, adapter)
            execution = result.execution
            result_run_id = (
                execution.get("domain_run_id")
                if isinstance(execution, Mapping)
                else execution.domain_run_id
            )
            result_experiment_id = (
                execution.get("domain_experiment_id")
                if isinstance(execution, Mapping)
                else execution.domain_experiment_id
            )
            if (
                result_run_id != manifest.domain_run_id
                or result_experiment_id != manifest.domain_experiment_id
            ):
                raise DomainExtensionError(
                    "El resultado confirmado no corresponde a la ejecución solicitada."
                )
            if isinstance(result, FastResultSummaryV21):
                design_summaries = result.designs
                with self._fast_result_reader_lock:
                    reader = self.fast_result_reader(manifest)
                    cases_by_design: dict[str, list[dict[str, Any]]] = {}
                    for design in design_summaries:
                        if design_id is not None and design.design_id != design_id:
                            continue
                        index = design.order_indexes.get("case")
                        if index is None:
                            raise DomainExtensionError("El índice confirmado de casos no existe.")
                        count = reader.index_count(index)
                        design_cases = [
                            case
                            for page in range((count + 49) // 50)
                            for case in reader.page(index, page)
                        ]
                        if design.frontier_index is not None:
                            frontier_count = reader.index_count(design.frontier_index)
                            frontier_ids = {
                                item.get("case_id")
                                for page in range((frontier_count + 49) // 50)
                                for item in reader.page(design.frontier_index, page)
                            }
                            for case in design_cases:
                                case["pareto_optimal"] = case.get("case_id") in frontier_ids
                        cases_by_design[design.design_id] = design_cases
                designs = [
                    {
                        "design_id": item.design_id,
                        "cases": cases_by_design.get(item.design_id, []),
                        "base_layout_count": item.base_layout_count,
                    }
                    for item in design_summaries
                    if design_id is None or item.design_id == design_id
                ]
                base_count = None
            elif isinstance(
                result, (SingleRowFacilityLayoutResultV2, SingleRowFacilityLayoutResultV21)
            ):
                designs = [
                    item
                    for item in result.designs
                    if design_id is None or item.design_id == design_id
                ]
                base_count = None
            else:
                raise DomainExtensionError("El resultado confirmado no admite análisis SRFL 2.x.")
            objective_ids = {item.definition.id for item in result.objective_snapshots}
            criterion_value = params.get("criterion_id")
            if criterion_value is not None and not isinstance(criterion_value, str):
                raise DomainExtensionError("El criterio solicitado es inválido.")
            criterion_id = criterion_value
            if criterion_id is not None and criterion_id not in objective_ids:
                raise DomainExtensionError("El criterio no pertenece al resultado confirmado.")
            case_value = params.get("case_id")
            if case_value is not None and not isinstance(case_value, str):
                raise DomainExtensionError("El caso solicitado es inválido.")
            case_id = case_value
            known_case_ids: set[str] = set()
            for design_item in designs:
                case_items = (
                    design_item.get("cases", [])
                    if isinstance(design_item, Mapping)
                    else design_item.cases
                )
                for case_item in case_items:
                    known_case_ids.add(
                        str(
                            case_item.get("case_id")
                            if isinstance(case_item, Mapping)
                            else case_item.case_id
                        )
                    )
            if case_id is not None and case_id not in known_case_ids:
                raise DomainExtensionError("El caso no pertenece al resultado confirmado.")
            cache_key = (manifest.domain_run_id, str(design_id or ""), str(criterion_id or ""))
            if metric_id == "pareto-sensitivity" and self._derived_metrics_cache is not None:
                cached_key, cached = self._derived_metrics_cache
                if cached_key == cache_key:
                    rows = cast(list[dict[str, Any]], cached["all_rows"])
                    return {
                        key: value
                        for key, value in {
                            **cached,
                            "rows": rows[cursor : cursor + 50],
                            "next_cursor": cursor + 50
                            if cursor + 50 < int(cached["total"])
                            else None,
                        }.items()
                        if key != "all_rows"
                    }
            response = analyze_metric(
                metric_id=metric_id,
                design_id=design_id,
                criterion_id=criterion_id,
                case_id=case_id,
                cursor=0 if metric_id == "pareto-sensitivity" else cursor,
                designs=designs,
                objectives=result.objective_snapshots,
                base_layout_count=base_count,
                include_all_rows=metric_id == "pareto-sensitivity",
            )
            if metric_id == "pareto-sensitivity":
                all_rows = cast(list[dict[str, Any]], response.pop("all_rows"))
                response["rows"] = all_rows[cursor : cursor + 50]
                response["next_cursor"] = (
                    cursor + 50 if cursor + 50 < int(response["total"]) else None
                )
                self._derived_metrics_cache = (cache_key, {**response, "all_rows": all_rows})
            return response
        except (ValueError, KeyError, IndexError) as exc:
            raise DomainExtensionError(str(exc)) from exc

    def fast_result_reader(self, manifest: Any) -> Any:
        """Reuse the verified positional reader between serialized gateway queries."""

        from tesis_domain_extensions.domains.single_row_facility_layout.fast_result_store import (
            FastResultReader,
        )

        run_id = str(manifest.domain_run_id)
        artifacts = manifest.fast_artifacts or {}
        signature = tuple(
            sorted(
                (name, str(metadata.get("size")), str(metadata.get("sha256")))
                for name, metadata in artifacts.items()
            )
        )
        cached = self._fast_result_reader_cache
        if cached is not None and cached[0] == run_id and cached[1] == signature:
            return cached[2]
        if cached is not None:
            cached[2].close()
            self._fast_result_reader_cache = None
            self._fast_result_plot_projection_cache = None
        root = self.store.results_root / run_id
        reader = FastResultReader(self.workspace, root, artifacts, completed=True)
        self._fast_result_reader_cache = (run_id, signature, reader)
        return reader

    def close(self) -> None:
        with self._fast_result_reader_lock:
            if self._fast_result_reader_cache is not None:
                self._fast_result_reader_cache[2].close()
                self._fast_result_reader_cache = None
            self._fast_result_plot_projection_cache = None

    def _interpret(self, run_reference: str) -> InterpretedRun:
        inspection = self.core.inspect_run(run_reference)
        manifest = inspection.run
        loaded = self.store.load(manifest.experiment_id)
        exported = self.core.export(manifest.run_id)
        result = loaded.adapter.interpret(
            exported.report,
            loaded.record.domain_config,
            loaded.record.projection_context,
            run_id=manifest.run_id,
            domain_experiment_id=manifest.experiment_id,
            case=None,
        )
        _, markdown_path = self.store.write_result(manifest.run_id, loaded.adapter, result)
        return InterpretedRun(
            result=result,
            manifest=manifest,
            run_reference=self.core.short_run_reference(manifest.run_id),
            domain_experiment_reference=self.store.short_reference(manifest.experiment_id),
            report_path=markdown_path,
        )

    def _render_fast_run(self, manifest: Any, adapter: DomainAdapter) -> InterpretedRun:
        if manifest.status != "completed":
            raise DomainExtensionError("La ejecución rápida no tiene resultado confirmado.")
        result = self.store.load_domain_result(manifest.domain_run_id, adapter)
        report_path = self.store.results_root / manifest.domain_run_id / "report.md"
        try:
            if report_path.is_symlink() or not report_path.is_file():
                raise ValueError
            report_path.resolve(strict=True).relative_to(self.workspace)
        except (OSError, ValueError) as exc:
            raise DomainExtensionError("El reporte rápido confirmado es inválido.") from exc
        return InterpretedRun(
            result=result,
            manifest=manifest,
            run_reference=manifest.domain_run_id[:8],
            domain_experiment_reference=self.store.short_reference(manifest.domain_experiment_id),
            report_path=report_path,
        )

    def _start_grouped_run(self, loaded: LoadedProjection) -> InterpretedRun:
        with WorkspaceWriteLock(self.workspace / ".domain-write.lock"):
            manifest = self._reserve_grouped_run(loaded)
        return self.execute_grouped_run(cast(Any, manifest).domain_run_id)

    def _activate_grouped_run(self, adapter: DomainAdapter, manifest: Any) -> Any:
        active = self._update_group_manifest(
            adapter, manifest, status="running", new_active_segment=True
        )
        self.store.write_domain_run(active)
        return active

    def _execute_fast_run(self, loaded: LoadedProjection, manifest: Any) -> InterpretedRun:
        execute = getattr(loaded.adapter, "execute_high_performance", None)
        if not callable(execute):
            raise DomainExtensionError("El adaptador no implementa el modo de alto rendimiento.")
        result, completed_manifest, report_path = execute(self, loaded, manifest)
        return InterpretedRun(
            result=result,
            manifest=completed_manifest,
            run_reference=completed_manifest.domain_run_id[:8],
            domain_experiment_reference=self.store.short_reference(
                completed_manifest.domain_experiment_id
            ),
            report_path=report_path,
        )

    def _reserve_grouped_run(self, loaded: LoadedProjection) -> BaseModel:
        adapter = loaded.adapter
        if adapter.domain_run_model is None:
            raise DomainExtensionError("El adaptador no declara su manifiesto de ejecución.")
        run_id = str(uuid4())
        timestamp = self.store.clock()
        generation = adapter.build_generation_metrics(
            loaded.record.domain_config,
            CaseGenerationStatistics(),
            duplicate_cases=0,
            core_cases=0,
        )
        manifest = adapter.domain_run_model.model_validate(
            {
                "schema_version": adapter.version,
                "domain_run_id": run_id,
                "domain_experiment_id": loaded.record.domain_experiment_id,
                "domain": loaded.record.domain_config.domain,
                "display_name": adapter.display_name(loaded.record.domain_config),
                "status": "created",
                "generator_cursor": 0,
                "generation": generation,
                **(
                    {
                        "designs": [
                            {
                                "design_id": design.id,
                                "design_title": design.title,
                                "theoretical_combinations": large_non_negative_integer(
                                    1
                                    << (
                                        len(loaded.record.domain_config.study.components)
                                        - len(design.base_component_ids)
                                    )
                                ),
                            }
                            for design in loaded.record.domain_config.study.designs
                        ]
                    }
                    if "designs" in adapter.domain_run_model.model_fields
                    else {}
                ),
                "cases": [],
                **(
                    {"mode": loaded.record.domain_config.execution.mode}
                    if "mode" in adapter.domain_run_model.model_fields
                    else {}
                ),
                **(
                    {"fast_counters": {}, "fast_artifacts": {}}
                    if "fast_counters" in adapter.domain_run_model.model_fields
                    else {}
                ),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        self.store.write_domain_run(manifest)
        return manifest

    def _execute_grouped_run(
        self,
        loaded: LoadedProjection,
        manifest: Any,
    ) -> InterpretedRun:
        adapter = loaded.adapter
        generation: Any = None
        duplicates = 0
        try:
            total = adapter.theoretical_combinations(loaded.record.domain_config)
            self._notify_grouped_progress("generation_started", total)
            generation = adapter.generate_cases(
                loaded.record.domain_config,
                loaded.record.projection_context,
                on_progress=lambda completed: self._notify_grouped_progress(
                    "generation_progress",
                    completed,
                    total,
                    getattr(generation.statistics, "valid_selections", None),
                ),
                is_cancel_requested=self.is_cancel_requested,
            )
            cursor = int(manifest.generator_cursor)
            duplicates = adapter.generation_duplicate_count(manifest)
            cases_by_id = {
                adapter.persisted_case_id(item): index for index, item in enumerate(manifest.cases)
            }
            for position, case in enumerate(generation.cases, start=1):
                self._raise_if_cancel_requested()
                if position <= cursor:
                    existing_index = cases_by_id.get(case.case_id)
                    if existing_index is None:
                        raise DomainExtensionError(
                            "El cursor agrupado no coincide con los casos persistidos."
                        )
                    existing = manifest.cases[existing_index]
                    if existing.status != "completed":
                        manifest = self._execute_persisted_case(
                            adapter,
                            loaded.record.domain_config,
                            manifest,
                            existing_index,
                            case,
                        )
                    continue
                existing_index = cases_by_id.get(case.case_id)
                if existing_index is not None:
                    existing = manifest.cases[existing_index]
                    origins = list(existing.origins)
                    if case.origin not in origins:
                        origins.append(case.origin)
                    cases = list(manifest.cases)
                    cases[existing_index] = existing.model_copy(update={"origins": origins})
                    duplicates += 1
                    manifest = self._update_group_manifest(
                        adapter,
                        manifest,
                        cases=cases,
                        generator_cursor=large_non_negative_integer(position),
                        generation=adapter.build_generation_metrics(
                            loaded.record.domain_config,
                            generation.statistics,
                            duplicate_cases=duplicates,
                            core_cases=len(cases),
                        ),
                    )
                    self.store.write_domain_run(manifest)
                    continue
                self._ensure_core_experiment(case)
                core_manifest = self.core.create_run(case.core_experiment_id)
                case_record = adapter.build_persisted_case(
                    case,
                    core_run_id=core_manifest.run_id,
                )
                cases = [*manifest.cases, case_record]
                manifest = self._update_group_manifest(
                    adapter,
                    manifest,
                    cases=cases,
                    generator_cursor=large_non_negative_integer(position),
                    generation=adapter.build_generation_metrics(
                        loaded.record.domain_config,
                        generation.statistics,
                        duplicate_cases=duplicates,
                        core_cases=len(cases),
                    ),
                )
                self.store.write_domain_run(manifest)
                manifest = self._execute_core_attempt(
                    adapter,
                    loaded.record.domain_config,
                    manifest,
                    len(manifest.cases) - 1,
                    case,
                    core_manifest,
                )
                cases_by_id[case.case_id] = len(cases) - 1
                self._raise_if_cancel_requested()
            statistics = generation.statistics
            generation_payload = adapter.build_generation_metrics(
                loaded.record.domain_config,
                statistics,
                duplicate_cases=duplicates,
                core_cases=len(manifest.cases),
            )
            terminal = (
                "completed"
                if all(item.status == "completed" for item in manifest.cases)
                else "failed"
            )
            manifest = self._update_group_manifest(
                adapter,
                manifest,
                status=terminal,
                generation=generation_payload,
            )
        except DomainRunCancelled:
            manifest = self._latest_grouped_manifest(manifest.domain_run_id)
            manifest = self._reconcile_grouped_attempts(adapter, manifest)
            generation_metrics = (
                adapter.build_generation_metrics(
                    loaded.record.domain_config,
                    generation.statistics,
                    duplicate_cases=duplicates,
                    core_cases=len(manifest.cases),
                )
                if generation is not None
                else manifest.generation
            )
            manifest = self._update_group_manifest(
                adapter, manifest, status="cancelled", generation=generation_metrics
            )
            self.store.write_domain_run(manifest)
            raise DomainRunCancelled(manifest) from None
        except (OperationalError, ValidationError, ValueError, DomainExtensionError) as exc:
            manifest = self._latest_grouped_manifest(manifest.domain_run_id)
            manifest = self._reconcile_grouped_attempts(adapter, manifest)
            generation_metrics = (
                adapter.build_generation_metrics(
                    loaded.record.domain_config,
                    generation.statistics,
                    duplicate_cases=duplicates,
                    core_cases=len(manifest.cases),
                )
                if generation is not None
                else manifest.generation
            )
            failed = self._update_group_manifest(
                adapter, manifest, status="failed", generation=generation_metrics
            )
            self.store.write_domain_run(failed)
            reference = self._group_reference(failed.domain_run_id)
            raise DomainExtensionError(
                "La ejecución agrupada quedó confirmada pero no pudo completarse: "
                f"{exc}\n"
                "Continúe la ejecución con:\n"
                f'  tesis-domain resume {reference} --workspace "{self.workspace}"',
                exit_code=self._core_exit_code(exc),
            ) from exc
        # Confirm the terminal manifest only after publishing its result.
        interpreted = self._render_grouped_run(loaded, manifest)
        self.store.write_domain_run(manifest)
        return interpreted

    def _notify_grouped_progress(self, method: str, *args: object) -> None:
        """Keep optional terminal presentation from affecting grouped execution."""

        try:
            getattr(self.progress_observer, method)(*args)
        except Exception:
            return

    def _execute_persisted_case(
        self,
        adapter: DomainAdapter,
        config: Any,
        manifest: Any,
        index: int,
        case: ProjectedCase,
    ) -> Any:
        item = manifest.cases[index]
        core_manifest = self.core.inspect_run(item.attempts[-1].core_run_id).run
        if core_manifest.status.value == "completed":
            cases = list(manifest.cases)
            cases[index] = self._replace_current_attempt_status(item, "completed")
            updated = self._update_group_manifest(adapter, manifest, cases=cases)
            self.store.write_domain_run(updated)
            return updated
        if core_manifest.status.value == "cancelled":
            core_manifest = self.core.create_run(item.core_experiment_id)
            attempts = [
                *item.attempts,
                CoreRunAttempt(core_run_id=core_manifest.run_id, status="created"),
            ]
            cases = list(manifest.cases)
            cases[index] = item.model_copy(update={"attempts": attempts})
            manifest = self._update_group_manifest(adapter, manifest, cases=cases)
            self.store.write_domain_run(manifest)
        return self._execute_core_attempt(
            adapter,
            config,
            manifest,
            index,
            case,
            core_manifest,
        )

    def _execute_core_attempt(
        self,
        adapter: DomainAdapter,
        config: Any,
        manifest: Any,
        index: int,
        case: ProjectedCase,
        core_manifest: RunManifest,
    ) -> Any:
        run_id = core_manifest.run_id
        self._set_active_core_run_id(run_id)
        self._notify_grouped_progress(
            "core_case_started",
            index + 1,
            adapter.format_case_progress(config, case),
            run_id,
            getattr(case.origin, "design_id", None),
        )
        try:
            if self.is_cancel_requested():
                with suppress(OperationalError):
                    self.core.cancel(run_id)
            elif core_manifest.status.value == "created":
                try:
                    core_manifest = self.core.run(run_id)
                except OperationalError:
                    observed = self.core.inspect_run(run_id).run
                    if not self.is_cancel_requested() or observed.status.value != "cancelled":
                        raise
                    core_manifest = observed
            elif core_manifest.status.value in {"running", "failed"}:
                try:
                    core_manifest = self.core.resume(run_id)
                except OperationalError:
                    observed = self.core.inspect_run(run_id).run
                    if not self.is_cancel_requested() or observed.status.value != "cancelled":
                        raise
                    core_manifest = observed
            core_manifest = self.core.inspect_run(run_id).run
        finally:
            self._set_active_core_run_id(None)

        cases = list(manifest.cases)
        cases[index] = self._replace_current_attempt_status(
            cases[index], core_manifest.status.value
        )
        manifest = self._update_group_manifest(adapter, manifest, cases=cases)
        self.store.write_domain_run(manifest)
        if self.is_cancel_requested() or core_manifest.status.value == "cancelled":
            raise DomainRunCancelled(manifest)
        if core_manifest.status.value == "failed":
            raise self._core_case_failure(index + 1, run_id)
        return manifest

    def _core_case_failure(self, ordinal: int, run_id: str) -> DomainExtensionError:
        inspection = self.core.inspect_run(run_id)
        failed = next(
            (
                state
                for state in inspection.pipeline.ordered_stages
                if state.status == StageStatus.FAILED
            ),
            None,
        )
        if failed is None:
            return DomainExtensionError(
                f"El caso CORE {ordinal} ({run_id}) terminó failed "
                "sin un stage fallido identificable."
            )
        stage_inspection = self.core.inspect(run_id, stage=failed.stage)
        if not isinstance(stage_inspection, StageInspection):
            return DomainExtensionError(
                f"El caso CORE {ordinal} ({run_id}) falló en {failed.stage.value} "
                "pero no se pudo cargar su resultado durable."
            )
        if stage_inspection.result.error is None:
            detail = "sin diagnóstico durable"
        else:
            detail = (
                f"{stage_inspection.result.error.code}: {stage_inspection.result.error.message}"
            )
        return DomainExtensionError(
            f"El caso CORE {ordinal} ({run_id}) falló en {failed.stage.value}: {detail}"
        )

    def _latest_grouped_manifest(self, run_id: str) -> Any:
        return self.store.load_domain_run(run_id)[0]

    def _reconcile_grouped_attempts(self, adapter: DomainAdapter, manifest: Any) -> Any:
        cases = list(manifest.cases)
        changed = False
        for index, item in enumerate(cases):
            current = item.attempts[-1]
            try:
                status = self.core.inspect_run(current.core_run_id).run.status.value
            except (OperationalError, ValidationError, ValueError):
                continue
            if status != current.status:
                cases[index] = self._replace_current_attempt_status(item, status)
                changed = True
        if not changed:
            return manifest
        updated = self._update_group_manifest(adapter, manifest, cases=cases)
        self.store.write_domain_run(updated)
        return updated

    def _raise_if_cancel_requested(self) -> None:
        if self.is_cancel_requested():
            raise DomainRunCancelled

    def _set_active_core_run_id(self, run_id: str | None) -> None:
        with self._active_core_lock:
            self._active_core_run_id = run_id

    @staticmethod
    def _replace_current_attempt_status(item: Any, status: str) -> Any:
        attempts = list(item.attempts)
        attempts[-1] = attempts[-1].model_copy(update={"status": status})
        return item.model_copy(update={"attempts": attempts})

    def _render_grouped_run(self, loaded: LoadedProjection, manifest: Any) -> InterpretedRun:
        adapter = loaded.adapter
        interpreted_cases: list[Any] = []
        for item in manifest.cases:
            core_config = self.core.load_experiment(item.core_experiment_id)
            case = ProjectedCase(
                case_id=adapter.persisted_case_id(item),
                core_experiment_id=item.core_experiment_id,
                core_config=core_config,
                origin=item.origins[0],
                payload=item.payload,
            )
            exported = self.core.export(item.core_run_id)
            interpreted = adapter.interpret(
                exported.report,
                loaded.record.domain_config,
                loaded.record.projection_context,
                run_id=item.core_run_id,
                domain_experiment_id=item.core_experiment_id,
                case=case,
            )
            interpreted_cases.append(interpreted.model_copy(update={"origins": item.origins}))
        result = adapter.build_grouped_result(
            loaded.record.domain_config,
            loaded.record.projection_context,
            manifest,
            interpreted_cases,
        )
        _, markdown_path = self.store.write_result(manifest.domain_run_id, adapter, result)
        return InterpretedRun(
            result=result,
            manifest=manifest,
            run_reference=self._group_reference(manifest.domain_run_id),
            domain_experiment_reference=self.store.short_reference(manifest.domain_experiment_id),
            report_path=markdown_path,
        )

    def _ensure_core_experiment(self, case: ProjectedCase) -> None:
        try:
            current = self.core.load_experiment(case.core_experiment_id)
        except OperationalError as exc:
            if exc.code != ErrorCode.NOT_FOUND:
                raise
            self.core.save_experiment(case.core_experiment_id, case.core_config)
            current = self.core.load_experiment(case.core_experiment_id)
        if current != case.core_config:
            raise DomainExtensionError("Un caso CORE existente no coincide con el caso proyectado.")

    def _optional_grouped_run(self, reference: str) -> tuple[Any, DomainAdapter] | None:
        compact = reference.replace("-", "").lower()
        if len(compact) not in range(8, 33) or any(
            character not in "0123456789abcdef" for character in compact
        ):
            return None
        try:
            return self.store.load_domain_run(reference)
        except DomainExtensionError as exc:
            if exc.exit_code == 66:
                return None
            raise

    def _update_group_manifest(
        self,
        adapter: DomainAdapter,
        manifest: Any,
        **changes: object,
    ) -> Any:
        if adapter.domain_run_model is None:
            raise DomainExtensionError("El adaptador no declara su manifiesto de ejecución.")
        payload = manifest.model_dump(mode="json")
        new_active_segment = changes.pop("new_active_segment", False)
        payload.update({key: self._json_value(value) for key, value in changes.items()})
        timestamp = self.store.clock()
        if "active_duration_ms" in payload:
            start = payload.get("active_started_at")
            accumulated = int(payload["active_duration_ms"])
            if start is not None and (
                new_active_segment or changes.get("status") in {"completed", "failed", "cancelled"}
            ):
                end = manifest.updated_at if new_active_segment else timestamp
                accumulated += max(
                    0,
                    int(
                        (
                            datetime.fromisoformat(end) - datetime.fromisoformat(start)
                        ).total_seconds()
                        * 1000
                    ),
                )
                payload["active_duration_ms"] = accumulated
                payload["active_started_at"] = None
            if new_active_segment:
                payload["active_started_at"] = timestamp
        payload["updated_at"] = timestamp
        return adapter.domain_run_model.model_validate_json(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )

    @classmethod
    def _json_value(cls, value: object) -> object:
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, list):
            return [cls._json_value(item) for item in value]
        if isinstance(value, tuple):
            return [cls._json_value(item) for item in value]
        if isinstance(value, dict):
            return {key: cls._json_value(item) for key, item in value.items()}
        return value

    def _group_reference(self, run_id: str) -> str:
        compact = run_id.replace("-", "")
        identifiers = [
            item[0].domain_run_id.replace("-", "") for item in self.store.list_domain_runs()
        ]
        for length in range(8, 33):
            prefix = compact[:length]
            if sum(item.startswith(prefix) for item in identifiers) == 1:
                return prefix
        return compact

    def _domain_run_manifest(
        self,
        reference: str,
        *,
        command: Literal["resume", "render"],
    ) -> RunManifest:
        try:
            manifest = self.core.inspect_run(reference).run
        except OperationalError as exc:
            if exc.code != ErrorCode.NOT_FOUND:
                raise
            self._raise_experiment_reference_mistake(reference, command, exc)
        except (ValidationError, ValueError) as exc:
            self._raise_experiment_reference_mistake(reference, command, exc)
        self.store.load(manifest.experiment_id)
        return manifest

    def _raise_experiment_reference_mistake(
        self,
        reference: str,
        command: Literal["resume", "render"],
        original: Exception,
    ) -> NoReturn:
        try:
            loaded = self.store.resolve(reference)
        except DomainExtensionError:
            raise original from None
        experiment_id = loaded.record.domain_experiment_id
        listing = self._domain_run_listing(
            self.core.list_runs(experiment_id=experiment_id),
            domain_id=None,
            experiment_id=experiment_id,
            prefix=None,
        )
        lines = [
            f"La referencia '{reference}' identifica un experimento de dominio, no un run.",
            f"El comando '{command}' requiere una referencia de run.",
        ]
        if listing.runs:
            lines.append("Runs asociados:")
            lines.extend(
                f"  {item.run_reference}  {item.status}  {item.created_at}" for item in listing.runs
            )
        else:
            lines.append("El experimento todavía no tiene runs.")
        lines.extend(
            [
                "Para consultarlos:",
                "  tesis-domain list-runs "
                f"--experiment {self.store.short_reference(experiment_id)} "
                f'--workspace "{self.workspace}"',
                "Para operar sobre un run:",
                f'  tesis-domain {command} RUN_REF --workspace "{self.workspace}"',
            ]
        )
        raise DomainExtensionError("\n".join(lines), exit_code=64) from original

    def _domain_run_listing(
        self,
        listing: RunListing,
        *,
        domain_id: str | None,
        experiment_id: str | None,
        prefix: str | None,
    ) -> DomainRunListing:
        summaries: list[DomainRunSummaryBase] = []
        warnings = [f"Advertencia del CORE: {item}" for item in listing.warnings]
        for item in listing.runs:
            core_experiment_id = item.manifest.experiment_id
            if not self.store.has_projection_entry(core_experiment_id):
                continue
            try:
                loaded = self.store.load(core_experiment_id)
            except (DomainExtensionError, OperationalError) as exc:
                warnings.append(f"Advertencia: se omitió el run {item.manifest.run_id}: {exc}")
                continue
            config = loaded.record.domain_config
            if domain_id is not None and config.domain.id != domain_id:
                continue
            summaries.append(
                cast(
                    DomainRunSummaryBase,
                    loaded.adapter.run_summary_model.model_validate(
                        {
                            "schema_version": loaded.adapter.version,
                            "run_reference": item.reference,
                            "run_id": item.manifest.run_id,
                            "domain_experiment_reference": self.store.short_reference(
                                core_experiment_id
                            ),
                            "domain_experiment_id": core_experiment_id,
                            "domain": config.domain,
                            "display_name": loaded.adapter.display_name(config),
                            "status": item.manifest.status.value,
                            "created_at": item.manifest.created_at,
                            "updated_at": item.manifest.updated_at,
                        }
                    ),
                )
            )
        normalized_prefix = prefix.replace("-", "").lower() if prefix is not None else None
        for manifest, adapter in self.store.list_domain_runs():
            if experiment_id is not None and manifest.domain_experiment_id != experiment_id:
                continue
            if domain_id is not None and manifest.domain.id != domain_id:
                continue
            compact = manifest.domain_run_id.replace("-", "")
            if normalized_prefix is not None and not compact.startswith(normalized_prefix):
                continue
            summaries.append(
                cast(
                    DomainRunSummaryBase,
                    adapter.run_summary_model.model_validate(
                        {
                            "schema_version": adapter.version,
                            "run_reference": self._group_reference(manifest.domain_run_id),
                            "run_id": manifest.domain_run_id,
                            "domain_experiment_reference": self.store.short_reference(
                                manifest.domain_experiment_id
                            ),
                            "domain_experiment_id": manifest.domain_experiment_id,
                            "domain": manifest.domain,
                            "display_name": adapter.display_name(
                                self.store.load(manifest.domain_experiment_id).record.domain_config
                            ),
                            "status": manifest.status,
                            "created_at": manifest.created_at,
                            "updated_at": manifest.updated_at,
                            **(
                                {"mode": manifest.mode, "fast_counters": manifest.fast_counters}
                                if "mode" in adapter.run_summary_model.model_fields
                                else {}
                            ),
                        }
                    ),
                )
            )
        summaries.sort(key=lambda item: item.run_id)
        summaries.sort(key=lambda item: item.created_at, reverse=True)
        return DomainRunListing(runs=tuple(summaries), warnings=tuple(warnings))

    def _summary(self, loaded: LoadedProjection) -> DomainExperimentSummaryBase:
        record = loaded.record
        return cast(
            DomainExperimentSummaryBase,
            loaded.adapter.experiment_summary_model.model_validate(
                {
                    "schema_version": loaded.adapter.version,
                    "reference": self.store.short_reference(record.domain_experiment_id),
                    "domain_experiment_id": record.domain_experiment_id,
                    "domain": record.domain_config.domain,
                    "display_name": loaded.adapter.display_name(record.domain_config),
                    "created_at": record.created_at,
                }
            ),
        )

    @staticmethod
    def _load_config(path: Path) -> tuple[DomainAdapter, BaseModel]:
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise DomainExtensionError(
                "No se pudo leer la configuración del dominio.", exit_code=66
            ) from exc
        adapter = resolve_adapter(payload)
        return adapter, adapter.parse_config(payload)

    @classmethod
    def _core_error(cls, exc: Exception) -> DomainExtensionError:
        if isinstance(exc, OperationalError):
            return DomainExtensionError(
                f"El CORE rechazó la operación ({exc.code.value}): {exc}",
                exit_code=cls._core_exit_code(exc),
            )
        if isinstance(exc, (ValidationError, ValueError)):
            return DomainExtensionError("La entrada no cumple el contrato del CORE.", exit_code=65)
        return DomainExtensionError("Ocurrió un error interno en el CORE.", exit_code=70)

    @staticmethod
    def _core_exit_code(exc: Exception) -> int:
        if not isinstance(exc, OperationalError):
            return 65 if isinstance(exc, (ValidationError, ValueError)) else 70
        if exc.code == ErrorCode.NOT_FOUND:
            return 66
        if exc.code == ErrorCode.RUN_CONTROL_UNAVAILABLE:
            return 69
        if exc.code in {ErrorCode.IO_ERROR, ErrorCode.RUN_LOCK_UNAVAILABLE}:
            return 74
        if exc.code == ErrorCode.RUN_ALREADY_ACTIVE:
            return 75
        if exc.code in {ErrorCode.CONFIG_INVALID, ErrorCode.VERSION_UNSUPPORTED}:
            return 78
        if exc.code in {
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
