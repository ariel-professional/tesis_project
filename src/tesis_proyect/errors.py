"""Internal failures carrying stable public error codes."""

from tesis_proyect.models.enums import ErrorCode


class OperationalError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
