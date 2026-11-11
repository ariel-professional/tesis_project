from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from tesis_domain_extensions.contracts.common import (
    DomainExperimentId,
    NonNegativeInt,
    NormalizedText,
    StrictModel,
)

MediaType = Literal["image/png", "image/jpeg", "image/webp", "application/pdf"]


class FileAttachment(StrictModel):
    kind: Literal["file"]
    sha256: DomainExperimentId
    name: NormalizedText
    media_type: MediaType
    size_bytes: NonNegativeInt


class LinkAttachment(StrictModel):
    kind: Literal["link"]
    url: NormalizedText
    label: NormalizedText | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("El enlace debe ser una URL HTTP o HTTPS completa.")
        if any(character.isspace() for character in value):
            raise ValueError("El enlace no puede contener espacios.")
        return value


Attachment = Annotated[FileAttachment | LinkAttachment, Field(discriminator="kind")]
