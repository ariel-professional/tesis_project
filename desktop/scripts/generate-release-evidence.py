from __future__ import annotations

import hashlib
import json
from email.parser import Parser
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

DESKTOP_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = DESKTOP_ROOT / "out" / "make"
PYTHON_SITE = DESKTOP_ROOT / "resources" / "python" / "Lib" / "site-packages"
EVIDENCE_ROOT = DESKTOP_ROOT / "release-evidence"


def _component(kind: str, name: str, version: str, license_name: str | None) -> dict[str, Any]:
    component: dict[str, Any] = {"type": kind, "name": name, "version": version}
    if license_name:
        component["licenses"] = [{"license": {"name": license_name}}]
    return component


def _node_components() -> list[dict[str, Any]]:
    lock = json.loads((DESKTOP_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    components = []
    for package_path, metadata in sorted(lock["packages"].items()):
        if not package_path or "node_modules/" not in package_path:
            continue
        name = package_path.rsplit("node_modules/", maxsplit=1)[1]
        components.append(
            _component(
                "library", name, metadata.get("version", "NOASSERTION"), metadata.get("license")
            )
        )
    return components


def _python_components() -> list[dict[str, Any]]:
    components = [_component("application", "CPython", "3.12.10", "Python-2.0")]
    for metadata_path in sorted(PYTHON_SITE.glob("*.dist-info/METADATA")):
        metadata = Parser().parsestr(metadata_path.read_text(encoding="utf-8"))
        license_name = metadata.get("License-Expression") or metadata.get("License")
        if license_name:
            license_name = license_name.strip().splitlines()[0]
            if len(license_name) > 120:
                license_name = "NOASSERTION"
        components.append(
            _component(
                "library",
                metadata.get("Name", metadata_path.parent.name),
                metadata.get("Version", "NOASSERTION"),
                license_name,
            )
        )
    return components


def _artifact_hashes() -> list[dict[str, str]]:
    if not ARTIFACT_ROOT.is_dir():
        raise FileNotFoundError("Run Electron Forge make before generating release evidence.")
    records = []
    for path in sorted(item for item in ARTIFACT_ROOT.rglob("*") if item.is_file()):
        records.append(
            {
                "path": path.relative_to(ARTIFACT_ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return records


def main() -> None:
    components = _node_components() + _python_components()
    components.sort(key=lambda item: (item["name"].casefold(), item["version"]))
    fingerprint = hashlib.sha256(
        json.dumps(components, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid5(NAMESPACE_URL, fingerprint)}",
        "version": 1,
        "metadata": {
            "component": _component("application", "tesis-proyect-desktop", "0.1.0", None)
        },
        "components": components,
    }
    hashes = _artifact_hashes()
    notices = ["# Third-party notices", ""]
    for component in components:
        licenses = component.get("licenses", [{"license": {"name": "NOASSERTION"}}])
        notice = licenses[0]["license"]["name"]
        notices.append(f"- {component['name']} {component['version']}: {notice}")

    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_ROOT / "sbom.cdx.json").write_text(
        json.dumps(sbom, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (EVIDENCE_ROOT / "SHA256SUMS.json").write_text(
        json.dumps(hashes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (EVIDENCE_ROOT / "THIRD_PARTY_NOTICES.md").write_text(
        "\n".join(notices) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
