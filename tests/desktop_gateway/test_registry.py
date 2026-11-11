from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.generate_desktop_registry import generate_registry

IDENTITY = {
    "schema_version": "1.0.0",
    "domain_id": "single-row-facility-layout",
    "domain_version": "2.0.0",
    "entry": "./src/index.ts",
}
IDENTITY_V1 = {**IDENTITY, "domain_version": "1.0.0", "entry": "./v1.ts"}
IDENTITY_V21 = {**IDENTITY, "domain_version": "2.1.0", "entry": "./src/v21.ts"}


def _manifest(
    root: Path,
    folder: str,
    document: dict[str, str] = IDENTITY,
    filename: str = "domain-ui.json",
) -> Path:
    ui = root / "src" / "tesis_domain_extensions" / "domains" / folder / "ui"
    (ui / "src").mkdir(parents=True, exist_ok=True)
    (ui / "src" / "index.ts").write_text("export {};\n", encoding="utf-8")
    if document["entry"] == "./v1.ts":
        (ui / "v1.ts").write_text("export {};\n", encoding="utf-8")
    if document["entry"] == "./src/v21.ts":
        (ui / "src" / "v21.ts").write_text("export {};\n", encoding="utf-8")
    path = ui / filename
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_registry_is_reproducible_and_uses_a_literal_lazy_import(tmp_path: Path) -> None:
    _manifest(tmp_path, "single_row_facility_layout")
    _manifest(
        tmp_path,
        "single_row_facility_layout",
        IDENTITY_V1,
        "domain-ui-v1.json",
    )
    _manifest(tmp_path, "single_row_facility_layout", IDENTITY_V21, "domain-ui-v21.json")

    first = generate_registry(tmp_path)
    second = generate_registry(tmp_path)

    assert first == second
    assert '"single-row-facility-layout@2.0.0": () =>' in first
    assert '"single-row-facility-layout@1.0.0": () =>' in first
    assert '"single-row-facility-layout@2.1.0": () =>' in first
    assert 'import("../../../src/tesis_domain_extensions/' in first


def test_registry_rejects_duplicate_domain_identity(tmp_path: Path) -> None:
    _manifest(tmp_path, "one")
    _manifest(tmp_path, "two")

    with pytest.raises(ValueError, match="duplicate domain UI"):
        generate_registry(tmp_path)


def test_registry_rejects_missing_first_party_ui(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing first-party domain UI"):
        generate_registry(tmp_path)


def test_registry_rejects_entry_outside_ui(tmp_path: Path) -> None:
    document = {**IDENTITY, "entry": "../outside.ts"}
    manifest = _manifest(tmp_path, "single_row_facility_layout", document)
    outside = manifest.parent.parent / "outside.ts"
    outside.write_text("export {};\n", encoding="utf-8")

    with pytest.raises(ValueError):
        generate_registry(tmp_path)
