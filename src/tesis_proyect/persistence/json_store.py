from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.common import ArtifactRef
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.persistence.workspace import Workspace

T = TypeVar("T", bound=BaseModel)


def stable_json_bytes(value: BaseModel | dict[str, Any] | list[Any]) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", by_alias=True)
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


class JsonStore:
    def __init__(
        self,
        workspace: Workspace,
        *,
        replace: Callable[
            [
                str | bytes | os.PathLike[str] | os.PathLike[bytes],
                str | bytes | os.PathLike[str] | os.PathLike[bytes],
            ],
            None,
        ] = os.replace,
    ) -> None:
        self.workspace = workspace
        self._replace = replace

    def write_bytes(self, relative: str, payload: bytes, *, overwrite: bool = True) -> ArtifactRef:
        target = self.workspace.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.workspace.resolve(target.parent.relative_to(self.workspace.root).as_posix())
        if not overwrite and target.exists():
            raise OperationalError(ErrorCode.ID_COLLISION, "Target already exists.")
        temporary: Path | None = None
        try:
            descriptor, raw_path = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
            )
            temporary = Path(raw_path)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if overwrite:
                self._replace(temporary, target)
            else:
                try:
                    os.link(temporary, target)
                except FileExistsError as exc:
                    raise OperationalError(
                        ErrorCode.ID_COLLISION, "Target already exists."
                    ) from exc
                temporary.unlink()
            temporary = None
            self.workspace.sync_directory(target.parent)
        except OperationalError:
            raise
        except OSError as exc:
            raise OperationalError(ErrorCode.IO_ERROR, "Atomic write failed.") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return self.artifact_ref(relative)

    def write_json(
        self,
        relative: str,
        value: BaseModel | dict[str, Any] | list[Any],
        *,
        overwrite: bool = True,
    ) -> ArtifactRef:
        return self.write_bytes(relative, stable_json_bytes(value), overwrite=overwrite)

    def read_bytes(self, relative: str, *, max_bytes: int) -> bytes:
        path = self.workspace.resolve(relative, must_exist=True)
        try:
            size = path.stat().st_size
            if size > max_bytes:
                raise OperationalError(ErrorCode.INPUT_TOO_LARGE, "Input exceeds its byte limit.")
            payload = path.read_bytes()
        except OperationalError:
            raise
        except OSError as exc:
            raise OperationalError(ErrorCode.IO_ERROR, "Input could not be read.") from exc
        if payload.startswith(b"\xef\xbb\xbf"):
            raise OperationalError(ErrorCode.INPUT_BOM_FORBIDDEN, "UTF-8 BOM is forbidden.")
        return payload

    def read_json_value(self, relative: str, *, max_bytes: int) -> Any:
        payload = self.read_bytes(relative, max_bytes=max_bytes)
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise OperationalError(
                ErrorCode.INPUT_DECODE_FAILED, "Input is not strict UTF-8."
            ) from exc
        try:
            return json.loads(
                text,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise OperationalError(
                ErrorCode.INPUT_JSON_INVALID, "Input is not strict JSON."
            ) from exc

    def read_model(self, relative: str, model: type[T], *, max_bytes: int) -> T:
        value = self.read_json_value(relative, max_bytes=max_bytes)
        try:
            return model.model_validate(value)
        except ValueError as exc:
            raise OperationalError(
                ErrorCode.SCHEMA_INVALID, "JSON document violates its schema."
            ) from exc

    def artifact_ref(self, relative: str) -> ArtifactRef:
        path = self.workspace.resolve(relative, must_exist=True)
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise OperationalError(ErrorCode.IO_ERROR, "Artifact could not be read.") from exc
        return ArtifactRef(
            path=relative,
            sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}",
            size_bytes=len(payload),
        )

    def verify(self, reference: ArtifactRef) -> bool:
        try:
            return self.artifact_ref(reference.path) == reference
        except OperationalError:
            return False
