from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from tesis_desktop_gateway.models import GatewayMessage


def schema_bytes() -> bytes:
    schema = TypeAdapter(GatewayMessage).json_schema()
    return (json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write_schema(root: Path) -> Path:
    target = root / "desktop_schemas" / "1.5.0" / "gateway-message.schema.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(schema_bytes())
    return target


def main() -> None:
    write_schema(Path.cwd())


if __name__ == "__main__":
    main()
