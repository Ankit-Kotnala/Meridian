"""HTTP middleware that establishes a safe per-request logging context."""

import re
from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, clear_contextvars

from rezumi_api.problems import problem_response

REQUEST_ID_HEADER = "X-Request-ID"
TRACE_ID_HEADER = "X-Trace-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_TRACEPARENT = re.compile(
    r"^(?P<version>[0-9a-f]{2})-"
    r"(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<parent_id>[0-9a-f]{16})-"
    r"(?P<flags>[0-9a-f]{2})$"
)
logger = structlog.get_logger(__name__)

_API_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-Permitted-Cross-Domain-Policies": "none",
}
_HSTS_HEADER = "max-age=31536000"


class SecurityResponseHeadersMiddleware:
    """Apply a conservative browser and cache policy to every API response."""

    def __init__(self, app: ASGIApp, *, enable_hsts: bool) -> None:
        self._app = app
        self._enable_hsts = enable_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def secure_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _API_SECURITY_HEADERS.items():
                    headers[name] = value
                if self._enable_hsts:
                    headers["Strict-Transport-Security"] = _HSTS_HEADER
            await send(message)

        await self._app(scope, receive, secure_send)


class RequestBodyTooLarge(Exception):
    """Internal control flow raised before an oversized request reaches a handler."""


class RequestBodyLimitMiddleware:
    """Enforce declared and streamed byte limits without buffering request bodies."""

    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if self._declared_size(scope) > self._max_body_bytes:
            await self._reject(scope, receive, send)
            return

        received_bytes = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self._max_body_bytes:
                    raise RequestBodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self._app(scope, limited_receive, tracked_send)
        except RequestBodyTooLarge:
            if response_started:
                raise
            await self._reject(scope, receive, send)

    @staticmethod
    def _declared_size(scope: Scope) -> int:
        for name, value in scope.get("headers", ()):
            if name.lower() != b"content-length":
                continue
            try:
                return max(0, int(value.decode("ascii")))
            except (UnicodeDecodeError, ValueError):
                return 0
        return 0

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope)
        response = problem_response(
            request,
            status_code=413,
            code="payload_too_large",
            title="Payload too large",
            detail="The request body exceeds the allowed size.",
        )
        await response(scope, receive, send)


def _request_id(candidate: str | None) -> str:
    if candidate is not None and _SAFE_REQUEST_ID.fullmatch(candidate):
        return candidate
    return str(uuid4())


def _trace_id(traceparent: str | None) -> str:
    """Extract a valid W3C trace ID or start a new trace context."""
    if traceparent is not None:
        match = _TRACEPARENT.fullmatch(traceparent)
        if match is not None:
            version = match.group("version")
            trace_id = match.group("trace_id")
            parent_id = match.group("parent_id")
            if version != "ff" and trace_id != "0" * 32 and parent_id != "0" * 16:
                return trace_id
    return uuid4().hex


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path.startswith("/") else "unmatched"


def install_request_context_middleware(app: FastAPI) -> None:
    """Add correlation IDs without logging query strings, headers, or bodies."""

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        clear_contextvars()
        request_id = _request_id(request.headers.get(REQUEST_ID_HEADER))
        trace_id = _trace_id(request.headers.get("traceparent"))
        bind_contextvars(request_id=request_id, trace_id=trace_id)
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            # Exception messages and tracebacks can contain database parameters or
            # provider payloads. Log only allowlisted request metadata and the
            # exception class at this PII-bearing HTTP boundary. Convert the error
            # here instead of re-raising it: Uvicorn's outer error logger otherwise
            # renders the original traceback and exception message.
            logger.error(
                "http_request_failed",
                http_method=request.method,
                http_route=_route_template(request),
                error_type=type(exc).__name__,
            )
            response = problem_response(
                request,
                status_code=500,
                code="internal_error",
                title="Request could not be completed",
                detail="The service could not complete this request.",
            )
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers[TRACE_ID_HEADER] = trace_id
            clear_contextvars()
            return response

        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers[TRACE_ID_HEADER] = trace_id
        logger.info(
            "http_request_completed",
            http_method=request.method,
            http_route=_route_template(request),
            http_status=response.status_code,
            duration_ms=duration_ms,
        )
        clear_contextvars()
        return response
