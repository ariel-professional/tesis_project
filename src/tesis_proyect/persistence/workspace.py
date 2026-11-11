from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode


@dataclass(frozen=True)
class Workspace:
    root: Path

    @classmethod
    def open(cls, root: Path) -> Workspace:
        try:
            resolved = root.resolve(strict=True)
        except OSError as exc:
            raise OperationalError(ErrorCode.NOT_FOUND, "Workspace does not exist.") from exc
        if not resolved.is_dir():
            raise OperationalError(ErrorCode.CONFIG_INVALID, "Workspace is not a directory.")
        return cls(resolved)

    def resolve(self, relative: str, *, must_exist: bool = False) -> Path:
        pure = PurePosixPath(relative)
        if (
            not relative
            or "\\" in relative
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise OperationalError(
                ErrorCode.PATH_OUTSIDE_WORKSPACE, "Path is not a confined POSIX relative path."
            )
        candidate = self.root.joinpath(*pure.parts)
        try:
            resolved = candidate.resolve(strict=must_exist)
            resolved.relative_to(self.root)
        except (OSError, ValueError) as exc:
            code = (
                ErrorCode.NOT_FOUND
                if must_exist and not candidate.exists()
                else ErrorCode.PATH_OUTSIDE_WORKSPACE
            )
            raise OperationalError(code, "Path does not resolve inside the workspace.") from exc
        return resolved

    def relative(self, path: Path) -> str:
        try:
            return path.resolve(strict=True).relative_to(self.root).as_posix()
        except (OSError, ValueError) as exc:
            raise OperationalError(
                ErrorCode.PATH_OUTSIDE_WORKSPACE, "Path is outside the workspace."
            ) from exc

    def ensure_layout(self) -> None:
        for relative in ("experiments", "runs"):
            path = self.resolve(relative)
            path.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                raise OperationalError(
                    ErrorCode.PATH_OUTSIDE_WORKSPACE, "Layout path is a symlink."
                )

    def run_dir(self, run_id: str) -> Path:
        return self.resolve(f"runs/{run_id}")

    def sync_directory(self, directory: Path) -> None:
        if os.name == "nt":
            return
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
