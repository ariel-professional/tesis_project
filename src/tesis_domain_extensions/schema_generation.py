from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from tesis_domain_extensions.catalog import SUPPORTED_DOMAINS

DOMAIN_SCHEMA_CATALOG: dict[tuple[str, str], dict[str, type[BaseModel]]] = {
    identity: adapter.schema_models for identity, adapter in SUPPORTED_DOMAINS.items()
}


def schema_bytes(model: type[BaseModel]) -> bytes:
    return (
        json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def write_domain_schemas(
    destination: Path,
    *,
    domain_id: str,
    version: str,
) -> None:
    try:
        schemas = DOMAIN_SCHEMA_CATALOG[(domain_id, version)]
    except KeyError as exc:
        raise ValueError(f"unknown domain schema catalog: {domain_id}@{version}") from exc
    destination.mkdir(parents=True, exist_ok=True)
    for name, model in schemas.items():
        (destination / name).write_bytes(schema_bytes(model))


def write_all_domain_schemas(root: Path) -> None:
    for domain_id, version in DOMAIN_SCHEMA_CATALOG:
        write_domain_schemas(
            root / domain_id / version,
            domain_id=domain_id,
            version=version,
        )
