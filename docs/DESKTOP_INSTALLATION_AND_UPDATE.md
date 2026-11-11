# Instalación y actualización — aplicación desktop

Esta guía cubre la instalación para usuarios, la actualización manual y la
construcción de una nueva build desde el repositorio.

## Instalar el artefacto Windows

El alcance validado es Windows 11 x64. La distribución Squirrel es autocontenida
y puede ejecutarse offline una vez descargada.

1. Obtener juntos el `Setup.exe` y `SHA256SUMS.json` de la misma build.
2. Verificar el hash:

   ```powershell
   Get-FileHash -Algorithm SHA256 '.\tesis-proyect-desktop-X.Y.Z Setup.exe'
   ```

3. Comparar el valor con la entrada correspondiente de `SHA256SUMS.json`.
4. Cerrar cualquier instancia anterior y ejecutar `Setup.exe`.
5. Abrir la aplicación desde el menú Inicio.

El prototipo actual no está firmado y puede activar SmartScreen. Un hash correcto
prueba integridad respecto de la evidencia entregada, no identidad editorial.

## Actualizar una instalación existente

Todavía no hay descarga ni actualización automática dentro de la aplicación. La
actualización es manual:

1. Cerrar la aplicación.
2. Respaldar `%APPDATA%\tesis-proyect-desktop\workspace`.
3. Leer las notas de la nueva build. Antes del primer release, un rebaseline de
   schemas puede exigir comenzar con un workspace nuevo; nunca se migra o reescribe
   evidencia silenciosamente.
4. Verificar el SHA-256 del nuevo instalador.
5. Ejecutar el nuevo `Setup.exe`. No se deben copiar archivos sueltos sobre la carpeta de
   instalación administrada por Squirrel.
6. Abrir la aplicación y confirmar que se pueden listar o recuperar las ejecuciones.

Si es necesario volver a una build anterior, primero debe conservarse una copia completa del
workspace. No se garantiza que una versión anterior comprenda evidencia creada
por una versión posterior.

## Preparar el entorno de desarrollo

Este recorrido ejecuta el código de una copia local; no instala ni actualiza
una aplicación construida previamente. Se debe abrir PowerShell en la carpeta
que contiene `pyproject.toml`. Se puede escribir `cd` seguido de la ruta de esa
carpeta entre comillas.

Requisitos:

- Windows 11 x64;
- Python 3.12 y `uv`;
- Node.js `>=22.13.0 <23` y npm 10; `.nvmrc` fija 22.17.1 como toolchain reproducible;
- copia completa del repositorio, incluidos `src/`, `desktop/`, `examples/` y los schemas.

