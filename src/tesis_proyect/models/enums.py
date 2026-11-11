from enum import StrEnum


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class StageTerminalStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class RunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComparisonStatus(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_APPLICABLE = "not_applicable"


class PersistencePolicy(StrEnum):
    NORMAL = "normal"
    DEBUG = "debug"


class CountingConvention(StrEnum):
    UNDIRECTED_PATHS_REVERSE_IDENTIFIED = "undirected_paths_reverse_identified"


class StageId(StrEnum):
    DEFINE_EXPERIMENT = "define_experiment"
    LOAD_OR_GENERATE_INSTANCE = "load_or_generate_instance"
    VALIDATE_INSTANCE_EDGES = "validate_instance_edges"
    VALIDATE_LINEAR_FOREST = "validate_linear_forest"
    ANALYZE_STRUCTURE = "analyze_structure"
    RUN_EXACT_METHOD = "run_exact_method"
    RUN_REFERENCE_METHOD = "run_reference_method"
    COMPARE_RESULTS = "compare_results"
    COLLECT_METRICS = "collect_metrics"
    EXPORT_REPORT = "export_report"


STAGE_ORDER: tuple[StageId, ...] = tuple(StageId)


class ErrorCode(StrEnum):
    MALFORMED_EDGE = "MALFORMED_EDGE"
    LOOP_EDGE = "LOOP_EDGE"
    DUPLICATE_EDGE = "DUPLICATE_EDGE"
    VERTEX_OUT_OF_RANGE = "VERTEX_OUT_OF_RANGE"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    MAX_DEGREE_EXCEEDED = "MAX_DEGREE_EXCEEDED"
    BRUTE_FORCE_LIMIT_EXCEEDED = "BRUTE_FORCE_LIMIT_EXCEEDED"
    EXACT_ENGINE_NOT_AVAILABLE = "EXACT_ENGINE_NOT_AVAILABLE"
    STAGE_TIMEOUT = "STAGE_TIMEOUT"
    RUN_CANCELLED = "RUN_CANCELLED"
    RUN_ALREADY_ACTIVE = "RUN_ALREADY_ACTIVE"
    RUN_LOCK_UNAVAILABLE = "RUN_LOCK_UNAVAILABLE"
    RUN_CONTROL_UNAVAILABLE = "RUN_CONTROL_UNAVAILABLE"
    RUNNER_INTERRUPTED = "RUNNER_INTERRUPTED"
    USAGE_ERROR = "USAGE_ERROR"
    CONFIG_INVALID = "CONFIG_INVALID"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    VERSION_UNSUPPORTED = "VERSION_UNSUPPORTED"
    NOT_FOUND = "NOT_FOUND"
    ID_COLLISION = "ID_COLLISION"
    PATH_OUTSIDE_WORKSPACE = "PATH_OUTSIDE_WORKSPACE"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    INPUT_BOM_FORBIDDEN = "INPUT_BOM_FORBIDDEN"
    INPUT_DECODE_FAILED = "INPUT_DECODE_FAILED"
    INPUT_JSON_INVALID = "INPUT_JSON_INVALID"
    INTEGRITY_ERROR = "INTEGRITY_ERROR"
    RUN_STATE_INVALID = "RUN_STATE_INVALID"
    WORKER_MESSAGE_TOO_LARGE = "WORKER_MESSAGE_TOO_LARGE"
    WORKER_PROTOCOL_ERROR = "WORKER_PROTOCOL_ERROR"
    WORKER_TERMINATED = "WORKER_TERMINATED"
    REPORT_UNAVAILABLE = "REPORT_UNAVAILABLE"
    IO_ERROR = "IO_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


DOMAIN_ERROR_CODES: dict[ErrorCode, int] = {
    code: number
    for number, code in enumerate(
        (
            ErrorCode.MALFORMED_EDGE,
            ErrorCode.LOOP_EDGE,
            ErrorCode.DUPLICATE_EDGE,
            ErrorCode.VERTEX_OUT_OF_RANGE,
            ErrorCode.CYCLE_DETECTED,
            ErrorCode.MAX_DEGREE_EXCEEDED,
            ErrorCode.BRUTE_FORCE_LIMIT_EXCEEDED,
            ErrorCode.EXACT_ENGINE_NOT_AVAILABLE,
            ErrorCode.STAGE_TIMEOUT,
            ErrorCode.RUN_CANCELLED,
            ErrorCode.RUN_ALREADY_ACTIVE,
            ErrorCode.RUN_LOCK_UNAVAILABLE,
            ErrorCode.RUN_CONTROL_UNAVAILABLE,
            ErrorCode.RUNNER_INTERRUPTED,
        ),
        start=1,
    )
}
