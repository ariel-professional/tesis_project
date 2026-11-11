from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from tesis_proyect.domain.hashing import run_config_hash
from tesis_proyect.engines.exact import EXACT_PRODUCER
from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import ExperimentId, ProducerRef
from tesis_proyect.models.config import ExperimentConfig, GeneratorSource
from tesis_proyect.models.enums import (
    STAGE_ORDER,
    CountingConvention,
    ErrorCode,
    RunStatus,
    StageStatus,
)
from tesis_proyect.models.execution import (
    PipelineState,
    RunManifest,
    StageState,
    Versions,
)
from tesis_proyect.observation import (
    ExecutionObserver,
    NullExecutionObserver,
    RunCreated,
)
from tesis_proyect.persistence.json_store import JsonStore
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.runner.clock import utc_timestamp
from tesis_proyect.runner.locking import WorkspaceWriteLock


class ExperimentService:
    def __init__(
        self,
        workspace: Workspace,
        *,
        uuid_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], str] = utc_timestamp,
        observer: ExecutionObserver | None = None,
    ) -> None:
        self.workspace = workspace
        self.store = JsonStore(workspace)
        self.uuid_factory = uuid_factory
        self.clock = clock
        self.observer = observer or NullExecutionObserver()
        self.workspace.ensure_layout()

    def load_config_file(self, path: Path) -> ExperimentConfig:
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise OperationalError(
                ErrorCode.NOT_FOUND, "Configuration file was not found."
            ) from exc
        if payload.startswith(b"\xef\xbb\xbf"):
            raise OperationalError(ErrorCode.INPUT_BOM_FORBIDDEN, "UTF-8 BOM is forbidden.")
        try:
            return ExperimentConfig.model_validate_json(payload)
        except (UnicodeDecodeError, ValueError) as exc:
            raise OperationalError(ErrorCode.CONFIG_INVALID, "Configuration is invalid.") from exc

    def save_experiment(self, experiment_id: str, config: ExperimentConfig) -> None:
        # Run the public ID validator without introducing a wrapper document.
        TypeAdapter(ExperimentId).validate_python(experiment_id)
        self.store.write_json(
            f"experiments/{experiment_id}.json",
            config,
            overwrite=False,
        )

    def load_experiment(self, experiment_id: str) -> ExperimentConfig:
        return self.store.read_model(
            f"experiments/{experiment_id}.json",
            ExperimentConfig,
            max_bytes=104_857_600,
        )

    def create_run(self, experiment_id: str) -> RunManifest:
        with WorkspaceWriteLock(self.workspace.root / ".domain-write.lock"):
            return self._create_run_locked(experiment_id)

    def _create_run_locked(self, experiment_id: str) -> RunManifest:
        config = self.load_experiment(experiment_id)
        run_id = self._new_run_id()
        pipeline = PipelineState(
            schema_version="1.0.0",
            pipeline_version="1.0.0",
            ordered_stages=[
                StageState(
                    ordinal=ordinal,
                    stage=stage,
                    status=StageStatus.PENDING,
                    attempt_count=0,
                    result=None,
                )
                for ordinal, stage in enumerate(STAGE_ORDER, start=1)
            ],
        )
        timestamp = self.clock()
        generator = (
            ProducerRef(id="builtin", version="builtin-v1")
            if isinstance(config.source, GeneratorSource)
            else None
        )
        versions = Versions(
            app=ProducerRef(id="tesis-proyect", version="0.1.0"),
            schema=ProducerRef(id="public-json", version="1.0.0"),
            pipeline=ProducerRef(id="increment-1", version="1.0.0"),
            problem=ProducerRef(id="undirected-path-extension", version="1.0.0"),
            generator=generator,
            exact=EXACT_PRODUCER,
            reference=ProducerRef(id="bruteforce-python", version="1"),
        )
        manifest = RunManifest(
            schema_version="1.0.0",
            run_id=run_id,
            experiment_id=experiment_id,
            run_config_hash=run_config_hash(config),
            instance_hash=None,
            counting_convention=CountingConvention.UNDIRECTED_PATHS_REVERSE_IDENTIFIED,
            versions=versions,
            status=RunStatus.CREATED,
            created_at=timestamp,
            updated_at=timestamp,
            cancellation=None,
        )
        self._publish_run(config, pipeline, manifest)
        self.observer.notify(RunCreated(run_id=run_id, timestamp=self.clock()))
        return manifest

    def _publish_run(
        self,
        config: ExperimentConfig,
        pipeline: PipelineState,
        manifest: RunManifest,
    ) -> None:
        final_root = self.workspace.resolve(f"runs/{manifest.run_id}")
        temporary_relative = f"runs/.{manifest.run_id}.creating-{uuid4()}"
        temporary_root = self.workspace.resolve(temporary_relative)
        try:
            temporary_root.mkdir(parents=False, exist_ok=False)
            for relative in ("config", "stages", "artifacts", "logs", "reports"):
                (temporary_root / relative).mkdir()
            (temporary_root / "execution.lock").touch(exist_ok=False)
            self.store.write_json(
                f"{temporary_relative}/config/run_config.json", config, overwrite=False
            )
            self.store.write_json(f"{temporary_relative}/pipeline.json", pipeline, overwrite=False)
            self.store.write_json(f"{temporary_relative}/run.json", manifest, overwrite=False)
            if final_root.exists():
                raise OperationalError(ErrorCode.ID_COLLISION, "Run ID already exists.")
            temporary_root.rename(final_root)
            self.workspace.sync_directory(final_root.parent)
        except OperationalError:
            raise
        except OSError as exc:
            code = ErrorCode.ID_COLLISION if final_root.exists() else ErrorCode.IO_ERROR
            raise OperationalError(code, "Run workspace could not be created.") from exc
        finally:
            if temporary_root.exists():
                shutil.rmtree(temporary_root)

    def _new_run_id(self) -> str:
        for _ in range(100):
            candidate = str(self.uuid_factory())
            if not self.workspace.resolve(f"runs/{candidate}").exists():
                return candidate
        raise OperationalError(ErrorCode.ID_COLLISION, "Could not allocate a unique run ID.")
