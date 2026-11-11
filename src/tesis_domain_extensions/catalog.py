from __future__ import annotations

import json
from typing import Any, cast

from tesis_domain_extensions.adapters import DomainAdapter
from tesis_domain_extensions.domains.inspection_route.adapter import InspectionRouteAdapter
from tesis_domain_extensions.domains.single_row_facility_layout.adapter import (
    SingleRowFacilityLayoutAdapter,
)
from tesis_domain_extensions.domains.single_row_facility_layout.adapter_v2 import (
    SingleRowFacilityLayoutAdapterV2,
)
from tesis_domain_extensions.domains.single_row_facility_layout.adapter_v21 import (
    SingleRowFacilityLayoutAdapterV21,
)
from tesis_domain_extensions.errors import DomainExtensionError


def build_catalog(adapters: tuple[Any, ...]) -> dict[tuple[str, str], DomainAdapter]:
    catalog: dict[tuple[str, str], DomainAdapter] = {}
    for adapter in adapters:
        domain_id = getattr(adapter, "domain_id", None)
        version = getattr(adapter, "version", None)
        if not isinstance(domain_id, str) or not isinstance(version, str):
            raise ValueError("domain adapters require string id and version")
        key = (domain_id, version)
        if key in catalog:
            raise ValueError(f"duplicate domain adapter: {domain_id}@{version}")
        required = (
            "parse_config",
            "project",
            "display_name",
            "interpret",
            "render_human",
            "render_json",
            "render_markdown",
            "build_projection_record",
            "parse_projection_record",
            "iter_cases",
            "generate_cases",
            "theoretical_combinations",
            "persisted_case_id",
            "generation_duplicate_count",
            "build_persisted_case",
            "build_generation_metrics",
        )
        if not all(callable(getattr(adapter, name, None)) for name in required):
            raise ValueError(f"incomplete domain adapter: {domain_id}@{version}")
        catalog[key] = cast(DomainAdapter, adapter)
    return catalog


SUPPORTED_DOMAINS = build_catalog(
    (
        InspectionRouteAdapter(),
        SingleRowFacilityLayoutAdapter(),
        SingleRowFacilityLayoutAdapterV2(),
        SingleRowFacilityLayoutAdapterV21(),
    )
)


def resolve_adapter(payload: bytes) -> DomainAdapter:
    try:
        document = json.loads(payload)
        domain = document["domain"]
        key = (domain["id"], domain["version"])
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainExtensionError("La configuración no identifica un dominio válido.") from exc
    if not isinstance(key[0], str) or not isinstance(key[1], str):
        raise DomainExtensionError("El identificador y la versión del dominio deben ser strings.")
    adapter = SUPPORTED_DOMAINS.get(key)
    if adapter is None:
        raise DomainExtensionError(f"El dominio {key[0]}@{key[1]} no está soportado.")
    return adapter
