"""Session-scoped staging and immutable, content-addressed documentary files."""

from __future__ import annotations

import base64
import hashlib
import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from pydantic import BaseModel

from tesis_domain_extensions.contracts.evidence import FileAttachment, MediaType
from tesis_domain_extensions.errors import DomainExtensionError

CHUNK_BYTES = 512 * 1024


def file_references(config: BaseModel) -> list[FileAttachment]:
    """Collect documentary references without depending on a concrete domain model."""

    return file_references_in_document(config.model_dump(mode="json"))


def file_references_in_document(document: Any) -> list[FileAttachment]:
    """Collect and validate every file reference in an arbitrary JSON document."""

    def visit(value: Any) -> list[FileAttachment]:
        if isinstance(value, dict):
            if value.get("kind") == "file":
                return [FileAttachment.model_validate(value)]
            return [ref for child in value.values() for ref in visit(child)]
        if isinstance(value, list):
            return [ref for child in value for ref in visit(child)]
        return []

    return visit(document)


def real_directory(path: Path) -> Path:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise DomainExtensionError("El directorio de adjuntos no es seguro.")
    path.mkdir(exist_ok=True)
    return path


def detect_media(stream: BinaryIO) -> MediaType:
    header = stream.read(16)
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    raise DomainExtensionError("El contenido no es PNG, JPEG, WebP ni PDF.")


@dataclass
class Upload:
    path: Path
    name: str
    media_type: MediaType
    expected_size: int
    received: int = 0
    reference: FileAttachment | None = None
    digest: Any = field(default_factory=hashlib.sha256)


class AttachmentStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.session_id = str(uuid4())
        self.uploads: dict[str, Upload] = {}
        self.authorized: dict[str, FileAttachment] = {}
        self.verified: dict[str, tuple[int, int, int, str]] = {}

    def begin(self, name: str, media_type: MediaType, size_bytes: int) -> str:
        root = real_directory(self.workspace / ".domain_attachment_staging")
        session = real_directory(root / self.session_id)
        upload_id = str(uuid4())
        path = session / upload_id
        path.touch(exist_ok=False)
        self.uploads[upload_id] = Upload(path, name, media_type, size_bytes)
        return upload_id

    def _upload(self, upload_id: str) -> Upload:
        if upload_id not in self.uploads:
            raise DomainExtensionError("La transferencia ya no pertenece a esta sesión.")
        upload = self.uploads[upload_id]
        if upload.path.is_symlink() or not upload.path.resolve().is_relative_to(self.workspace):
            raise DomainExtensionError("Ruta de transferencia no autorizada.")
        return upload

    def append(self, upload_id: str, offset: int, data: str) -> int:
        upload = self._upload(upload_id)
        block = base64.b64decode(data, validate=True)
        if upload.reference is not None or offset != upload.received:
            raise DomainExtensionError("El bloque no corresponde al estado de la transferencia.")
        if not block or len(block) > CHUNK_BYTES:
            raise DomainExtensionError("El bloque debe contener entre 1 y 524288 bytes.")
        if upload.received + len(block) > upload.expected_size:
            raise DomainExtensionError("El archivo supera el tamaño declarado.")
        with upload.path.open("r+b") as stream:
            stream.seek(offset)
            try:
                stream.write(block)
                stream.flush()
            except OSError:
                stream.truncate(offset)
                raise
        upload.received += len(block)
        upload.digest.update(block)
        return upload.received

    def finish(self, upload_id: str) -> FileAttachment:
        upload = self._upload(upload_id)
        if upload.reference is not None:
            return upload.reference
        if upload.received != upload.expected_size:
            raise DomainExtensionError("La transferencia está incompleta.")
        with upload.path.open("rb") as stream:
            media = detect_media(stream)
            if media != upload.media_type:
                raise DomainExtensionError("El tipo declarado no coincide con el contenido.")
            digest = upload.digest.hexdigest()
        upload.reference = FileAttachment(
            kind="file",
            sha256=digest,
            name=upload.name,
            media_type=media,
            size_bytes=upload.received,
        )
        self.authorized[digest] = upload.reference
        return upload.reference

    def authorize(self, config: BaseModel) -> None:
        self.authorized.update({ref.sha256: ref for ref in file_references(config)})

    def _durable_path(self, digest: str) -> Path:
        root = self.workspace / "domain_attachments"
        if root.is_symlink():
            raise DomainExtensionError("El directorio de adjuntos no es seguro.")
        path = root / digest
        if path.is_symlink() or not path.resolve().is_relative_to(self.workspace):
            raise DomainExtensionError("Ruta de adjunto no autorizada.")
        return path

    def _source(self, ref: FileAttachment) -> Path:
        durable = self._durable_path(ref.sha256)
        if durable.exists():
            return durable
        for upload_id, upload in self.uploads.items():
            if upload.reference is not None and upload.reference.sha256 == ref.sha256:
                return self._upload(upload_id).path
        raise DomainExtensionError(f"Adjunto no disponible: {ref.name}. Volvé a adjuntarlo.")

    def _verify(self, ref: FileAttachment, path: Path) -> None:
        stat = path.stat()
        signature = (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, ref.media_type)
        if self.verified.get(str(path)) == signature and stat.st_size == ref.size_bytes:
            return
        with path.open("rb") as stream:
            media = detect_media(stream)
            stream.seek(0)
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != ref.sha256 or stat.st_size != ref.size_bytes or media != ref.media_type:
            raise DomainExtensionError(f"El adjunto está dañado o no coincide: {ref.name}.")
        self.verified[str(path)] = signature

    def publish(self, config: BaseModel) -> None:
        refs = file_references(config)
        # Validate every reference before publishing any files or configuration.
        sources = [(ref, self._source(ref)) for ref in refs]
        for ref, source in sources:
            self._verify(ref, source)
        if not sources:
            return
        real_directory(self.workspace / "domain_attachments")
        for ref, source in sources:
            target = self._durable_path(ref.sha256)
            if not target.exists():
                with source.open("r+b") as stream:
                    os.fsync(stream.fileno())
                with suppress(FileExistsError):
                    os.link(source, target)
            self._verify(ref, target)
        self.authorize(config)

    def read(self, digest: str, offset: int, length: int) -> str:
        ref = self.authorized.get(digest)
        if ref is None:
            raise DomainExtensionError("El adjunto no pertenece al contexto abierto.")
        source = self._source(ref)
        self._verify(ref, source)
        if offset < 0 or length < 0 or length > CHUNK_BYTES:
            raise DomainExtensionError("Rango de lectura inválido.")
        with source.open("rb") as stream:
            stream.seek(offset)
            return base64.b64encode(stream.read(length)).decode("ascii")

    def abort(self, upload_id: str) -> None:
        if upload_id not in self.uploads:
            return
        upload = self._upload(upload_id)
        upload.path.unlink(missing_ok=True)
        del self.uploads[upload_id]

    def close(self) -> None:
        for upload_id in list(self.uploads):
            self.abort(upload_id)
        session = self.workspace / ".domain_attachment_staging" / self.session_id
        if session.is_dir() and not session.is_symlink():
            session.rmdir()
