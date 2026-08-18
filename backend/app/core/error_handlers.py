"""Translation of domain errors into the app's `{"error": ErrorDetail}` body.

Extracted from `main.py` so anything that builds an app — including tests that
exercise a single router in isolation — renders errors identically. A handler
registered in only one place is a handler that silently doesn't apply in the
other.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.schemas.errors import ApiError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.error.model_dump()})
