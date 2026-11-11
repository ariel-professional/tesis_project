from __future__ import annotations

import ast
import json
from pathlib import Path

PACKAGE_ROOT = Path("src/tesis_domain_extensions")


def test_companion_package_imports_only_the_core_application_boundary() -> None:
    allowed = (
        "tesis_proyect.application",
        "tesis_proyect.errors",
        "tesis_proyect.models",
        "tesis_proyect.observation",
    )
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports = [node.module]
            else:
                continue
            for name in imports:
                if (
                    name == "tesis_proyect.runner.locking"
                    and path.name
                    in {
                        "application.py",
                        "deletion.py",
                        "projection_store.py",
                    }
                    and path.parent == PACKAGE_ROOT
                ):
                    continue
                if (
                    name == "tesis_proyect" or name.startswith("tesis_proyect.")
                ) and not name.startswith(allowed):
                    violations.append(f"{path}: {name}")
    assert not violations, "Forbidden CORE imports:\n" + "\n".join(violations)


def test_domain_adapter_does_not_spawn_or_import_either_cli() -> None:
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        if "subprocess" in source:
            violations.append(f"{path}: subprocess")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("tesis_proyect.cli")
            ):
                violations.append(f"{path}: {node.module}")
    assert not violations, "Adapter coupling violations:\n" + "\n".join(violations)


def test_both_cli_adapters_use_core_commands_without_importing_each_other() -> None:
    core_cli = Path("src/tesis_proyect/cli/app.py").read_text(encoding="utf-8")
    domain_cli = (PACKAGE_ROOT / "cli.py").read_text(encoding="utf-8")
    assert "CoreCommands" in core_cli
    assert "CoreCommands" in domain_cli
    assert "tesis_domain_extensions" not in core_cli
    assert "tesis_proyect.cli" not in domain_cli


def test_domain_traceability_has_exact_requirements_and_resolvable_evidence() -> None:
    payload = json.loads(Path("traceability/domain_extensions.json").read_text(encoding="utf-8"))
    expected = {f"DE-RF-{number:02d}" for number in range(1, 20)} | {
        f"DE-RNF-{number:02d}" for number in range(1, 9)
    }
    requirements = payload["requirements"]
    assert {item["id"] for item in requirements} == expected
    assert len(requirements) == len(expected)
    suites = payload["suites"]
    for paths in suites.values():
        assert paths
        assert all(Path(path).is_file() for path in paths)
    for requirement in requirements:
        assert requirement["tests"]
        assert set(requirement["tests"]) <= set(suites)
        for reference in requirement["evidence"]:
            path_text, function_name = reference.split("::", maxsplit=1)
            source = Path(path_text).read_text(encoding="utf-8")
            assert f"def {function_name}(" in source


def test_common_domain_infrastructure_has_no_inspection_route_types() -> None:
    common_files = [
        PACKAGE_ROOT / "adapters.py",
        PACKAGE_ROOT / "application.py",
        PACKAGE_ROOT / "projection_store.py",
        PACKAGE_ROOT / "schema_generation.py",
    ]
    forbidden = (
        "InspectionRoute",
        "forest_id",
        "duplicate_forests",
        "constraint_set_id",
    )
    assert all(
        token not in path.read_text(encoding="utf-8")
        for path in common_files
        for token in forbidden
    )
    assert all(
        "SingleRow" not in path.read_text(encoding="utf-8")
        for path in common_files
        if path.name != "application.py"
    )
