from __future__ import annotations

from collections.abc import Mapping, Sequence


def format_layout_case_progress(
    *,
    design_title: str,
    added_component_ids: Sequence[str],
    component_station_ids: Mapping[str, Sequence[str]],
    station_names: Mapping[str, str],
) -> str:
    """Describe a generated case with the labels visible in the study editor."""

    if not added_component_ids:
        return f"{design_title} · sin restricciones agregadas"

    def component_label(component_id: str) -> str:
        station_ids = component_station_ids.get(component_id)
        if station_ids is None:
            return "Restricción sin nombre"
        return " → ".join(station_names.get(station_id, station_id) for station_id in station_ids)

    added = ", ".join(component_label(item) for item in added_component_ids)
    return f"{design_title} · restricciones agregadas: {added}"
