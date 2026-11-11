from __future__ import annotations

from typing import Literal

from pydantic import StrictBool

from tesis_domain_extensions.contracts.common import (
    NonNegativeInt,
    PositiveInt,
    StrictModel,
)


class ExactMethodConfig(StrictModel):
    engine: Literal["auto"]


class ReferenceMethodConfig(StrictModel):
    engine: Literal["bruteforce_python_v1"]


class MethodsConfig(StrictModel):
    exact: ExactMethodConfig
    reference: ReferenceMethodConfig


class IntegerLimits(StrictModel):
    max_n: PositiveInt
    reference_max_n: PositiveInt
    exact_timeout_ms: PositiveInt
    reference_timeout_ms: PositiveInt
    cancellation_grace_ms: NonNegativeInt
    control_connect_timeout_ms: PositiveInt
    control_response_timeout_ms: PositiveInt
    control_max_message_bytes: PositiveInt
    input_max_bytes: PositiveInt
    event_max_payload_bytes: PositiveInt
    worker_max_message_bytes: PositiveInt
    runner_log_max_bytes: PositiveInt
    runner_log_backup_count: NonNegativeInt


class PersistenceConfig(StrictModel):
    policy: Literal["normal", "debug"]
    persist_events: StrictBool


class ExecutionConfig(StrictModel):
    methods: MethodsConfig
    integer_limits: IntegerLimits
    persistence: PersistenceConfig
    counting_convention: Literal["undirected_paths_reverse_identified"]
