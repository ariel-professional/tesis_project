from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path("src/tesis_proyect")

FORBIDDEN_TOP_LEVEL: dict[str, set[str]] = {
    "models": {
        "application",
        "cli",
        "domain",
        "engines",
        "persistence",
        "pipeline",
        "reporting",
        "runner",
    },
    "domain": {"application", "cli", "engines", "persistence", "pipeline", "reporting", "runner"},
    "engines": {"application", "cli", "persistence", "pipeline", "reporting", "runner"},
    "persistence": {
        "application",
        "cli",
        "domain",
        "engines",
        "pipeline",
        "reporting",
        "runner",
    },
    "runner": {"application", "cli", "pipeline", "reporting"},
    "reporting": {
        "application",
        "cli",
        "domain",
        "engines",
        "pipeline",
        "runner",
    },
    "pipeline": {"application", "cli"},
    "application": {"cli"},
}


def _module(path: Path) -> str:
    relative = path.relative_to(Path("src")).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(
                alias.name for alias in node.names if alias.name.startswith("tesis_proyect")
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("tesis_proyect")
        ):
            result.add(node.module)
    return result


def test_internal_dependency_direction() -> None:
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        relative = path.relative_to(PACKAGE_ROOT)
        owner = relative.parts[0] if len(relative.parts) > 1 else "root"
        forbidden = FORBIDDEN_TOP_LEVEL.get(owner, set())
        for imported in _imports(path):
            parts = imported.split(".")
            target = parts[1] if len(parts) > 1 else "root"
            if target in forbidden:
                violations.append(f"{_module(path)} -> {imported}")
    assert not violations, "Forbidden imports:\n" + "\n".join(sorted(violations))


def test_internal_module_graph_is_acyclic() -> None:
    paths = list(PACKAGE_ROOT.rglob("*.py"))
    modules = {_module(path): path for path in paths}
    graph = {
        module: {dependency for dependency in _imports(path) if dependency in modules}
        for module, path in modules.items()
    }
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(module: str) -> None:
        if module in visiting:
            cycle = [*visiting[visiting.index(module) :], module]
            raise AssertionError("Import cycle: " + " -> ".join(cycle))
        if module in visited:
            return
        visiting.append(module)
        for dependency in graph[module]:
            visit(dependency)
        visiting.pop()
        visited.add(module)

    for module in graph:
        visit(module)
