from __future__ import annotations

from tesis_domain_extensions.errors import DomainExtensionError

from .contracts import AdjacencyValueMatrix, FlowMatrix, ObjectiveDefinition, ObjectiveSnapshot

OBJECTIVE_CATALOG: tuple[ObjectiveDefinition, ...] = (
    ObjectiveDefinition(
        id="retained-compatible-layouts",
        version="1",
        name="Flexibilidad de distribución",
        summary="Porcentaje de alternativas de distribución que siguen siendo posibles.",
        decision_question=(
            "¿Qué alternativa deja más opciones abiertas para definir la distribución final?"
        ),
        classification="criterion",
        direction="maximize",
        unit="fracción exacta",
        formula="H_i / H_D",
        scope="case",
        required_inputs=["core-layout-count"],
        evidence=["Conteos CORE confirmados para el caso y el diseño base."],
        limitations=["No mide distancia, costo ni robustez física."],
    ),
    ObjectiveDefinition(
        id="rel-closeness",
        version="1",
        name="Cobertura de prioridades de cercanía",
        summary=(
            "Porcentaje de relaciones prioritarias del nivel que la alternativa "
            "incorpora como adyacencias obligatorias."
        ),
        decision_question=(
            "¿Qué alternativa cubre más relaciones de cercanía y en qué niveles de prioridad REL?"
        ),
        classification="criterion",
        direction="maximize",
        unit="fracción exacta por nivel",
        formula="relaciones del nivel incorporadas / relaciones declaradas en ese nivel",
        scope="prescribed_adjacencies",
        required_inputs=["rel-matrix"],
        evidence=["Matriz REL completa y aristas prescriptas del caso."],
        limitations=[
            "Cuenta adyacencias obligatorias; no incluye cercanías que puedan aparecer "
            "ocasionalmente en una disposición."
        ],
    ),
    ObjectiveDefinition(
        id="captured-adjacency-flow",
        version="1",
        name="Valores de las adyacencias obligatorias",
        summary=(
            "Compara una o más matrices de flujo, costo, riesgo o beneficio sobre "
            "los pares que cada alternativa vuelve obligatorios."
        ),
        decision_question=("¿Qué alternativa obtiene el mejor valor en cada matriz declarada?"),
        classification="criterion",
        direction="maximize",
        direction_mode="per_instance",
        repeatable_input=True,
        unit="unidad declarada por matriz",
        formula="suma de los valores de los pares convertidos en adyacencias obligatorias",
        scope="prescribed_adjacencies",
        required_inputs=["flow-matrix"],
        evidence=["Matrices completas y aristas prescriptas del caso."],
        limitations=["No evalúa distancias ni una disposición física final."],
    ),
)


def resolve_objective(identifier: str, version: str = "1") -> ObjectiveDefinition:
    for definition in OBJECTIVE_CATALOG:
        if definition.id == identifier and definition.version == version:
            return definition
    raise DomainExtensionError(f"criterio SRFL desconocido: {identifier}@{version}")


def selected_objective_snapshots(decision_model: object) -> list[ObjectiveSnapshot]:
    snapshots: list[ObjectiveSnapshot] = []
    selected = {
        (item.id, item.version) for item in getattr(decision_model, "selected_objectives", [])
    }
    if ("retained-compatible-layouts", "1") in selected:
        snapshots.append(
            ObjectiveSnapshot(definition=resolve_objective("retained-compatible-layouts"))
        )
    rel = getattr(decision_model, "rel_closeness", None)
    if rel is not None and ("rel-closeness", "1") in selected:
        levels = sorted(
            {item.level for item in rel.requirements if item.level in {"A", "E", "I", "O"}}
        )
        definition = resolve_objective("rel-closeness")
        for level in levels:
            snapshots.append(
                ObjectiveSnapshot(
                    definition=definition.model_copy(
                        update={
                            "id": f"rel-closeness-{level.lower()}",
                            "name": f"{definition.name} · nivel {level}",
                            "unit": f"fracción exacta REL {level}",
                        }
                    )
                )
            )
    if ("captured-adjacency-flow", "1") in selected:
        flow = getattr(decision_model, "adjacency_flow", None)
        definition = resolve_objective("captured-adjacency-flow")
        if isinstance(flow, list):
            for matrix in flow:
                if not isinstance(matrix, AdjacencyValueMatrix):
                    continue
                period = (
                    f" por {matrix.reference_period}" if matrix.reference_period is not None else ""
                )
                direction_verb = "maximiza" if matrix.direction == "maximize" else "minimiza"
                snapshots.append(
                    ObjectiveSnapshot(
                        definition=definition.model_copy(
                            update={
                                "id": f"adjacency-{matrix.id}",
                                "name": matrix.name,
                                "summary": matrix.description,
                                "decision_question": (
                                    f"¿Qué alternativa {direction_verb} {matrix.name}?"
                                ),
                                "direction": matrix.direction,
                                "direction_mode": "fixed",
                                "repeatable_input": False,
                                "unit": f"{matrix.unit}{period}",
                                "evidence": [f"Fuente declarada: {matrix.provenance}."],
                            }
                        )
                    )
                )
        elif isinstance(flow, FlowMatrix):
            snapshots.append(
                ObjectiveSnapshot(
                    definition=definition.model_copy(
                        update={
                            "name": "Flujo entre áreas adyacentes",
                            "summary": (
                                "Suma los movimientos entre pares de áreas que la "
                                "alternativa vuelve obligatorios."
                            ),
                            "decision_question": (
                                "¿Qué alternativa incorpora mayor volumen de movimientos?"
                            ),
                            "direction_mode": "fixed",
                            "repeatable_input": False,
                            "unit": "unidad declarada por horizonte",
                        }
                    )
                )
            )
    return snapshots
