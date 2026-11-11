"""Fail-closed inventory and recovery for an explicitly requested domain run deletion."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from tesis_domain_extensions.attachment_store import file_references, file_references_in_document
from tesis_domain_extensions.errors import DomainExtensionError
from tesis_domain_extensions.projection_store import ProjectionStore
from tesis_proyect.models.execution import RunManifest
from tesis_proyect.runner.locking import WorkspaceWriteLock, is_run_active


class ApprovedDestination(BaseModel):
    model_config = {"extra": "forbid"}
    path: str
    existed: bool
    is_directory: bool
    device: int | None = None
    inode: int | None = None
    size_bytes: int | None = None
    sha256: str | None = None


class DeletionOperation(BaseModel):
    model_config = {"extra": "forbid"}
    domain_run_id: str
    destinations: list[ApprovedDestination] = Field(min_length=1)
    deleted_domain_experiment: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    preserved_template: bool


class DomainRunDeletionService:
    def __init__(self, store: ProjectionStore, template_roots: tuple[Path, ...] = ()) -> None:
        self.store = store
        self.workspace = store.workspace
        self.operations_root = self.workspace / ".domain_deletion_operations"
        bundled_examples = Path(__file__).resolve().parents[3] / "examples" / "domains"
        self.template_roots = tuple(dict.fromkeys((bundled_examples, *template_roots)))

    def recover_pending(self) -> None:
        if not self.operations_root.exists() and not self.operations_root.is_symlink():
            return
        self._require_real_directory(self.operations_root)
        with WorkspaceWriteLock(self.workspace / ".domain-write.lock"):
            entries = sorted(self.operations_root.iterdir())
            for entry in entries:
                if (
                    entry.name.startswith(".")
                    and entry.suffix == ".tmp"
                    and entry.is_file()
                    and not entry.is_symlink()
                ):
                    continue
                if entry.suffix != ".json" or not entry.is_file():
                    raise DomainExtensionError(
                        "Hay una entrada de borrado pendiente no reconocida."
                    )
            for path in entries:
                if path.suffix != ".json":
                    continue
                operation = self._read_operation(path)
                self._apply(operation)
                path.unlink()

    def delete(self, domain_run_id: str) -> dict[str, object]:
        try:
            parsed = UUID(domain_run_id)
        except ValueError as exc:
            raise DomainExtensionError("El ID de ejecución de dominio es inválido.") from exc
        if parsed.version != 4 or str(parsed) != domain_run_id:
            raise DomainExtensionError("El ID de ejecución de dominio es inválido.")
        with WorkspaceWriteLock(self.workspace / ".domain-write.lock"):
            if self.operations_root.exists() or self.operations_root.is_symlink():
                self._require_real_directory(self.operations_root)
            pending_path = self.operations_root / f"{domain_run_id}.json"
            if pending_path.exists() or pending_path.is_symlink():
                operation = self._read_operation(pending_path)
                if operation.domain_run_id != domain_run_id:
                    raise DomainExtensionError("El registro de borrado identifica otra ejecución.")
                self._apply(operation)
                pending_path.unlink()
                return self._result(operation)
            return self._delete_locked(domain_run_id)

    def _delete_locked(  # noqa: C901 - one locked inventory preserves reference consistency
        self, domain_run_id: str
    ) -> dict[str, object]:
        manifest, _ = self.store.load_domain_run(domain_run_id)
        if manifest.status == "running":
            raise DomainExtensionError("No se puede borrar una ejecución activa.")
        run_root = self.workspace / "domain_runs" / domain_run_id
        self._validate_tree(run_root)
        projection_id = manifest.domain_experiment_id
        projection_path = self.workspace / "domain_projections" / f"{projection_id}.json"
        projection_record, _ = self.store._read_projection(projection_id)
        selected_core_runs: set[str] = set()
        selected_core_experiments: set[str] = set()
        for case in manifest.cases:
            selected_core_experiments.add(case.core_experiment_id)
            selected_core_runs.update(attempt.core_run_id for attempt in case.attempts)

        domain_manifests = self._all_domain_manifests()
        for other, _ in domain_manifests:
            if other.status == "running" or self.store.domain_run_active(other.domain_run_id):
                raise DomainExtensionError(
                    "No se puede borrar durante una operación científica activa."
                )
            if other.domain_run_id == domain_run_id:
                continue
            for case in other.cases:
                if any(attempt.core_run_id in selected_core_runs for attempt in case.attempts):
                    selected_core_runs.difference_update(
                        attempt.core_run_id for attempt in case.attempts
                    )
                if case.core_experiment_id in selected_core_experiments:
                    selected_core_experiments.discard(case.core_experiment_id)

        core_manifests = self._core_manifests()
        if selected_core_runs - {run_id for run_id, _ in core_manifests}:
            raise DomainExtensionError("No se encontraron todos los runs CORE seleccionados.")
        core_runs_root = self.workspace / "runs"
        for run_id, core_manifest in core_manifests:
            core_run_root = core_runs_root / run_id
            lock_path = core_run_root / "execution.lock"
            if lock_path.is_symlink() or not lock_path.is_file():
                raise DomainExtensionError("No se pudo verificar el lock de un run CORE.")
            if is_run_active(lock_path):
                raise DomainExtensionError("No se puede borrar durante una operación CORE activa.")
            if core_manifest.status == "running":
                raise DomainExtensionError(
                    "Un manifiesto CORE todavía indica una operación activa."
                )
            if run_id in selected_core_runs:
                continue
            selected_core_experiments.discard(core_manifest.experiment_id)

        other_projection_ids = {
            other.domain_experiment_id
            for other, _ in domain_manifests
            if other.domain_run_id != domain_run_id
        }
        projection_is_shared = projection_id in other_projection_ids
        template_path = self.workspace / "domain_templates" / f"{projection_id}.json"
        preserved_template = template_path.exists() or template_path.is_symlink()
        if preserved_template:
            if template_path.is_symlink() or not template_path.is_file():
                raise DomainExtensionError("La plantilla asociada no es segura.")
            if self._read_model(template_path) != projection_record.domain_config:
                raise DomainExtensionError("La plantilla asociada no coincide con la proyección.")

        selected_attachment_ids = {
            ref.sha256 for ref in file_references(projection_record.domain_config)
        }
        shared_attachment_ids: set[str] = set()
        for projection_file in self._json_files(self.workspace / "domain_projections"):
            if projection_file == projection_path:
                continue
            record, _ = self.store._read_projection(projection_file.stem)
            shared_attachment_ids.update(
                ref.sha256 for ref in file_references(record.domain_config)
            )
        template_files = self._json_files(self.workspace / "domain_templates")
        for root in self.template_roots:
            template_files.extend(self._tree_json_files(root))
        for template_file in template_files:
            shared_attachment_ids.update(
                ref.sha256 for ref in self._read_template_references(template_file)
            )
        if projection_is_shared:
            shared_attachment_ids.update(selected_attachment_ids)
        exclusive_attachments = selected_attachment_ids - shared_attachment_ids

        destinations = [f"runs/{run_id}" for run_id in sorted(selected_core_runs)]
        destinations.extend(
            f"experiments/{experiment_id}.json"
            for experiment_id in sorted(selected_core_experiments)
        )
        destinations.extend(
            f"domain_attachments/{digest}" for digest in sorted(exclusive_attachments)
        )
        if not projection_is_shared:
            destinations.append(f"domain_projections/{projection_id}.json")
        destinations.append(f"domain_runs/{domain_run_id}")
        approved_destinations = []
        for relative in destinations:
            destination = self._validate_destination(relative)
            self._validate_tree(destination)
            approved_destinations.append(self._approve(relative, destination))
        operation = DeletionOperation(
            domain_run_id=domain_run_id,
            destinations=approved_destinations,
            deleted_domain_experiment=None if projection_is_shared else projection_id,
            preserved_template=preserved_template,
        )
        self._persist(operation)
        self._apply(operation)
        (self.operations_root / f"{domain_run_id}.json").unlink()
        return self._result(operation)

    @staticmethod
    def _result(operation: DeletionOperation) -> dict[str, object]:
        return {
            "deleted_domain_run_id": operation.domain_run_id,
            "deleted_domain_experiment": operation.deleted_domain_experiment,
            "preserved_template": operation.preserved_template,
        }

    @staticmethod
    def _read_operation(path: Path) -> DeletionOperation:
        if path.is_symlink() or not path.is_file():
            raise DomainExtensionError("El registro de borrado pendiente no es seguro.")
        try:
            operation = DeletionOperation.model_validate_json(path.read_bytes())
        except (OSError, ValidationError) as exc:
            raise DomainExtensionError("El registro de borrado pendiente es inválido.") from exc
        if (
            path.stem != operation.domain_run_id
            or len({item.path for item in operation.destinations}) != len(operation.destinations)
            or operation.destinations[-1].path != f"domain_runs/{operation.domain_run_id}"
        ):
            raise DomainExtensionError("El inventario del borrado pendiente no es válido.")
        return operation

    def _all_domain_manifests(self) -> tuple[tuple[Any, Any], ...]:
        root = self.workspace / "domain_runs"
        if not root.exists() and not root.is_symlink():
            return ()
        self._require_real_directory(root)
        loaded: list[tuple[Any, Any]] = []
        for entry in root.iterdir():
            if entry.is_symlink() or not entry.is_dir():
                raise DomainExtensionError(
                    "No se pudo verificar una entrada de ejecución de dominio."
                )
            try:
                run_id = UUID(entry.name)
            except ValueError as exc:
                raise DomainExtensionError(
                    "Hay una carpeta de ejecución de dominio no canónica."
                ) from exc
            if run_id.version != 4 or str(run_id) != entry.name:
                raise DomainExtensionError("Hay una carpeta de ejecución de dominio no canónica.")
            loaded.append(self.store.load_domain_run(entry.name))
        return tuple(loaded)

    def _core_manifests(self) -> list[tuple[str, RunManifest]]:
        root = self.workspace / "runs"
        if not root.exists() and not root.is_symlink():
            return []
        if not root.is_dir() or root.is_symlink():
            raise DomainExtensionError("No se pudo verificar el inventario de runs CORE.")
        result: list[tuple[str, RunManifest]] = []
        for entry in root.iterdir():
            if entry.name.startswith("."):
                continue
            try:
                parsed = UUID(entry.name)
            except ValueError:
                raise DomainExtensionError(
                    "El inventario contiene una carpeta CORE no reconocida."
                ) from None
            if (
                parsed.version != 4
                or str(parsed) != entry.name
                or entry.is_symlink()
                or not entry.is_dir()
            ):
                raise DomainExtensionError("El inventario contiene una ruta CORE no canónica.")
            manifest_path = entry / "run.json"
            if manifest_path.is_symlink() or not manifest_path.is_file():
                raise DomainExtensionError("No se pudo validar un manifiesto CORE.")
            try:
                manifest = RunManifest.model_validate_json(manifest_path.read_bytes())
            except (OSError, ValidationError) as exc:
                raise DomainExtensionError("No se pudo validar un manifiesto CORE.") from exc
            if manifest.run_id != entry.name:
                raise DomainExtensionError(
                    "El nombre de un run CORE no coincide con su manifiesto."
                )
            result.append((entry.name, manifest))
        return result

    def _persist(self, operation: DeletionOperation) -> None:
        self._require_real_directory(self.operations_root, create=True)
        path = self.operations_root / f"{operation.domain_run_id}.json"
        temporary = self.operations_root / f".{operation.domain_run_id}.tmp"
        payload = (
            json.dumps(operation.model_dump(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise DomainExtensionError("No se pudo registrar el borrado confirmado.") from exc

    def _apply(self, operation: DeletionOperation) -> None:
        approved_paths: list[tuple[ApprovedDestination, Path]] = []
        for approved in operation.destinations:
            path = self._validate_destination(approved.path)
            if not path.exists() and not path.is_symlink():
                approved_paths.append((approved, path))
                continue
            self._validate_tree(path)
            self._verify_approved(approved, path)
            approved_paths.append((approved, path))
        for approved, path in approved_paths:
            if not path.exists() and not path.is_symlink():
                continue
            self._validate_tree(path)
            self._verify_approved(approved, path)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    def _validate_destination(self, relative: str) -> Path:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise DomainExtensionError("El inventario contiene una ruta no canónica.")
        parts = pure.parts
        valid = False
        if len(parts) == 2 and parts[0] in {"runs", "domain_runs"}:
            try:
                run_id = UUID(parts[1])
                valid = run_id.version == 4 and str(run_id) == parts[1]
            except ValueError:
                valid = False
        elif len(parts) == 2 and parts[0] == "experiments":
            valid = (
                re.fullmatch(r"[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?\.json", parts[1]) is not None
            )
        elif len(parts) == 2 and parts[0] in {"domain_attachments", "domain_projections"}:
            valid = re.fullmatch(r"[0-9a-f]{64}(?:\.json)?", parts[1]) is not None
        if not valid:
            raise DomainExtensionError(
                "El inventario contiene un destino fuera del alcance permitido."
            )
        path = self.workspace
        for part in pure.parts:
            path = path / part
            if path.is_symlink():
                raise DomainExtensionError("La ruta de destino contiene un enlace simbólico.")
        try:
            path.resolve(strict=False).relative_to(self.workspace)
        except ValueError as exc:
            raise DomainExtensionError("El destino sale del workspace.") from exc
        return path

    @staticmethod
    def _approve(relative: str, path: Path) -> ApprovedDestination:
        if not path.exists():
            return ApprovedDestination(path=relative, existed=False, is_directory=False)
        stat = path.stat()
        is_directory = path.is_dir()
        digest = None
        if not is_directory:
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(block)
            digest = hasher.hexdigest()
        return ApprovedDestination(
            path=relative,
            existed=True,
            is_directory=is_directory,
            device=stat.st_dev,
            inode=stat.st_ino,
            size_bytes=None if is_directory else stat.st_size,
            sha256=digest,
        )

    @staticmethod
    def _verify_approved(approved: ApprovedDestination, path: Path) -> None:
        if not approved.existed:
            raise DomainExtensionError("Un destino aprobado apareció después del inventario.")
        stat = path.stat()
        if stat.st_dev != approved.device or stat.st_ino != approved.inode:
            raise DomainExtensionError("Un destino cambió después del inventario.")
        if path.is_dir() != approved.is_directory:
            raise DomainExtensionError("El tipo de un destino cambió después del inventario.")
        if approved.is_directory:
            return
        if stat.st_size != approved.size_bytes:
            raise DomainExtensionError("Un archivo destino cambió después del inventario.")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != approved.sha256:
            raise DomainExtensionError("Un archivo destino cambió después del inventario.")

    def _validate_tree(self, path: Path) -> None:
        if path.is_symlink():
            raise DomainExtensionError("El árbol que se borraría contiene un enlace simbólico.")
        if path.exists() and path.is_dir():
            for child in path.iterdir():
                self._validate_tree(child)

    def _json_files(self, root: Path) -> list[Path]:
        if not root.exists() and not root.is_symlink():
            return []
        self._require_real_directory(root)
        result: list[Path] = []
        for path in root.iterdir():
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise DomainExtensionError("No se pudo validar un archivo de referencia.")
            result.append(path)
        return result

    def _tree_json_files(self, root: Path) -> list[Path]:
        if not root.exists() and not root.is_symlink():
            return []
        if root.is_symlink() or not root.is_dir():
            raise DomainExtensionError("El directorio de plantillas no es seguro.")
        files: list[Path] = []
        pending = [root]
        while pending:
            directory = pending.pop()
            for entry in directory.iterdir():
                if entry.is_symlink():
                    raise DomainExtensionError("Las plantillas contienen un enlace simbólico.")
                if entry.is_dir():
                    pending.append(entry)
                elif entry.is_file() and entry.suffix == ".json":
                    files.append(entry)
        return files

    @staticmethod
    def _read_model(path: Path) -> BaseModel:
        try:
            document: Any = json.loads(path.read_bytes())
            config = document if isinstance(document, dict) else None
            if config is None:
                raise ValueError
            from tesis_domain_extensions.catalog import resolve_adapter

            adapter = resolve_adapter(json.dumps({"domain": config["domain"]}).encode())
            return adapter.parse_config(json.dumps(config).encode())
        except (OSError, ValueError, KeyError, ValidationError) as exc:
            raise DomainExtensionError("No se pudo validar una plantilla compartida.") from exc

    @staticmethod
    def _read_template_references(path: Path) -> list[Any]:
        try:
            document = json.loads(path.read_bytes())
            return file_references_in_document(document)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            raise DomainExtensionError(
                "No se pudieron validar las referencias de adjuntos de una plantilla."
            ) from exc

    @staticmethod
    def _require_real_directory(path: Path, *, create: bool = False) -> None:
        if create:
            path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise DomainExtensionError("El directorio de operaciones de borrado no es seguro.")
