import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger("http")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.correlation_id = cid
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        response.headers["X-Request-ID"] = rid
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            correlation_id=cid,
            request_id=rid,
        )
        return response


def configure_otel(app) -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        resource = Resource.create({"service.name": "mlr-ruleops"})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        return
