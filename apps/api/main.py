import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.exceptions import HTTPException as StarletteHTTPException
from temporalio.client import Client

from apps.api import runtime as runtime_api
from apps.retrieval.service import RetrievalService
from packages.auth.context import authenticated_principal
from packages.auth.identity import IdentityVerifier, Principal, Verifier
from packages.config.settings import Settings
from packages.model_clients.embeddings import DeterministicEmbeddingProvider
from packages.observability.logging import configure_logging
from packages.observability.metrics import Metrics
from packages.observability.sentry import capture_exception, init_sentry
from packages.persistence.models import TENANT_TABLES
from packages.usage.budget import BudgetService


def sanitize_http_span(span: Span, _scope: dict) -> None:
    """Drop query strings before spans are exported; they may contain secrets or PII."""
    if not span or not span.is_recording():
        return
    attributes = getattr(span, "attributes", {})
    for key in ("http.url", "http.target", "url.full"):
        value = attributes.get(key)
        if isinstance(value, str):
            span.set_attribute(key, value.split("?", 1)[0])
    if "url.query" in attributes:
        span.set_attribute("url.query", "[REDACTED]")


def create_app(
    settings: Settings | None = None,
    *,
    verifier: Verifier | None = None,
    tracer_provider: TracerProvider | None = None,
    run_dispatcher: runtime_api.RunDispatcher | None = None,
    retrieval_service: runtime_api.RetrievalApi | None = None,
    budget_service: runtime_api.BudgetApi | None = None,
) -> FastAPI:
    settings = settings or Settings()
    logger = configure_logging()
    init_sentry(settings)
    own_provider = tracer_provider is None
    if settings.otel_enabled and tracer_provider is None:
        tracer_provider = TracerProvider(
            resource=Resource.create({"service.name": "agent-platform-api"})
        )
        if settings.otel_traces_endpoint:
            exporter = OTLPSpanExporter(endpoint=settings.otel_traces_endpoint, timeout=3)
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    if verifier is None and all(
        (settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)
    ):
        assert settings.oidc_issuer and settings.oidc_audience and settings.oidc_jwks_url
        verifier = IdentityVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            jwks_url=settings.oidc_jwks_url,
            tenant_claim=settings.oidc_tenant_claim,
            cache_ttl_seconds=settings.oidc_jwks_cache_ttl_seconds,
            refresh_min_interval_seconds=settings.oidc_jwks_refresh_min_interval_seconds,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = (
            create_async_engine(settings.database_url, pool_pre_ping=True)
            if settings.database_url
            else None
        )
        app.state.run_dispatcher = run_dispatcher
        app.state.retrieval = retrieval_service
        app.state.budget = budget_service
        app.state.temporal_client = None
        if app.state.engine is not None:
            if app.state.retrieval is None:
                app.state.retrieval = RetrievalService(
                    app.state.engine, DeterministicEmbeddingProvider()
                )
            if app.state.budget is None:
                app.state.budget = BudgetService(app.state.engine)
            if app.state.run_dispatcher is None and settings.temporal_address:
                try:
                    app.state.temporal_client = await Client.connect(
                        settings.temporal_address, namespace=settings.temporal_namespace
                    )
                except Exception:
                    logger.exception("Temporal unavailable; run dispatch is disabled")
                else:
                    app.state.run_dispatcher = runtime_api.TemporalRunDispatcher(
                        app.state.temporal_client,
                        settings.temporal_task_queue or "agent-runs",
                    )
        logger.info("platform API started")
        try:
            yield
        finally:
            if app.state.engine is not None:
                await app.state.engine.dispose()
            if own_provider and tracer_provider is not None:
                tracer_provider.shutdown()
            logger.info("platform API stopped")

    app = FastAPI(title="Agent Platform API", version="0.1.0", lifespan=lifespan)
    app.state.verifier = verifier
    metrics = Metrics()
    app.state.metrics = metrics

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={"error": {"code": f"http_{exc.status_code}", "message": str(exc.detail)}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Invalid request"}},
        )

    @app.middleware("http")
    async def unexpected_error(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            capture_exception(exc)
            logger.error("unexpected API failure")
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "internal_error", "message": "Internal server error"}},
            )

    @app.middleware("http")
    async def observe_requests(request: Request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", None)
        if path is None or response.status_code == 404:
            path = "unmatched"
        metrics.increment(
            "platform_http_requests_total",
            {
                "method": request.method,
                "path": path,
                "status": str(response.status_code),
            },
        )
        return response

    @app.get("/metrics", include_in_schema=False, tags=["health"])
    async def metrics_view() -> PlainTextResponse:
        return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request) -> dict[str, str]:
        engine = request.app.state.engine
        if engine is None:
            raise HTTPException(503, "Database unavailable")
        if request.app.state.verifier is None:
            raise HTTPException(503, "Authentication unavailable")
        try:
            async with asyncio.timeout(3):
                async with engine.connect() as conn:
                    role = (
                        await conn.execute(
                            text(
                                "SELECT rolsuper, rolbypassrls FROM pg_roles "
                                "WHERE rolname = current_user"
                            )
                        )
                    ).one()
                    if role.rolsuper or role.rolbypassrls:
                        raise ValueError("Unsafe database role")
                    placeholders = ", ".join(f":t{index}" for index in range(len(TENANT_TABLES)))
                    table_params = {f"t{index}": name for index, name in enumerate(TENANT_TABLES)}
                    safe_tables = (
                        await conn.execute(
                            text(f"""SELECT count(*) FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = current_schema() AND c.relname IN ({placeholders})
                          AND c.relrowsecurity AND c.relforcerowsecurity
                          AND NOT pg_has_role(current_user, c.relowner, 'MEMBER')
                          AND EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid
                                      AND p.polname = 'tenant_isolation' AND p.polqual IS NOT NULL
                                      AND p.polwithcheck IS NOT NULL)"""),
                            table_params,
                        )
                    ).scalar_one()
                    if safe_tables != len(TENANT_TABLES):
                        raise ValueError("Database isolation is not configured safely")
                    await conn.execute(text("SELECT 1 FROM tenants LIMIT 1"))
        except Exception as exc:
            raise HTTPException(503, "Database unavailable or unsafe") from exc
        return {"status": "ok"}

    router = APIRouter(prefix="/v1", dependencies=[Depends(authenticated_principal)])

    @router.get("/session", tags=["identity"])
    async def session(
        principal: Annotated[Principal, Depends(authenticated_principal)],
    ) -> dict[str, str]:
        return {"subject": principal.subject, "tenant_id": str(principal.tenant_id)}

    app.include_router(router)
    app.include_router(
        runtime_api.router,
        prefix="/v1",
        dependencies=[Depends(authenticated_principal)],
    )
    if settings.otel_enabled:
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=tracer_provider,
            server_request_hook=sanitize_http_span,
            excluded_urls="health/live,health/ready,metrics",
            http_capture_headers_server_request=["^$"],
            http_capture_headers_server_response=["^$"],
            http_capture_headers_sanitize_fields=[".*"],
        )
    return app


app = create_app()
