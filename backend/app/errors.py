"""Controlled API error contract (SRS 15.6, 19)."""
import logging
import uuid

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("crimemind")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict | None = None):
        self.status, self.code, self.message, self.fields = status, code, message, fields


def body(code: str, message: str, request_id: str, fields: dict | None = None) -> dict:
    out = {"error": {"code": code, "message": message, "request_id": request_id}}
    if fields:
        out["error"]["fields"] = fields
    return out


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id_mw(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        response = await call_next(request)
        response.headers["x-request-id"] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def _api(request: Request, exc: ApiError):
        return JSONResponse(body(exc.code, exc.message, request.state.request_id, exc.fields), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _val(request: Request, exc: RequestValidationError):
        fields = {".".join(str(p) for p in e["loc"][1:]) or "body": e["msg"] for e in exc.errors()}
        return JSONResponse(body("VALIDATION_ERROR", "Malformed request.", request.state.request_id, fields), status_code=422)

    @app.exception_handler(psycopg.OperationalError)
    async def _dbdown(request: Request, exc: psycopg.OperationalError):
        log.error("database unavailable rid=%s class=%s", request.state.request_id, type(exc).__name__)
        return JSONResponse(body("DATABASE_UNAVAILABLE", "The database is unavailable. No result was produced.",
                                 request.state.request_id), status_code=503)

    @app.exception_handler(Exception)
    async def _any(request: Request, exc: Exception):
        # Errors are system states, never evidence; no internals or record content leak (SRS 19.1, 19.4).
        log.error("unhandled rid=%s class=%s", request.state.request_id, type(exc).__name__)
        return JSONResponse(body("INTERNAL_ERROR", "An internal error occurred. No result was produced.",
                                 request.state.request_id), status_code=500)