Las herramientas se comprueban con `python --version`, `uv --version`,
`node --version` y `npm --version`. Python se puede instalar desde
[python.org](https://www.python.org/downloads/) y `uv` siguiendo su
[guía de instalación](https://docs.astral.sh/uv/getting-started/installation/).
Para Node se puede usar [nvm-windows](https://github.com/coreybutler/nvm-windows)
o instalar una versión compatible por otro medio; npm se distribuye con Node.
Si una herramienta recién instalada no se reconoce, se debe cerrar y volver a abrir la terminal.
La versión concreta fijada para el proyecto es Node 22.17.1 con npm 10.

Desde la raíz:

```powershell
uv sync --frozen --extra dev
Set-Location desktop
nvm install 22.17.1
nvm use 22.17.1
npm ci
npm run doctor
npm run dev
```

Los dos comandos `nvm` son necesarios sólo si se utiliza nvm-windows; con otra
instalación de Node compatible, se pueden omitir. `uv sync` crea el entorno local de
Python y `npm ci` instala las dependencias bloqueadas de la aplicación. La
primera instalación necesita acceso a las fuentes de paquetes.

Si `npm --version` no funciona, `npm run doctor` tampoco puede arrancar. En ese
caso debe repararse NVM primero. Para la toolchain fijada:

```powershell
nvm install 22.17.1
nvm use 22.17.1
node --version
npm --version
where.exe node
where.exe npm
```

No se debe combinar el `node.exe` de una versión con el npm de otra: un build obtenido así
no constituye evidencia reproducible.

`npm run dev` es watch mode: React usa HMR, main/preload se recompilan de manera
incremental, el gateway se reinicia al cambiar Python y el registro/tipos se
regeneran cuando cambian sus entradas. No ejecuta `package` ni `make`, y queda
activo hasta `Ctrl+C`. Es necesario esperar `[desktop:ready]` antes de usar la ventana.
Si hay un cálculo activo, el reinicio del gateway se difiere hasta que termine.

Para una verificación finita y repetible —no un servidor de desarrollo— se ejecuta:

```powershell
npm run verify
```

Este comando valida la toolchain, regenera archivos, ejecuta TypeScript/Vitest y
realiza `hello`, `ping` y `shutdown` contra un gateway Python real en un workspace
temporal. No reemplaza un E2E visual de Electron.

Para tests y tipos continuos:

```powershell
npm run typecheck:watch
npm run test:watch
```

Cada watcher se detiene con `Ctrl+C`. Si existe `ELECTRON_RUN_AS_NODE` en la sesión,
el script de desarrollo lo elimina sólo para su proceso hijo.

## Qué actualizar según el cambio

| Cambio | Acción durante desarrollo | Verificación mínima |
|---|---|---|
| React/CSS/UI SRFL | Guardar; HMR actualiza la ventana. | `npm test` y `npm run typecheck`. |
| Main o preload | Guardar; Webpack recompila. Escribir `rs` si la ventana no reinicia. | Typecheck y smoke de Electron. |
| Backend Python | Guardar; el gateway de desarrollo se reinicia. | Ruff, mypy y tests Python afectados. |
| `domain-ui*.json` | Guardar; watch regenera el registro multi-versión. | `npm run generate` y prueba del registro. |
| Schema desktop/SRFL | Regenerar el schema aprobado; watch actualiza `.d.ts`. | Tests de drift y typecheck. |
| Dependencias npm | Editar mediante npm para mantener el lock. Reiniciar watch. | `npm ci`, audit, tests y package. |
| Dependencias Python | Actualizar `pyproject.toml` y `uv.lock`. | `uv sync --frozen`, suite y runtime embebido. |

Los archivos de `desktop/src/generated/` no se editan a mano. El watch consume
schemas existentes pero no decide cambios contractuales: modificar contratos del
gateway, eventos, manifests o modelos agrupados requiere ADR y actualización de
sus pruebas/documentación.

## Regenerar contratos y tipos

Desde la raíz, y sólo después de aprobar el cambio contractual pertinente, se ejecuta:

```powershell
uv run python scripts/generate_schemas.py
uv run python scripts/generate_domain_schemas.py
uv run python -m tesis_desktop_gateway.schema_generation
npm --prefix desktop run generate
```

Los tests de contratos deben demostrar que una regeneración posterior no produce
drift.

## Selector de versión SRFL

El selector **Aplicación / modelo** y la compatibilidad entre definiciones se
explican en la [guía de usuario](DESKTOP_USER_GUIDE.md#elegir-aplicación-y-modelo).
Cada versión conserva sus propias ejecuciones; no existe conversión automática.

Cambiar el código fuente no reemplaza una aplicación instalada ni un paquete ya
generado. Para ver los cambios inmediatamente, se deben cerrar las instancias anteriores
y usar `npm run dev`. Para probar una aplicación desempaquetada nueva, se ejecuta
`npm run package` y se abre
`desktop/out/tesis-proyect-desktop-win32-x64/tesis-proyect-desktop.exe`. El
`Setup.exe` sólo cambia después de ejecutar el proceso de release correspondiente.

## Construir un instalador nuevo

1. Actualizar coherentemente la versión de la aplicación y el lockfile. Una
   actualización Squirrel debe tener una versión superior a la instalada.
2. Descargar el ZIP embebible oficial `python-3.12.10-embed-amd64.zip` en
   `desktop/`. El script verifica su SHA-256 fijado antes de usarlo.
3. Ensamblar el runtime:

   ```powershell
   .\desktop\scripts\assemble-python.ps1
   ```

4. Ejecutar los gates:

   ```powershell
   uv run ruff check src tests scripts desktop/scripts/generate-release-evidence.py
   uv run ruff format --check src tests scripts desktop/scripts/generate-release-evidence.py
   uv run mypy src
   uv run pytest
   npm --prefix desktop run typecheck
   npm --prefix desktop test
   ```

5. Empaquetar y generar evidencia:

   ```powershell
   npm --prefix desktop run make
   uv run python desktop/scripts/generate-release-evidence.py
   ```

Los distributables quedan en `desktop/out/make/` y el SBOM, hashes y avisos en
`desktop/release-evidence/`. Antes de publicar, se debe probar el `Setup.exe` en una
Windows 11 x64 limpia, offline y sin Python o Node del sistema. La firma de código
es obligatoria para una release pública, aunque el prototipo interno siga sin
firma.
