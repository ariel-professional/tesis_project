from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest

from tesis_proyect.application import workspace_selection

SELECTORS = (workspace_selection,)


def layout(path) -> None:
    (path / "experiments").mkdir(parents=True)
    (path / "runs").mkdir()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_current_workspace_wins_without_scanning_children(tmp_path, module: ModuleType) -> None:
    layout(tmp_path)
    layout(tmp_path / "nested")
    selected = module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)
    assert selected == tmp_path.resolve()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_unique_immediate_workspace_is_discovered_and_files_are_ignored(
    tmp_path, module: ModuleType
) -> None:
    (tmp_path / "ar.exe").write_text("opaque", encoding="utf-8")
    (tmp_path / "f1" / "k1").mkdir(parents=True)
    (tmp_path / "f2" / "l5").mkdir(parents=True)
    layout(tmp_path / "f3")
    selected = module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)
    assert selected == (tmp_path / "f3").resolve()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_multiple_immediate_workspaces_are_sorted_and_rejected(
    tmp_path, module: ModuleType
) -> None:
    layout(tmp_path / "zeta")
    layout(tmp_path / "Alpha")
    with pytest.raises(module.MultipleWorkspacesError) as failure:
        module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)
    assert [item.name for item in failure.value.candidates] == ["Alpha", "zeta"]
    assert not (tmp_path / "tesis_workspace").exists()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_empty_current_directory_is_initialized(module: ModuleType, tmp_path) -> None:
    selected = module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)
    assert selected == tmp_path.resolve()
    assert (tmp_path / "experiments").is_dir()
    assert (tmp_path / "runs").is_dir()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_occupied_and_partial_candidates_use_first_empty_suffix(
    tmp_path, module: ModuleType
) -> None:
    (tmp_path / "document.txt").write_text("occupied", encoding="utf-8")
    (tmp_path / "tesis_workspace").write_text("collision", encoding="utf-8")
    (tmp_path / "tesis_workspace_1" / "experiments").mkdir(parents=True)
    (tmp_path / "tesis_workspace_2").mkdir()
    selected = module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)
    assert selected == (tmp_path / "tesis_workspace_2").resolve()
    assert (selected / "experiments").is_dir()
    assert (selected / "runs").is_dir()
    assert not (tmp_path / "tesis_workspace_1" / "runs").exists()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_existing_suffixed_workspace_is_reused(module: ModuleType, tmp_path) -> None:
    (tmp_path / "foreign").mkdir()
    (tmp_path / "tesis_workspace").write_text("collision", encoding="utf-8")
    layout(tmp_path / "tesis_workspace_4")
    selected = module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)
    assert selected == (tmp_path / "tesis_workspace_4").resolve()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_inaccessible_child_is_warned_and_accessible_workspace_is_used(
    tmp_path, module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    layout(tmp_path / "valid")
    original = module._workspace_status

    def status(path):
        if path == blocked:
            raise PermissionError("denied")
        return original(path)

    monkeypatch.setattr(module, "_workspace_status", status)
    warnings = []
    selected = module.select_workspace(None, warning=warnings.append, current_directory=tmp_path)
    assert selected == (tmp_path / "valid").resolve()
    assert len(warnings) == 1
    assert warnings[0].path == blocked


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_explicit_workspace_does_not_discover_or_initialize(tmp_path, module: ModuleType) -> None:
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    occupied = tmp_path / "current"
    occupied.mkdir()
    (occupied / "foreign").mkdir()
    selected = module.select_workspace(
        explicit, warning=lambda item: None, current_directory=occupied
    )
    assert selected == explicit.resolve()
    assert not (occupied / "tesis_workspace").exists()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_layout_symlink_is_not_a_workspace(module: ModuleType, tmp_path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "runs").mkdir()
    try:
        (candidate / "experiments").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable on this platform")
    selected = module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)
    assert selected == (tmp_path / "tesis_workspace").resolve()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_concurrent_creation_collision_is_reevaluated(
    module: ModuleType, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "foreign").mkdir()
    candidate = tmp_path / "tesis_workspace"
    original = Path.mkdir
    injected = False

    def racing_mkdir(path: Path, *args, **kwargs):
        nonlocal injected
        if path == candidate and not injected:
            injected = True
            original(path)
            original(path / "experiments")
            original(path / "runs")
            raise FileExistsError
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", racing_mkdir)
    selected = module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)
    assert selected == candidate.resolve()


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_unavailable_current_directory_is_reported(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable() -> Path:
        raise OSError("cwd unavailable")

    monkeypatch.setattr(Path, "cwd", unavailable)
    with pytest.raises(module.WorkspaceSelectionError, match="current directory"):
        module.select_workspace(None, warning=lambda item: None)


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_explicit_workspace_must_be_an_available_directory(module: ModuleType, tmp_path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(module.WorkspaceSelectionError, match="unavailable"):
        module.select_workspace(missing, warning=lambda item: None)

    regular_file = tmp_path / "regular.txt"
    regular_file.write_text("not a directory", encoding="utf-8")
    with pytest.raises(module.WorkspaceSelectionError, match="not a directory"):
        module.select_workspace(regular_file, warning=lambda item: None)


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_root_inspection_failure_is_reported(
    module: ModuleType, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(path: Path) -> bool:
        raise PermissionError(path)

    monkeypatch.setattr(module, "_workspace_status", denied)
    with pytest.raises(module.WorkspaceSelectionError, match="Cannot inspect"):
        module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_directory_enumeration_failure_is_reported(
    module: ModuleType, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = module.os.scandir

    def denied(path):
        if Path(path) == tmp_path:
            raise PermissionError(path)
        return original(path)

    monkeypatch.setattr(module.os, "scandir", denied)
    with pytest.raises(module.WorkspaceSelectionError, match="Cannot inspect"):
        module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_nested_creation_failure_is_reported(
    module: ModuleType, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "foreign").mkdir()
    candidate = tmp_path / "tesis_workspace"
    original = Path.mkdir

    def denied(path: Path, *args, **kwargs):
        if path == candidate:
            raise PermissionError(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", denied)
    with pytest.raises(module.WorkspaceSelectionError, match="Cannot create"):
        module.select_workspace(None, warning=lambda item: None, current_directory=tmp_path)


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_initialization_rejects_layout_collision(module: ModuleType, tmp_path) -> None:
    (tmp_path / "experiments").write_text("collision", encoding="utf-8")
    with pytest.raises(module.WorkspaceSelectionError, match="layout collision"):
        module._initialize(tmp_path)


@pytest.mark.parametrize("module", SELECTORS, ids=("shared",))
def test_initialization_io_failure_is_reported(
    module: ModuleType, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "experiments"
    original = Path.mkdir

    def denied(path: Path, *args, **kwargs):
        if path == target:
            raise PermissionError(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", denied)
    with pytest.raises(module.WorkspaceSelectionError, match="Cannot initialize"):
        module._initialize(tmp_path)


def test_workspace_selector_lives_in_the_application_boundary() -> None:
    assert "application" in Path(workspace_selection.__file__).parts
