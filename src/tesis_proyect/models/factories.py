# from tesis_proyect.models.common import StructuredError
# from tesis_proyect.models.enums import DOMAIN_ERROR_CODES, ErrorCode, StageId


# def structured_error(
#     code: ErrorCode,
#     message: str,
#     *,
#     stage: StageId | None = None,
#     recoverable: bool | None = None,
# ) -> StructuredError:
#     """Build a contract-valid error with the canonical code mapping."""

#     if recoverable is None:
#         recoverable = code in {
#             ErrorCode.STAGE_TIMEOUT,
#             ErrorCode.RUNNER_INTERRUPTED,
#             ErrorCode.RUN_ALREADY_ACTIVE,
#             ErrorCode.RUN_CONTROL_UNAVAILABLE,
#             ErrorCode.RUN_LOCK_UNAVAILABLE,
#         }
#     return StructuredError(
#         schema_version="1.0.0",
#         code=code,
#         domain_error_code=DOMAIN_ERROR_CODES.get(code),
#         message=message[:512] or "Operation failed.",
#         recoverable=recoverable,
#         details={},
#         stage=stage,
#     )

from typing import Any

from tesis_proyect.models.common import StructuredError
from tesis_proyect.models.enums import DOMAIN_ERROR_CODES, ErrorCode, StageId


def structured_error(
    code: ErrorCode,
    message: str,
    *,
    stage: StageId | None = None,
    recoverable: bool | None = None,
    details: dict[str, Any] | None = None,
) -> StructuredError:
    """Build a contract-valid error with the canonical code mapping."""

    if recoverable is None:
        recoverable = code in {
            ErrorCode.STAGE_TIMEOUT,
            ErrorCode.RUNNER_INTERRUPTED,
            ErrorCode.RUN_ALREADY_ACTIVE,
            ErrorCode.RUN_CONTROL_UNAVAILABLE,
            ErrorCode.RUN_LOCK_UNAVAILABLE,
        }

    return StructuredError(
        schema_version="1.0.0",
        code=code,
        domain_error_code=DOMAIN_ERROR_CODES.get(code),
        message=message[:512] or "Operation failed.",
        recoverable=recoverable,
        details=details or {},
        stage=stage,
    )
