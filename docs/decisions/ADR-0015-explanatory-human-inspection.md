# ADR-0015 — Explanatory human inspection with stable NDJSON

- Estado: accepted
- Fecha: 2026-08-06

- Objetivos afectados: OBJ-8, OBJ-9
- Requisitos afectados: RC-05, RPE-08
- Resuelve: no aplica
- Regla normativa: `docs/contracts/public_contract_catalog.md`, sección 5



## Contexto

La vista humana de `inspect` mostraba únicamente UUID, status y cantidad de
stages. La ejecución real demostró que esa salida no permitía entender la
instancia, el conteo, la ausencia del motor exacto ni por qué `resume` no era
una acción válida. La revisión simultánea de NDJSON confirmó que sus vistas son
correctas como estado operativo, aunque deliberadamente no incluyen el
contenido de los artefactos científicos.

## Alternativas consideradas

Se consideraron ampliar las vistas NDJSON, agregar otro formato público o
enriquecer solo la presentación humana usando la evidencia ya persistida.

## Decisión

`inspect --format human` derivará una explicación completa y no mutante del
run, y una inspección detallada del último intento de un stage. Las formas
NDJSON conservarán exactamente los schemas `RunInspection` y
`StageInspection`; los resultados científicos seguirán siendo artefactos
referenciados por ruta, hash y tamaño.

## Justificación

La vista humana necesita responder qué se ejecutó, qué resultado existe, qué
limitación impide una comparación y qué comandos son válidos a continuación.
Mantener NDJSON evita romper automatizaciones y conserva la separación entre
estado operativo y evidencia científica autocontenida.

## Consecuencias

La salida humana es más extensa y puede evolucionar editorialmente dentro de
los campos mínimos aprobados. No cambia ningún schema JSON, evento, archivo
persistido ni gramática de comandos. La documentación debe distinguir eventos,
inspección operativa y reportes.

## Trazabilidad

Aprobación explícita del responsable del proyecto el 2026-08-06; ADR-0011;
`tests/test_cli_contract.py`; `docs/USER_GUIDE.md`.
