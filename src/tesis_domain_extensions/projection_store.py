from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from tesis_domain_extensions.adapters import DomainAdapter, DomainProjection
from tesis_domain_extensions.catalog import resolve_adapter
from tesis_domain_extensions.contracts.projection import (
    DomainExperimentSummaryBase,
    domain_experiment_id,
)
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.runner.locking import RunExecutionLock, WorkspaceWriteLock, is_run_active

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PREFIX = re.compile(r"^[0-9a-fA-F]{1,64}$")
_MIB = 1024 * 1024
_MAX_STANDARD_DOCUMENT_BYTES = 500 * _MIB
_MAX_FAST_RESULT_SUMMARY_BYTES = 100 * _MIB


class CoreExperimentCommands(Protocol):
    def load_experiment(self, experiment_id: str) -> ExperimentConfig: ...

    def save_experiment(
        self,
        experiment_id: str,
        config: ExperimentConfig,
    ) -> None: ...


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def pretty_json(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def normalize_projection_prefix(value: str, *, minimum_length: int) -> str:
    if _PREFIX.fullmatch(value) is None or len(value) < minimum_length:
        raise DomainExtensionError(
            f"La referencia debe contener entre {minimum_length} y 64 dígitos hexadecimales.",
            exit_code=64,
        )
    return value.lower()


@dataclass(frozen=True)
class LoadedProjection:
    record: Any
    adapter: DomainAdapter
    projected: DomainProjection


@dataclass(frozen=True)
class ProjectionListing:
    experiments: tuple[DomainExperimentSummaryBase, ...]
    warnings: tuple[str, ...]


class ProjectionStore:
    def __init__(
        self,
        workspace: Path,
        core: CoreExperimentCommands,
        *,
        clock: Callable[[], str] = utc_timestamp,
    ) -> None:
        self.workspace = workspace.resolve(strict=True)
        if not self.workspace.is_dir() or self.workspace.is_symlink():
            raise DomainExtensionError("El workspace debe ser un directorio real.", exit_code=64)
        self.clock = clock
        self.core = core

    @property
    def projections_root(self) -> Path:
        return self.workspace / "domain_projections"

    @property
    def results_root(self) -> Path:
        return self.workspace / "domain_runs"

    def has_projection_entry(self, experiment_id: str) -> bool:
        path = self.projections_root / f"{experiment_id}.json"
        return path.exists() or path.is_symlink()

    def prepare(
        self,
        adapter: DomainAdapter,
        config: Any,
    ) -> LoadedProjection:
        with WorkspaceWriteLock(self.workspace / ".domain-write.lock"):
            return self._prepare_locked(adapter, config)

    def _prepare_locked(
        self,
        adapter: DomainAdapter,
        config: Any,
    ) -> LoadedProjection:
        projected = adapter.project(config)
        instance_nonce = os.urandom(16).hex()
        experiment_id = domain_experiment_id(config, instance_nonce)
        record = adapter.build_projection_record(
            domain_experiment_id=experiment_id,
            created_at=self.clock(),
            config=config,
            context=projected.context,
            instance_nonce=instance_nonce,
        )

        if projected.core_config is not None:
            current = self._load_core_experiment_optional(experiment_id)
            if current is None:
                try:
                    self.core.save_experiment(experiment_id, projected.core_config)
                except OperationalError as exc:
                    if exc.code != ErrorCode.ID_COLLISION:
                        raise
                current = self._load_required_core_experiment(experiment_id)
            self._verify_core_experiment(current, projected.core_config)

        if not self._write_projection_once(record):
            raise DomainExtensionError("Colisionó la identidad aleatoria del experimento.")
        return LoadedProjection(record=record, adapter=adapter, projected=projected)

    def resolve(self, reference: str) -> LoadedProjection:
        prefix = normalize_projection_prefix(reference, minimum_length=8)
        matches = self._matching_ids(prefix)
        if not matches:
            raise DomainExtensionError("No se encontró el experimento de dominio.", exit_code=66)
        if len(matches) > 1:
            raise DomainExtensionError(
                f"La referencia '{reference}' es ambigua; agregue más dígitos.", exit_code=64
            )
        return self.load(matches[0])

    def load(self, experiment_id: str) -> LoadedProjection:
        if _DIGEST.fullmatch(experiment_id) is None:
            raise DomainExtensionError("El ID del experimento de dominio es inválido.")
        record, adapter = self._read_projection(experiment_id)
        projected = adapter.project(record.domain_config)
        self._verify_projection(record, adapter, projected)
        if projected.core_config is not None:
            self._verify_core_experiment(
                self._load_required_core_experiment(experiment_id),
                projected.core_config,
            )
        return LoadedProjection(record=record, adapter=adapter, projected=projected)

    def short_reference(self, experiment_id: str) -> str:
        ids = self._projection_ids()
        if experiment_id not in ids:
            ids.append(experiment_id)
        return self._short_references(ids)[experiment_id]

    def list_experiments(
        self,
        *,
        domain_id: str | None,
        prefix: str | None,
    ) -> ProjectionListing:
        normalized = (
            normalize_projection_prefix(prefix, minimum_length=1) if prefix is not None else None
        )
        ids, warnings = self._listing_ids()
        references = self._short_references(ids)
        summaries: list[DomainExperimentSummaryBase] = []
        for experiment_id in ids:
            if normalized is not None and not experiment_id.startswith(normalized):
                continue
            try:
                loaded = self.load(experiment_id)
            except DomainExtensionError as exc:
                warnings.append(
                    f"Advertencia: se omitió domain_projections/{experiment_id}.json: {exc}"
                )
                continue
            config = loaded.record.domain_config
            if domain_id is not None and config.domain.id != domain_id:
                continue
            summaries.append(
                cast(
                    DomainExperimentSummaryBase,
                    loaded.adapter.experiment_summary_model.model_validate(
                        {
                            "schema_version": loaded.adapter.version,
                            "reference": references[experiment_id],
                            "domain_experiment_id": experiment_id,
                            "domain": config.domain,
                            "display_name": loaded.adapter.display_name(config),
                            "created_at": loaded.record.created_at,
                        }
                    ),
                )
            )
        summaries.sort(key=lambda item: item.domain_experiment_id)
        summaries.sort(key=lambda item: item.created_at, reverse=True)
        return ProjectionListing(experiments=tuple(summaries), warnings=tuple(warnings))

    def write_result(
        self,
        run_id: str,
        adapter: DomainAdapter,
        result: Any,
    ) -> tuple[Path, Path]:
        try:
            parsed = UUID(run_id)
        except ValueError as exc:
            raise DomainExtensionError("El CORE devolvió un run ID inválido.") from exc
        if parsed.version != 4 or str(parsed) != run_id:
            raise DomainExtensionError("El CORE devolvió un run ID inválido.")
        root = self._ensure_real_directory(self.results_root) / run_id
        try:
            root.mkdir(exist_ok=True)
        except OSError as exc:
            raise DomainExtensionError(
                "No se pudo crear el directorio del resultado de dominio.", exit_code=74
            ) from exc
        if root.is_symlink() or not root.is_dir():
            raise DomainExtensionError("El directorio del resultado de dominio es inválido.")
        json_path = root / "result.json"
        markdown_path = root / "report.md"
        self._atomic_replace(json_path, adapter.render_json(result))
        self._atomic_replace(markdown_path, adapter.render_markdown(result).encode("utf-8"))
        return json_path, markdown_path

    @contextmanager
    def domain_execution(self, reference: str) -> Iterator[tuple[Any, DomainAdapter]]:
        with WorkspaceWriteLock(self.workspace / ".domain-write.lock"):
            manifest, adapter = self.load_domain_run(reference)
            pending = (
                self.workspace / ".domain_deletion_operations" / f"{manifest.domain_run_id}.json"
            )
            if pending.exists() or pending.is_symlink():
                raise DomainExtensionError("La ejecución tiene un borrado pendiente.")
            lock = RunExecutionLock(self.results_root / manifest.domain_run_id / "execution.lock")
            lock.acquire()
        try:
            yield manifest, adapter
        finally:
            lock.release()

    def domain_run_active(self, run_id: str) -> bool:
        manifest, _adapter = self.load_domain_run(run_id)
        path = self.results_root / manifest.domain_run_id / "execution.lock"
        if path.is_symlink():
            raise DomainExtensionError("El bloqueo de dominio no puede ser un enlace simbólico.")
        return path.exists() and is_run_active(path)

    def write_domain_run(self, manifest: BaseModel) -> Path:
        with WorkspaceWriteLock(self.workspace / ".domain-write.lock"):
            return self._write_domain_run_locked(manifest)

    def _write_domain_run_locked(self, manifest: BaseModel) -> Path:
        run_id = getattr(manifest, "domain_run_id", None)
        self._validate_domain_run_id(run_id)
        run_id = cast(str, run_id)
        root = self._ensure_real_directory(self.results_root) / run_id
        try:
            root.mkdir(exist_ok=True)
        except OSError as exc:
            raise DomainExtensionError(
                "No se pudo crear la ejecución de dominio.", exit_code=74
            ) from exc
        if root.is_symlink() or not root.is_dir():
            raise DomainExtensionError("El directorio de la ejecución de dominio es inválido.")
        path = root / "domain_run.json"
        self._atomic_replace(path, pretty_json(manifest))
        return path

    def load_domain_run(self, reference: str) -> tuple[Any, DomainAdapter]:
        compact = reference.replace("-", "").lower()
        if re.fullmatch(r"[0-9a-f]{8,32}", compact) is None:
            raise DomainExtensionError("La referencia de ejecución de dominio es inválida.")
        matches = [
            item for item in self._domain_run_ids() if item.replace("-", "").startswith(compact)
        ]
        if not matches:
            raise DomainExtensionError("No se encontró la ejecución de dominio.", exit_code=66)
        if len(matches) > 1:
            raise DomainExtensionError("La referencia de ejecución de dominio es ambigua.")
        path = self.results_root / matches[0] / "domain_run.json"
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError
            resolved = path.resolve(strict=True)
            resolved.relative_to(self.workspace)
            if resolved.stat().st_size > _MAX_STANDARD_DOCUMENT_BYTES:
                raise ValueError
            payload = resolved.read_bytes()
            if len(payload) > _MAX_STANDARD_DOCUMENT_BYTES:
                raise ValueError
            document = json.loads(payload)
            domain = document["domain"]
            adapter = resolve_adapter(
                json.dumps({"domain": domain}, separators=(",", ":")).encode("utf-8")
            )
            if adapter.domain_run_model is None:
                raise ValueError
            manifest = self._parse_domain_run(payload, adapter)
            if getattr(manifest, "domain_run_id", None) != matches[0]:
                raise ValueError
        except (
            OSError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            raise DomainExtensionError("La ejecución de dominio es inválida.") from exc
        return manifest, adapter

    @staticmethod
    def _parse_domain_run(payload: bytes, adapter: DomainAdapter) -> BaseModel:
        model = adapter.domain_run_model
        if model is None:
            raise ValueError("domain adapter has no run manifest model")
        try:
            return model.model_validate_json(payload)
        except ValidationError:
            legacy_model = getattr(adapter, "legacy_domain_run_model", None)
            if not isinstance(legacy_model, type) or not issubclass(legacy_model, BaseModel):
                raise
            return legacy_model.model_validate_json(payload)

    def load_domain_result(self, run_id: str, adapter: DomainAdapter) -> BaseModel:
        """Load a confirmed domain result without recomputing scientific evidence."""

        result, _ = self.load_domain_result_document(run_id, adapter)
        return result

    def load_domain_result_document(
        self, run_id: str, adapter: DomainAdapter
    ) -> tuple[BaseModel, bytes]:
        """Load and validate the result together with its immutable JSON document."""

        self._validate_domain_run_id(run_id)
        try:
            manifest, manifest_adapter = self.load_domain_run(run_id)
            if manifest_adapter is not adapter or manifest.status != "completed":
                raise ValueError
            result_model = adapter.result_model
            if getattr(manifest, "mode", "standard") == "high_performance":
                fast_model = getattr(adapter, "fast_result_model", None)
                if not isinstance(fast_model, type) or not issubclass(fast_model, BaseModel):
                    raise ValueError
                result_model = fast_model
        except (DomainExtensionError, ValueError) as exc:
            raise DomainExtensionError("La ejecución confirmada del dominio es inválida.") from exc
        path = self.results_root / run_id / "result.json"
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError
            resolved = path.resolve(strict=True)
            resolved.relative_to(self.workspace)
            maximum_bytes = (
                _MAX_FAST_RESULT_SUMMARY_BYTES
                if getattr(manifest, "mode", "standard") == "high_performance"
                else _MAX_STANDARD_DOCUMENT_BYTES
            )
            if resolved.stat().st_size > maximum_bytes:
                raise ValueError
            payload = resolved.read_bytes()
            if len(payload) > maximum_bytes:
                raise ValueError
            return result_model.model_validate_json(payload), payload
        except (
            OSError,
            UnicodeDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            raise DomainExtensionError("El resultado confirmado del dominio es inválido.") from exc

    def list_domain_runs(self) -> tuple[tuple[Any, DomainAdapter], ...]:
        loaded: list[tuple[Any, DomainAdapter]] = []
        for run_id in self._domain_run_ids():
            try:
                loaded.append(self.load_domain_run(run_id))
            except DomainExtensionError:
                continue
        loaded.sort(key=lambda item: item[0].domain_run_id)
        loaded.sort(key=lambda item: item[0].created_at, reverse=True)
        return tuple(loaded)

    def _verify_projection(
        self,
        record: Any,
        adapter: DomainAdapter,
        projected: DomainProjection,
    ) -> None:
        if (record.domain_config.domain.id, record.domain_config.domain.version) != (
            adapter.domain_id,
            adapter.version,
        ):
            raise DomainExtensionError("La proyección identifica otro adaptador de dominio.")
        if record.projection_context != projected.context:
            raise DomainExtensionError("El contexto reversible no coincide con la proyección.")

    def _load_core_experiment_optional(self, experiment_id: str) -> ExperimentConfig | None:
        try:
            return self.core.load_experiment(experiment_id)
        except OperationalError as exc:
            if exc.code == ErrorCode.NOT_FOUND:
                return None
            raise DomainExtensionError("El experimento del CORE es inválido.") from exc

    def _load_required_core_experiment(self, experiment_id: str) -> ExperimentConfig:
        try:
            return self.core.load_experiment(experiment_id)
        except OperationalError as exc:
            if exc.code == ErrorCode.NOT_FOUND:
                raise DomainExtensionError(
                    "No se encontró el experimento correspondiente en el CORE.",
                    exit_code=66,
                ) from exc
            raise DomainExtensionError("El experimento del CORE es inválido.") from exc

    @staticmethod
    def _verify_core_experiment(
        current: ExperimentConfig,
        expected: ExperimentConfig,
    ) -> None:
        if current != expected:
            raise DomainExtensionError("El experimento del CORE no coincide con la proyección.")

    def _projection_ids(self) -> list[str]:
        root = self.projections_root
        if not root.exists():
            return []
        if root.is_symlink() or not root.is_dir():
            raise DomainExtensionError("domain_projections debe ser un directorio real.")
        try:
            entries = sorted(root.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise DomainExtensionError("No se pudieron enumerar las proyecciones.") from exc
        return [
            entry.stem
            for entry in entries
            if entry.suffix == ".json"
            and _DIGEST.fullmatch(entry.stem) is not None
            and entry.is_file()
            and not entry.is_symlink()
        ]

    def _domain_run_ids(self) -> list[str]:
        root = self.results_root
        if not root.exists():
            return []
        if root.is_symlink() or not root.is_dir():
            raise DomainExtensionError("domain_runs debe ser un directorio real.")
        identifiers: list[str] = []
        try:
            entries = sorted(root.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise DomainExtensionError(
                "No se pudieron enumerar las ejecuciones de dominio."
            ) from exc
        for entry in entries:
            try:
                parsed = UUID(entry.name)
            except ValueError:
                continue
            if (
                parsed.version == 4
                and str(parsed) == entry.name
                and entry.is_dir()
                and not entry.is_symlink()
                and (entry / "domain_run.json").is_file()
            ):
                identifiers.append(entry.name)
        return identifiers

    @staticmethod
    def _validate_domain_run_id(value: object) -> None:
        if not isinstance(value, str):
            raise DomainExtensionError("El ID de ejecución de dominio es inválido.")
        try:
            parsed = UUID(value)
        except ValueError as exc:
            raise DomainExtensionError("El ID de ejecución de dominio es inválido.") from exc
        if parsed.version != 4 or str(parsed) != value:
            raise DomainExtensionError("El ID de ejecución de dominio es inválido.")

    def _listing_ids(self) -> tuple[list[str], list[str]]:
        root = self.projections_root
        if not root.exists():
            return [], []
        if root.is_symlink() or not root.is_dir():
            raise DomainExtensionError("domain_projections debe ser un directorio real.")
        try:
            entries = sorted(root.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            raise DomainExtensionError("No se pudieron enumerar las proyecciones.") from exc
        ids: list[str] = []
        warnings: list[str] = []
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if (
                entry.suffix != ".json"
                or _DIGEST.fullmatch(entry.stem) is None
                or entry.is_symlink()
                or not entry.is_file()
            ):
                warnings.append(
                    f"Advertencia: se omitió domain_projections/{entry.name}: "
                    "la entrada no es una proyección canónica."
                )
                continue
            ids.append(entry.stem)
        return ids, warnings

    def _matching_ids(self, prefix: str) -> list[str]:
        return [item for item in self._projection_ids() if item.startswith(prefix)]

    @staticmethod
    def _short_references(ids: list[str]) -> dict[str, str]:
        counts = Counter(value[:length] for value in ids for length in range(8, 65))
        references: dict[str, str] = {}
        for value in ids:
            references[value] = next(
                prefix
                for prefix in (value[:length] for length in range(8, 65))
                if counts[prefix] == 1
            )
        return references

    def _read_optional(self, experiment_id: str) -> Any | None:
        path = self.projections_root / f"{experiment_id}.json"
        if not path.exists():
            return None
        return self._read_projection(experiment_id)[0]

    def _read_projection(self, experiment_id: str) -> tuple[Any, DomainAdapter]:
        path = self.projections_root / f"{experiment_id}.json"
        if path.is_symlink() or not path.is_file():
            raise DomainExtensionError(
                "No se encontró una proyección de dominio válida.", exit_code=66
            )
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(self.workspace)
            if resolved.stat().st_size > _MAX_STANDARD_DOCUMENT_BYTES:
                raise ValueError
            payload = resolved.read_bytes()
            if len(payload) > _MAX_STANDARD_DOCUMENT_BYTES:
                raise ValueError
            document = json.loads(payload)
            if not isinstance(document, dict) or "domain_config" not in document:
                raise ValueError
            config_payload = json.dumps(
                document["domain_config"], ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            adapter = resolve_adapter(config_payload)
            record = adapter.parse_projection_record(payload)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            raise DomainExtensionError("La proyección de dominio es inválida.") from exc
        if cast(Any, record).domain_experiment_id != experiment_id:
            raise DomainExtensionError("El nombre de la proyección no coincide con su ID.")
        return record, adapter

    def _write_projection_once(self, record: Any) -> bool:
        root = self._ensure_real_directory(self.projections_root)
        path = root / f"{record.domain_experiment_id}.json"
        temporary = root / f".{path.name}.tmp-{uuid4()}"
        try:
            with temporary.open("xb") as handle:
                handle.write(pretty_json(record))
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                return False
            return True
        except OSError as exc:
            raise DomainExtensionError("No se pudo persistir la proyección.", exit_code=74) from exc
        finally:
            temporary.unlink(missing_ok=True)

    def _ensure_real_directory(self, path: Path) -> Path:
        if path.exists() and (path.is_symlink() or not path.is_dir()):
            raise DomainExtensionError(f"{path.name} debe ser un directorio real.")
        try:
            path.mkdir(exist_ok=True)
        except OSError as exc:
            raise DomainExtensionError(f"No se pudo crear {path.name}.", exit_code=74) from exc
        return path

    @staticmethod
    def _atomic_replace(path: Path, payload: bytes) -> None:
        if path.exists() and path.is_symlink():
            raise DomainExtensionError(f"{path.name} no puede ser un symlink.")
        temporary = path.with_name(f".{path.name}.tmp-{uuid4()}")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            raise DomainExtensionError(f"No se pudo escribir {path.name}.", exit_code=74) from exc
        finally:
            temporary.unlink(missing_ok=True)
