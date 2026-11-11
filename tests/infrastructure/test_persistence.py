import os
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, StrictInt

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.persistence.json_store import JsonStore, stable_json_bytes
from tesis_proyect.persistence.workspace import Workspace
from tesis_proyect.schema_generation import generated, write_schemas

pytestmark = pytest.mark.integration


@pytest.fixture
def store(tmp_path: Path) -> JsonStore:
    workspace = Workspace.open(tmp_path)
    workspace.ensure_layout()
    return JsonStore(workspace)


def test_stable_presentation_json() -> None:
    assert stable_json_bytes({"z": None, "a": "á"}) == '{\n  "a": "á",\n  "z": null\n}\n'.encode()


def test_atomic_write_and_integrity(store: JsonStore) -> None:
    reference = store.write_json("experiments/example.json", {"b": 2, "a": 1}, overwrite=False)
    assert reference.path == "experiments/example.json"
    assert reference.sha256.startswith("sha256:")
    assert store.verify(reference)
    with pytest.raises(OperationalError) as collision:
        store.write_json("experiments/example.json", {"a": 9}, overwrite=False)
    assert collision.value.code == ErrorCode.ID_COLLISION
    assert store.read_json_value(reference.path, max_bytes=1024) == {"a": 1, "b": 2}


def test_failed_replace_preserves_confirmed_file_and_removes_temp(tmp_path: Path) -> None:
    workspace = Workspace.open(tmp_path)
    workspace.ensure_layout()
    normal = JsonStore(workspace)
    normal.write_json("experiments/example.json", {"version": 1})

    def fail_replace(source: object, target: object) -> None:
        raise OSError("injected")

    failing = JsonStore(workspace, replace=fail_replace)  # type: ignore[arg-type]
    with pytest.raises(OperationalError) as failure:
        failing.write_json("experiments/example.json", {"version": 2})
    assert failure.value.code == ErrorCode.IO_ERROR
    assert normal.read_json_value("experiments/example.json", max_bytes=1024) == {"version": 1}
    assert not list((tmp_path / "experiments").glob("*.tmp"))


@pytest.mark.parametrize("relative", ["../escape", "/absolute", "a/../b", "a\\b"])
def test_rejects_unconfined_path(store: JsonStore, relative: str) -> None:
    with pytest.raises(OperationalError) as failure:
        store.workspace.resolve(relative)
    assert failure.value.code == ErrorCode.PATH_OUTSIDE_WORKSPACE


def test_rejects_symlink_escape_when_supported(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available to this Windows account")
    workspace = Workspace.open(tmp_path)
    with pytest.raises(OperationalError) as failure:
        workspace.resolve("link/file.json")
    assert failure.value.code == ErrorCode.PATH_OUTSIDE_WORKSPACE


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xef\xbb\xbf[]", ErrorCode.INPUT_BOM_FORBIDDEN),
        (b"\xff", ErrorCode.INPUT_DECODE_FAILED),
        (b"[NaN]", ErrorCode.INPUT_JSON_INVALID),
        (b"{", ErrorCode.INPUT_JSON_INVALID),
    ],
)
def test_strict_input_failures(store: JsonStore, payload: bytes, code: ErrorCode) -> None:
    path = store.workspace.resolve("input.json")
    path.write_bytes(payload)
    with pytest.raises(OperationalError) as failure:
        store.read_json_value("input.json", max_bytes=1024)
    assert failure.value.code == code


def test_size_is_checked_before_parse(store: JsonStore) -> None:
    path = store.workspace.resolve("large.json")
    path.write_bytes(b"[" + b" " * 1024 + b"]")
    with pytest.raises(OperationalError) as failure:
        store.read_json_value("large.json", max_bytes=10)
    assert failure.value.code == ErrorCode.INPUT_TOO_LARGE


def test_relative_round_trip_and_directory_sync(store: JsonStore) -> None:
    path = store.workspace.resolve("experiments")
    assert store.workspace.relative(path) == "experiments"
    store.workspace.sync_directory(path)
    assert os.path.isdir(path)


def test_workspace_open_relative_and_missing_artifact_failures(tmp_path: Path) -> None:
    with pytest.raises(OperationalError) as missing:
        Workspace.open(tmp_path / "missing")
    assert missing.value.code == ErrorCode.NOT_FOUND
    file_path = tmp_path / "file"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(OperationalError) as not_directory:
        Workspace.open(file_path)
    assert not_directory.value.code == ErrorCode.CONFIG_INVALID
    workspace = Workspace.open(tmp_path)
    outside = tmp_path.parent
    with pytest.raises(OperationalError):
        workspace.relative(outside)
    assert workspace.run_dir("example") == tmp_path / "runs" / "example"


def test_schema_invalid_missing_verification_and_hardlink_race(
    store: JsonStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TinyModel(BaseModel):
        model_config = ConfigDict(strict=True)
        value: StrictInt

    store.write_json("experiments/invalid-model.json", {"value": "1"})
    with pytest.raises(OperationalError) as invalid:
        store.read_model("experiments/invalid-model.json", TinyModel, max_bytes=1024)
    assert invalid.value.code == ErrorCode.SCHEMA_INVALID
    reference = store.write_json("experiments/reference.json", {"value": 1})
    (store.workspace.root / reference.path).unlink()
    assert not store.verify(reference)

    def collide(source: object, target: object) -> None:
        raise FileExistsError

    monkeypatch.setattr(os, "link", collide)
    with pytest.raises(OperationalError) as collision:
        store.write_json("experiments/race.json", {"value": 1}, overwrite=False)
    assert collision.value.code == ErrorCode.ID_COLLISION


def test_schema_writer_removes_stale_files_and_writes_exact_catalog(tmp_path: Path) -> None:
    root = tmp_path / "schemas"
    root.mkdir()
    stale = root / "stale.schema.json"
    stale.write_text("stale", encoding="utf-8")
    write_schemas(root)
    assert not stale.exists()
    assert {path.name: path.read_text(encoding="utf-8") for path in root.iterdir()} == generated()
