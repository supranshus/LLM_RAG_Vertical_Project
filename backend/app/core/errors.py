import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import request_id_var

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base for errors the API turns into a JSON error response."""

    code = "internal_error"
    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UnauthorizedError(AppError):
    code = "unauthorized"
    status_code = 401


class ForbiddenError(AppError):
    code = "forbidden"
    status_code = 403


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class FileTooLargeError(AppError):
    code = "file_too_large"
    status_code = 413


class UnsupportedFileTypeError(AppError):
    code = "unsupported_file_type"
    status_code = 415


class LLMRateLimitError(AppError):
    code = "llm_rate_limited"
    status_code = 429


class LLMUnavailableError(AppError):
    code = "llm_unavailable"
    status_code = 502


class VectorStoreUnavailableError(AppError):
    code = "vector_store_unavailable"
    status_code = 502


class LLMTimeoutError(AppError):
    code = "llm_timeout"
    status_code = 504


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "request_id": request_id_var.get()}}
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.warning("%s: %s", exc.code, exc.message)
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        parts = []
        for err in exc.errors():
            location = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query"))
            message = err.get("msg", "invalid")
            parts.append(f"{location}: {message}" if location else message)
        return error_response(422, "validation_error", "; ".join(parts) or "Invalid request")

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(500, "internal_error", "Internal server error")
