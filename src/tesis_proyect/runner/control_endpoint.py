from __future__ import annotations

import hashlib
import os
import tempfile
import unicodedata
from pathlib import Path

from tesis_proyect.errors import OperationalError
from tesis_proyect.models.enums import ErrorCode


def canonical_workspace_bytes(workspace: Path) -> bytes:
    resolved = unicodedata.normalize("NFC", str(workspace.resolve(strict=True)))
    if os.name == "nt":
        resolved = os.path.normcase(resolved).replace("\\", "/")
    return resolved.encode("utf-8")


def control_digest(workspace: Path, run_id: str) -> str:
    payload = (
        b"tesis-proyect-control-v1\0"
        + canonical_workspace_bytes(workspace)
        + b"\0"
        + run_id.encode("ascii")
    )
    return hashlib.sha256(payload).hexdigest()


def control_endpoint(workspace: Path, run_id: str) -> str:
    digest = control_digest(workspace, run_id)
    if os.name == "nt":
        return rf"\\.\pipe\tesis-proyect-ctl-{digest}"
    root = _unix_runtime_root()
    endpoint = root / f"ctl-{digest}.sock"
    if len(os.fsencode(endpoint)) >= 104:
        raise OperationalError(ErrorCode.RUN_CONTROL_UNAVAILABLE, "Unix control path is too long.")
    return str(endpoint)


def _unix_runtime_root() -> Path:
    uid = getattr(os, "getuid", lambda: 0)()
    configured = os.environ.get("XDG_RUNTIME_DIR")
    if configured:
        try:
            candidate = Path(configured).resolve(strict=True)
            stat = candidate.stat()
        except OSError:
            pass
        else:
            if candidate.is_dir() and stat.st_uid == uid and stat.st_mode & 0o077 == 0:
                root = candidate / "tesis-proyect"
                root.mkdir(mode=0o700, exist_ok=True)
                os.chmod(root, 0o700)
                return root
    root = Path(tempfile.gettempdir()) / f"tesis-proyect-{uid}"
    root.mkdir(mode=0o700, exist_ok=True)
    os.chmod(root, 0o700)
    return root
