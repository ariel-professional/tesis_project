from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter

from tesis_proyect.models.config import ExperimentConfig
from tesis_proyect.models.enums import STAGE_ORDER, StageId
from tesis_proyect.models.execution import (
    PipelineState,
    RunManifest,
)
from tesis_proyect.models.scientific import CountingResult
from tesis_proyect.models.stages import (
    StageResult,
)
from tesis_proyect.persistence.json_store import JsonStore
from tesis_proyect.persistence.workspace import Workspace

MANIFEST_MAX_BYTES = 1_048_576
STAGE_RESULT_MAX_BYTES = 10_485_760
ARTIFACT_MAX_BYTES = 104_857_600

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class RunLayout:
    """Canonical run-relative paths, kept in one place."""

    run_id: str

    @property
    def root(self) -> str:
        return f"runs/{self.run_id}"

    @property
    def lock(self) -> str:
        return f"{self.root}/execution.lock"

    @property
    def config(self) -> str:
        return f"{self.root}/config/run_config.json"

    @property
    def manifest(self) -> str:
        return f"{self.root}/run.json"

    @property
    def pipeline(self) -> str:
        return f"{self.root}/pipeline.json"

    @property
    def runner_log(self) -> str:
        return f"{self.root}/logs/runner.log"

    def stage(self, stage: StageId) -> str:
        ordinal = STAGE_ORDER.index(stage) + 1
        return f"{self.root}/stages/{ordinal:02d}_{stage}.json"

    def artifact(self, name: str) -> str:
        return f"{self.root}/artifacts/{name}"

    def report(self, name: str) -> str:
        return f"{self.root}/reports/{name}"


class RunRepository:
    """Typed, run-scoped access to durable workspace evidence."""

    def __init__(self, workspace: Workspace, run_id: str) -> None:
        self.workspace = workspace
        self.store = JsonStore(workspace)
        self.layout = RunLayout(run_id)

    def load_config(self) -> ExperimentConfig:
        return self.store.read_model(
            self.layout.config, ExperimentConfig, max_bytes=ARTIFACT_MAX_BYTES
        )

    def load_manifest(self) -> RunManifest:
        return self.store.read_model(
            self.layout.manifest, RunManifest, max_bytes=MANIFEST_MAX_BYTES
        )

    def load_pipeline(self) -> PipelineState:
        return self.store.read_model(
            self.layout.pipeline, PipelineState, max_bytes=MANIFEST_MAX_BYTES
        )

    def load_stage(self, stage: StageId) -> StageResult:
        return self.store.read_model(
            self.layout.stage(stage), StageResult, max_bytes=STAGE_RESULT_MAX_BYTES
        )

    def optional_stage(self, stage: StageId) -> StageResult | None:
        if not self.exists(self.layout.stage(stage)):
            return None
        return self.load_stage(stage)

    def load_artifact(self, name: str, model: type[T]) -> T:
        return self.store.read_model(
            self.layout.artifact(name), model, max_bytes=ARTIFACT_MAX_BYTES
        )

    def optional_artifact(self, name: str, model: type[T]) -> T | None:
        relative = self.layout.artifact(name)
        if not self.exists(relative):
            return None
        return self.store.read_model(relative, model, max_bytes=ARTIFACT_MAX_BYTES)

    def load_counting(self, name: str) -> CountingResult:
        value = self.store.read_json_value(
            self.layout.artifact(name), max_bytes=STAGE_RESULT_MAX_BYTES
        )
        return TypeAdapter(CountingResult).validate_python(value)

    def optional_counting(self, name: str) -> CountingResult | None:
        return self.load_counting(name) if self.exists(self.layout.artifact(name)) else None

    def write_manifest(self, manifest: RunManifest) -> None:
        self.store.write_json(self.layout.manifest, manifest)

    def write_pipeline(self, pipeline: PipelineState) -> None:
        self.store.write_json(self.layout.pipeline, pipeline)

    def exists(self, relative: str) -> bool:
        return self.workspace.resolve(relative).exists()
