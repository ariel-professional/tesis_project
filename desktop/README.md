# Tesis Project Desktop

Aplicación Windows del vertical slice React + Electron para ejecutar estudios
`single-row-facility-layout` sobre el CORE Python. El renderer sólo consume el
`DomainUiHost`; Electron main mantiene el proceso `tesis-desktop-gateway` y la
persistencia científica continúa bajo autoridad Python.

## Inicio rápido de desarrollo

Seguir los requisitos y comandos de la [guía de instalación y desarrollo](../docs/DESKTOP_INSTALLATION_AND_UPDATE.md#preparar-el-entorno-de-desarrollo).

`npm run dev` es el modo recomendado. Genera el registro y los tipos al inicio,
levanta Electron Forge y deja activos:

- HMR del renderer React y de las UI de dominio;
- recompilación incremental de main y preload;
- reinicio automático del gateway ante cambios `../src/**/*.py`;
- regeneración del registro al cambiar un manifest `ui/domain-ui*.json`;
- regeneración de tipos al cambiar los schemas desktop o SRFL.

Los cambios de `forge.config.ts` requieren reiniciar `npm run dev`. La política
de seguridad del servidor de desarrollo se toma del HTML del renderer mediante
`scripts/renderer-csp.cjs`, para permitir los adjuntos `blob:` también durante HMR.

No reconstruye el runtime Python embebido ni el instalador. Si cambia main o
preload y la ventana no toma el cambio, se escribe `rs` en la terminal de Forge. Un
cambio Python durante una ejecución activa difiere el reinicio del gateway hasta
que la operación termina. Así se conserva el cálculo en curso.

El comando queda corriendo deliberadamente hasta `Ctrl+C`. La aplicación está
lista recién cuando la terminal imprime `[desktop:ready]`. Para una comprobación
que termina sola y devuelve código de salida, se utiliza:

```powershell
npm run verify
```

El diagnóstico de Node/npm y los comandos de pruebas continuas están en esa misma guía.

## Comandos

| Comando | Uso |
|---|---|
| `npm run doctor` | Verifica versiones/rutas y que el gateway pueda iniciar. |
| `npm run verify` | Generación, typecheck, Vitest y handshake real del gateway; termina solo. |
| `npm run dev` / `npm run watch` | Desarrollo incremental completo. |
| `npm start` | Watch nativo de Forge y Python, sin regenerar manifests/schemas externos. |
| `npm run generate` | Regenera registro UI y tipos desde schemas existentes. |
| `npm run typecheck` | Verifica TypeScript sin emitir archivos. |
| `npm test` | Ejecuta Vitest una vez. |
| `npm run typecheck:watch` | Typecheck continuo. |
| `npm run test:watch` | Tests afectados en watch mode. |
| `npm run package` | Produce la aplicación desempaquetada. |
| `npm run make` | Produce los distributables Squirrel. |

## Archivos generados

No editar manualmente:

- `src/generated/domain-registry.ts`;
- `src/generated/gateway-message.d.ts`;
- `src/generated/single-row-facility-layout.d.ts`.

Sus fuentes son los manifests `ui/domain-ui*.json`,
`../desktop_schemas/1.5.0/gateway-message.schema.json` y los schemas de configuración
SRFL. Cambiar un modelo Pydantic no reescribe automáticamente un contrato
público: primero debe aprobarse y regenerarse el schema correspondiente.

## Documentación

- [Guía de usuario](../docs/DESKTOP_USER_GUIDE.md)
- [Instalación, actualización y release](../docs/DESKTOP_INSTALLATION_AND_UPDATE.md)
- [Contrato del gateway](../docs/contracts/desktop_gateway_contracts.md)

## Construir un instalador Windows

El procedimiento completo, incluida la preparación del runtime, las verificaciones
previas y la prueba offline del instalador, está en
[Construir un instalador nuevo](../docs/DESKTOP_INSTALLATION_AND_UPDATE.md#construir-un-instalador-nuevo).
La regeneración de contratos y tipos está en
[Regenerar contratos y tipos](../docs/DESKTOP_INSTALLATION_AND_UPDATE.md#regenerar-contratos-y-tipos).
