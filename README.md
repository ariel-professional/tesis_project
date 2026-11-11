# Tesis Project

Aplicación para estudiar caminos hamiltonianos con aristas prescriptas y su aplicación a problemas específicos. Incluye un núcleo Python, interfaces de línea de comandos y una aplicación de escritorio Electron/React.

## Desarrollo

Requiere Python 3.12 o posterior y [uv](https://docs.astral.sh/uv/):

```powershell
uv sync --frozen --extra dev
uv run tesis-proyect --help
uv run tesis-domain --help
uv run pytest
```

Para la aplicación desktop, seguir la [guía de instalación y desarrollo](docs/DESKTOP_INSTALLATION_AND_UPDATE.md#preparar-el-entorno-de-desarrollo), que incluye requisitos, comandos y comprobaciones. La misma guía describe la instalación desde un ejecutable.

## Documentación
- [Guía del núcleo](docs/USER_GUIDE.md) y [guía de dominios](docs/DOMAIN_GUIDE.md).
- [Guía de usuario desktop](docs/DESKTOP_USER_GUIDE.md).
- [Arquitectura](docs/architecture/repository-layout.md), [contratos](docs/contracts/) y [decisiones de arquitectura](docs/decisions/).
- `examples/` contiene ejemplos; `domain_schemas/` y `desktop_schemas/` contienen contratos versionados. Los schemas JSON del núcleo se generan con `uv run python scripts/generate_schemas.py` en `schemas/1.0.0/`.
