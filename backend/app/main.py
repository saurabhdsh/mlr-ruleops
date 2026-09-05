from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import approvals, auth, configurations, deployments, misc, proposals, rules, tickets
from app.core.config import settings
from app.core.errors import RuleOpsError
from app.core.logging import configure_logging
from app.security.headers import SecurityHeadersMiddleware
from app.telemetry.middleware import CorrelationIdMiddleware, configure_otel

configure_logging()

app = FastAPI(title=settings.app_name, version="1.0.0")
configure_otel(app)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")
app.include_router(configurations.router, prefix="/api/v1")
app.include_router(proposals.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(deployments.router, prefix="/api/v1")
app.include_router(misc.router, prefix="/api/v1")
app.include_router(misc.router)  # /health /ready at root too


@app.exception_handler(RuleOpsError)
async def ruleops_error(request: Request, exc: RuleOpsError) -> JSONResponse:
    cid = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "context": exc.context,
            "retryable": exc.retryable,
            "correlation_id": cid,
        },
    )


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    cid = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": str(exc)[:400] or "Unexpected server error",
            "context": {"path": request.url.path},
            "retryable": True,
            "correlation_id": cid,
        },
    )


@app.on_event("startup")
def startup() -> None:
    if settings.database_url.startswith("sqlite"):
        from app.db.base import Base
        from app.db.session import engine
        from app import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        from app.db.session import SessionLocal
        from app.db.seed import seed_if_empty

        db = SessionLocal()
        try:
            seed_if_empty(db)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
