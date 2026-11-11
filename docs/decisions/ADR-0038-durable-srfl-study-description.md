# ADR-0038 — Descripción durable e identidad interna de estudios SRFL

**Estado:** accepted  
**Fecha:** 2026-09-07

## Contexto

La UI sólo permitía titular un estudio y exponía `study.id` como un campo editable. El contrato
SRFL no admitía una descripción, por lo que cualquier contexto agregado sólo en React se perdería
al preparar el experimento.

## Decisión

- Agregar `study.description` opcional al contrato SRFL `1.0.0` durante su etapa pre-release.
- Conservar la descripción en la configuración validada, la proyección content-addressed y el
  resultado confirmado como `study_description`.
- Mantener compatibles las definiciones existentes mediante `description: null`.
- Generar un UUID con prefijo `study-` para cada borrador nuevo en Desktop, incluido el creado
  desde una plantilla o definición importada.
- No exponer `study.id` como control editable ni como información principal de la UI.

## Consecuencias

La descripción participa del hash del experimento porque forma parte de la configuración validada.
Una definición importada se usa como origen de un experimento nuevo y por eso no reutiliza su ID de
estudio. Se regeneran los schemas de dominio y los tipos TypeScript; no cambian CORE ni el protocolo
gateway.
