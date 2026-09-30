"""Uniform API errors: every failure returns {"error": {"code", "message"}}."""
from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, extra: dict | None = None):
        self.status_code, self.code, self.message, self.extra = status_code, code, message, extra or {}
        super().__init__(message)


def not_found(what="Resource"):
    return AppError(404, "NOT_FOUND", f"{what} not found")


def forbidden(msg="You do not have permission to do this"):
    return AppError(403, "FORBIDDEN", msg)


def validation(msg):
    return AppError(422, "VALIDATION_ERROR", msg)


async def app_error_handler(_: Request, exc: AppError):
    body = {"error": {"code": exc.code, "message": exc.message, **exc.extra}}
    return JSONResponse(status_code=exc.status_code, content=body)
