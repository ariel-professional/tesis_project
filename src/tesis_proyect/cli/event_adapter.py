from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode
from tesis_proyect.models.protocols import EventEnvelope
from tesis_proyect.observation import PublicEventObserver

if TYPE_CHECKING:
    pass


class EventSink:
    def __init__(
        self,
        *,
        output: Callable[[str], None] = lambda line: print(line, file=sys.stdout, flush=True),
        persist_path: Path | None = None,
        max_payload_bytes: int = 65_536,
    ) -> None:
        self.output = output
        self.persist_path = persist_path
        self.max_payload_bytes = max_payload_bytes

    def emit(self, event: EventEnvelope) -> None:
        line = json.dumps(
            event.model_dump(mode="json", by_alias=True),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        payload = (line + "\n").encode("utf-8")
        if len(payload) > self.max_payload_bytes:
            raise OperationalError(ErrorCode.IO_ERROR, "Event exceeds its payload limit.")
        self.output(line)
        if self.persist_path is not None:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self.persist_path.open("ab") as handle:
                handle.write(payload)
                handle.flush()


__all__ = ["EventSink", "PublicEventObserver"]
