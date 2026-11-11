"""Shared workspace selection for all bundled input/output adapters."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tesis_proyect.persistence.workspace import Workspace

_LAYOUT_DIRECTORIES = ("experiments", "runs")
_FALLBACK_NAME = "tesis_workspace"


@dataclass(frozen=True)
class WorkspaceScanWarning:
    path: Path
    error: OSError


class WorkspaceSelectionError(RuntimeError):
    pass


class MultipleWorkspacesError(WorkspaceSelectionError):
    def __init__(self, root: Path, candidates: tuple[Path, ...]) -> None:
        super().__init__("Multiple workspaces were found.")
        self.root = root
        self.candidates = candidates


def select_workspace(
    explicit: Path | None,
    *,
    warning: Callable[[WorkspaceScanWarning], None],
    current_directory: Path | None = None,
) -> Path:
    """Resolve an explicit workspace or discover one directly below cwd."""

    if explicit is not None:
        return _resolve_directory(explicit)
    root = _resolve_directory(current_directory or _current_directory())
    try:
        if _workspace_status(root):
            return root
    except OSError as exc:
        raise WorkspaceSelectionError(f"Cannot inspect directory: {root}") from exc

    entries, ordered, inaccessible = _discover(root, warning)
    if len(ordered) > 1:
        raise MultipleWorkspacesError(root, ordered)
    if ordered:
        return ordered[0]
    if not entries:
        _initialize(root)
        return root
    return _nested_workspace(root, inaccessible)


def select_and_open_workspace(
    explicit: Path | None,
    *,
    warning: Callable[[WorkspaceScanWarning], None],
    current_directory: Path | None = None,
) -> Workspace:
    """Apply the shared selection policy and open its validated CORE workspace."""

    selected = select_workspace(
        explicit,
        warning=warning,
        current_directory=current_directory,
    )
    return Workspace.open(selected)


def _discover(
    root: Path, warning: Callable[[WorkspaceScanWarning], None]
) -> tuple[list[os.DirEntry[str]], tuple[Path, ...], set[str]]:
    entries = _entries(root)
    candidates: list[Path] = []
    inaccessible: set[str] = set()
    for entry in entries:
        path = root / entry.name
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if _workspace_status(path):
                candidates.append(path.resolve(strict=True))
        except OSError as exc:
            inaccessible.add(entry.name)
            warning(WorkspaceScanWarning(path=path, error=exc))
    ordered = tuple(sorted(candidates, key=lambda item: (item.name.casefold(), item.name)))
    return entries, ordered, inaccessible


def _current_directory() -> Path:
    try:
        return Path.cwd()
    except OSError as exc:
        raise WorkspaceSelectionError("The current directory is unavailable.") from exc


def _resolve_directory(path: Path) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise WorkspaceSelectionError(f"Workspace directory is unavailable: {path}") from exc
    if not resolved.is_dir():
        raise WorkspaceSelectionError(f"Workspace is not a directory: {path}")
    return resolved


def _entries(root: Path) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(root) as scan:
            return list(scan)
    except OSError as exc:
        raise WorkspaceSelectionError(f"Cannot inspect directory: {root}") from exc


def _workspace_status(root: Path) -> bool:
    return all(_real_directory(root / name) for name in _LAYOUT_DIRECTORIES)


def _real_directory(path: Path) -> bool:
    try:
        metadata = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return False
    return stat.S_ISDIR(metadata.st_mode)


def _empty_directory(path: Path) -> bool:
    try:
        with os.scandir(path) as scan:
            return next(scan, None) is None
    except OSError as exc:
        raise WorkspaceSelectionError(f"Cannot inspect directory: {path}") from exc


def _nested_workspace(root: Path, inaccessible: set[str]) -> Path:
    index = 0
    while True:
        name = _FALLBACK_NAME if index == 0 else f"{_FALLBACK_NAME}_{index}"
        candidate = root / name
        if name in inaccessible:
            index += 1
            continue
        try:
            candidate.mkdir()
        except FileExistsError:
            try:
                if _workspace_status(candidate):
                    return candidate.resolve(strict=True)
                if _real_directory(candidate) and _empty_directory(candidate):
                    _initialize(candidate)
                    return candidate.resolve(strict=True)
            except OSError:
                pass
            index += 1
            continue
        except OSError as exc:
            raise WorkspaceSelectionError(f"Cannot create workspace: {candidate}") from exc
        _initialize(candidate)
        return candidate.resolve(strict=True)


def _initialize(root: Path) -> None:
    for name in _LAYOUT_DIRECTORIES:
        path = root / name
        try:
            path.mkdir()
        except FileExistsError:
            if _real_directory(path):
                continue
            raise WorkspaceSelectionError(f"Workspace layout collision: {path}") from None
        except OSError as exc:
            raise WorkspaceSelectionError(f"Cannot initialize workspace: {path}") from exc
