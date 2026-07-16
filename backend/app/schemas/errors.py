from typing import Any, Literal

from pydantic import BaseModel

ErrorCode = Literal[
    "blocked_captcha",
    "blocked_other",
    "cooldown_skipped",
    "job_timeout",
    "validation_error",
    "job_not_found",
    "run_not_found",
    "lead_not_found",
    "queue_unavailable",
]


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    retryable: bool
    retry_after_seconds: int | None = None
    details: dict[str, Any] | None = None


class ApiError(Exception):
    """Raised by route handlers to produce a `{"error": ErrorDetail}` response
    body via the exception handler registered in app/main.py, instead of
    FastAPI's default bare `{"detail": "..."}`."""

    def __init__(self, status_code: int, error: ErrorDetail) -> None:
        self.status_code = status_code
        self.error = error
        super().__init__(error.message)
