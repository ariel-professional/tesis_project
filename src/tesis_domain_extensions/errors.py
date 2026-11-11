from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError


class DomainExtensionError(Exception):
    def __init__(self, message: str, *, exit_code: int = 65) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class DomainRunCancelled(Exception):
    """Cooperative stop requested while generating or scheduling domain cases."""

    def __init__(self, manifest: object | None = None) -> None:
        super().__init__("La ejecución de dominio fue cancelada.")
        self.manifest = manifest


_VALIDATION_MESSAGES = {
    "missing": "falta el campo obligatorio",
    "extra_forbidden": "el campo no está permitido",
    "json_invalid": "el archivo no contiene JSON válido",
    "literal_error": "el valor no pertenece al conjunto admitido",
    "list_type": "se esperaba una lista",
    "tuple_type": "se esperaba un par",
    "string_type": "se esperaba texto",
    "int_type": "se esperaba un entero",
    "bool_type": "se esperaba true o false",
    "too_short": "no contiene suficientes elementos",
    "greater_than": "el valor debe ser mayor que el mínimo permitido",
    "greater_than_equal": "el valor no alcanza el mínimo permitido",
}


def _validation_message(issue: Mapping[str, object]) -> str:
    context = issue.get("ctx")
    if issue.get("type") == "value_error" and isinstance(context, dict):
        error = context.get("error")
        if isinstance(error, ValueError):
            return str(error)
    kind = issue.get("type")
    if isinstance(kind, str):
        return _VALIDATION_MESSAGES.get(kind, "valor inválido")
    return "valor inválido"


def invalid_domain_config(error: ValidationError) -> DomainExtensionError:
    lines = ["La configuración del dominio es inválida:"]
    for issue in error.errors(include_url=False):
        location = issue.get("loc", ())
        path = ".".join(str(item) for item in location) or "configuración"
        lines.append(f"- {path}: {_validation_message(issue)}")
    return DomainExtensionError("\n".join(lines), exit_code=65)
