from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tesis_domain_extensions.attachment_store import AttachmentStore
from tesis_domain_extensions.contracts.evidence import LinkAttachment
from tesis_domain_extensions.domains.single_row_facility_layout.adapter import (
    SingleRowFacilityLayoutAdapter,
)
from tesis_domain_extensions.errors import DomainExtensionError

PDF = b"%PDF-1.7\n% documentary fixture\n%%EOF\n"


@pytest.mark.parametrize("failure", ["interrupted", "write_error"])
def test_incomplete_transfer_cannot_publish_and_retry_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    store = AttachmentStore(tmp_path)
    upload = store.begin("plano.pdf", "application/pdf", len(PDF))
    if failure == "write_error":
        original = Path.open

        def broken_open(self: Path, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            if self.name == upload:
                raise OSError("simulated write failure")
            return original(self, *args, **kwargs)  # type: ignore[arg-type]

        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", broken_open)
            with pytest.raises(OSError):
                store.append(upload, 0, base64.b64encode(PDF).decode())
    else:
        store.append(upload, 0, base64.b64encode(PDF[:8]).decode())
    with pytest.raises(DomainExtensionError, match="incompleta"):
        store.finish(upload)
    assert not (tmp_path / "domain_attachments").exists()
    store.abort(upload)
    retried = store.begin("plano.pdf", "application/pdf", len(PDF))
    store.append(retried, 0, base64.b64encode(PDF).decode())
    reference = store.finish(retried)
    assert base64.b64decode(store.read(reference.sha256, 5, 8)) == PDF[5:13]
    store.close()


def test_document_validation_and_read_scope(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    upload = store.begin("falso.png", "image/png", len(PDF))
    store.append(upload, 0, base64.b64encode(PDF).decode())
    with pytest.raises(DomainExtensionError, match="no coincide"):
        store.finish(upload)
    with pytest.raises(DomainExtensionError, match="contexto"):
        store.read("../outside", 0, 1)
    with pytest.raises(ValidationError):
        LinkAttachment(kind="link", url="javascript:alert(1)")
    store.close()


def test_missing_reference_blocks_commit_and_reupload_resolves_it(tmp_path: Path) -> None:
    import hashlib

    adapter = SingleRowFacilityLayoutAdapter()
    payload = json.loads(
        Path("examples/domains/single-row-facility-layout/comparison.json").read_bytes()
    )
    reference = {
        "kind": "file",
        "sha256": hashlib.sha256(PDF).hexdigest(),
        "name": "plano.pdf",
        "media_type": "application/pdf",
        "size_bytes": len(PDF),
    }
    payload["study"]["attachments"] = [reference]
    config = adapter.parse_config(json.dumps(payload).encode())
    store = AttachmentStore(tmp_path)
    with pytest.raises(DomainExtensionError, match="no disponible"):
        store.publish(config)
    upload = store.begin("plano.pdf", "application/pdf", len(PDF))
    store.append(upload, 0, base64.b64encode(PDF).decode())
    store.finish(upload)
    store.publish(config)
    store.close()
    assert (tmp_path / "domain_attachments" / reference["sha256"]).read_bytes() == PDF
