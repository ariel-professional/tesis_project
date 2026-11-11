from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from tesis_domain_extensions.contracts.common import (
    DomainExperimentId,
    DomainExperimentReference,
    DomainRef,
    NormalizedText,
    RunId,
    RunReference,
    StrictModel,
    Timestamp,
)


def canonical_domain_config(config: BaseModel) -> bytes:
    return json.dumps(
        config.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def domain_experiment_id(config: BaseModel, instance_nonce: str | None = None) -> str:
    canonical = canonical_domain_config(config)
    if instance_nonce is None:
        return hashlib.sha256(canonical).hexdigest()
    if re.fullmatch(r"[0-9a-f]{32}", instance_nonce) is None:
        raise ValueError("instance_nonce must be 32 lowercase hexadecimal characters")
    return hashlib.sha256(
        b"domain-experiment-instance-v1\0" + instance_nonce.encode("ascii") + b"\0" + canonical
    ).hexdigest()


class DomainExperimentProjectionBase(StrictModel):
    schema_version: Literal["1.0.0"]
    domain_experiment_id: DomainExperimentId
    created_at: Timestamp
    instance_nonce: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")


class DomainExperimentSummaryBase(StrictModel):
    schema_version: Literal["1.0.0"]
    reference: DomainExperimentReference
    domain_experiment_id: DomainExperimentId
    domain: DomainRef
    display_name: NormalizedText
    created_at: Timestamp


class DomainRunSummaryBase(StrictModel):
    schema_version: Literal["1.0.0"]
    run_reference: RunReference
    run_id: RunId
    domain_experiment_reference: DomainExperimentReference
    domain_experiment_id: DomainExperimentId
    domain: DomainRef
    display_name: NormalizedText
    status: Literal["created", "running", "completed", "failed", "cancelled"]
    created_at: Timestamp
    updated_at: Timestamp
