"""FastAPI application factory. The workflow worker remains a separate process."""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from snoc_agent.api.auth import Principal, current_principal
from snoc_agent.api.filters import DateRange, TimeWindow, parse_time_window
from snoc_agent.api.queries import DashboardQueries
from snoc_agent.api.schemas import (
    AuditPage,
    CategoryResponse,
    ComponentStatus,
    DashboardSummary,
    DQExecutive,
    DQPayload,
    HealthResponse,
    ModelSnapshot,
    OperationRow,
    RecentResponse,
    RequestPage,
    RequestRow,
    TrendResponse,
    WorkflowResponse,
    WorkflowStage,
)
from snoc_agent.config import Settings, load_settings
from snoc_agent.db.models import BusinessRequest
from snoc_agent.db.session import SessionFactory, create_engine_and_session

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def _safe_request_id(value: str) -> str:
    return value if REQUEST_ID_RE.fullmatch(value) else str(uuid.uuid4())


class RequestContextMiddleware:
    """Pure ASGI middleware avoids buffering request/response bodies."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        raw_headers = dict(scope.get("headers", []))
        supplied = raw_headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
        request_id = _safe_request_id(supplied)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-request-id", request_id.encode("ascii")),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _window(
    range: DateRange = DateRange.WEEK,
    start: datetime | None = None,
    end: datetime | None = None,
) -> TimeWindow:
    return parse_time_window(range, start=start, end=end)


async def _session(request: Request) -> AsyncIterator[Session]:
    factory: SessionFactory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _queries(
    request: Request,
    session: Session,
) -> DashboardQueries:
    return DashboardQueries(session, dry_run=request.app.state.settings.dry_run)


def _page(page: int, page_size: int) -> tuple[int, int]:
    if page < 1 or not 1 <= page_size <= 100:
        raise HTTPException(422, "page must be positive and page_size must be 1..100")
    return page, page_size


def _dq_payload(queries: DashboardQueries, kind: str) -> DQPayload:
    available, rows = queries.dq_rows(kind)
    return DQPayload(
        available=available,
        reason=None if available else f"public.dq_{kind.rstrip('s')}_summary is unavailable",
        data=rows,
    )


SESSION_DEPENDENCY = Depends(_session)
PRINCIPAL_DEPENDENCY = Depends(current_principal)
WINDOW_DEPENDENCY = Depends(_window)


async def _queries_dependency(
    request: Request,
    session: Session = SESSION_DEPENDENCY,
) -> DashboardQueries:
    return _queries(request, session)


QUERIES_DEPENDENCY = Depends(_queries_dependency)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings or load_settings()
    engine, session_factory = create_engine_and_session(
        configured.database_url,
        pool_size=configured.database_pool_size,
        max_overflow=configured.database_max_overflow,
    )

    app = FastAPI(
        title="SNOC safety-first agent API",
        version="1.0.0",
        docs_url="/docs" if configured.app_env.casefold() != "production" else None,
        redoc_url=None,
    )
    app.state.settings = configured
    app.state.engine = engine
    app.state.session_factory = session_factory
    if configured.cors_origin_set:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=sorted(configured.cors_origin_set),
            allow_credentials=False,
            allow_methods=["GET"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, _exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "database_unavailable",
                "message": "A required data source is unavailable.",
                "request_id": request.state.request_id,
            },
        )

    @app.get("/health/live", response_model=HealthResponse)
    async def live(request: Request) -> HealthResponse:
        return HealthResponse(
            status="ok",
            mode="demo" if configured.dry_run else "live",
            request_id=request.state.request_id,
        )

    @app.get("/health/ready", response_model=HealthResponse)
    async def ready(request: Request, session: Session = SESSION_DEPENDENCY) -> HealthResponse:
        checked = datetime.now(UTC)
        try:
            session.execute(text("SELECT 1"))
            component = ComponentStatus(name="database", status="ready", checked_at=checked)
            status = "ready"
        except SQLAlchemyError:
            session.rollback()
            component = ComponentStatus(
                name="database",
                status="unavailable",
                detail="database connection failed",
                checked_at=checked,
            )
            status = "unavailable"
        response = HealthResponse(
            status=status,
            mode="demo" if configured.dry_run else "live",
            request_id=request.state.request_id,
            components=[component],
        )
        if status != "ready":
            raise HTTPException(503, response.model_dump(mode="json"))
        return response

    @app.get("/api/snoc/health/components", response_model=HealthResponse)
    async def components(
        request: Request,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        session: Session = SESSION_DEPENDENCY,
    ) -> HealthResponse:
        now = datetime.now(UTC)
        statuses = []
        try:
            session.execute(text("SELECT 1"))
            statuses.append(ComponentStatus(name="database", status="ready", checked_at=now))
        except SQLAlchemyError:
            session.rollback()
            statuses.append(ComponentStatus(name="database", status="unavailable", checked_at=now))
        provider_status = (
            "demo"
            if configured.effective_llm_provider.value == "demo"
            else "configured"
            if configured.effective_analyzer_base_url and configured.effective_verifier_base_url
            else "unavailable"
        )
        statuses.extend(
            [
                ComponentStatus(name="analyzer", status=provider_status, checked_at=now),
                ComponentStatus(name="verifier", status=provider_status, checked_at=now),
                ComponentStatus(
                    name="business_api",
                    status=(
                        "demo"
                        if configured.dry_run
                        else "configured"
                        if configured.business_api_base_url
                        else "unavailable"
                    ),
                    checked_at=now,
                ),
            ]
        )
        overall = "ready" if all(item.status != "unavailable" for item in statuses) else "degraded"
        return HealthResponse(
            status=overall,
            mode="demo" if configured.dry_run else "live",
            request_id=request.state.request_id,
            components=statuses,
        )

    @app.get("/api/snoc/dashboard/summary", response_model=DashboardSummary)
    async def summary(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> DashboardSummary:
        return queries.summary(window)

    @app.get("/api/snoc/dashboard/trends", response_model=TrendResponse)
    async def trends(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> TrendResponse:
        granularity, data = queries.trends(window)
        return TrendResponse(range=window.range.value, granularity=granularity, data=data)

    @app.get("/api/snoc/dashboard/intents", response_model=CategoryResponse)
    async def intents(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> CategoryResponse:
        return CategoryResponse(
            range=window.range.value,
            data=queries.category_counts(window, outcomes=False),
        )

    @app.get("/api/snoc/dashboard/outcomes", response_model=CategoryResponse)
    async def outcomes(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> CategoryResponse:
        return CategoryResponse(
            range=window.range.value,
            data=queries.category_counts(window, outcomes=True),
        )

    @app.get("/api/snoc/dashboard/recent", response_model=RecentResponse)
    async def recent(
        window: TimeWindow = WINDOW_DEPENDENCY,
        limit: int = Query(25, ge=1, le=100),
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> RecentResponse:
        return RecentResponse(range=window.range.value, items=queries.recent(window, limit))

    @app.get("/api/snoc/requests", response_model=RequestPage)
    async def requests(
        page: int = 1,
        page_size: int = 25,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> RequestPage:
        page, page_size = _page(page, page_size)
        return queries.requests(page=page, page_size=page_size)

    @app.get("/api/snoc/requests/{request_id}", response_model=RequestRow)
    async def request_detail(
        request_id: uuid.UUID,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        session: Session = SESSION_DEPENDENCY,
    ) -> RequestRow:
        request = session.get(BusinessRequest, request_id)
        if request is None:
            raise HTTPException(404, "request not found")
        count = len(request.operations)
        return RequestRow(
            request_id=str(request.id),
            public_reference=request.public_reference,
            created_at=request.created_at,
            status=request.status,
            request_kind=request.request_kind,
            operation_count=count,
            escalation_reason=request.escalation_reason,
        )

    @app.get("/api/snoc/operations/{operation_id}", response_model=OperationRow)
    async def operation_detail(
        operation_id: uuid.UUID,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> OperationRow:
        operation = queries.operation(operation_id)
        if operation is None:
            raise HTTPException(404, "operation not found")
        return operation

    @app.get("/api/snoc/manual-review", response_model=RequestPage)
    @app.get("/api/snoc/escalations", response_model=RequestPage)
    async def manual_review(
        page: int = 1,
        page_size: int = 25,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> RequestPage:
        page, page_size = _page(page, page_size)
        return queries.requests(page=page, page_size=page_size, manual_only=True)

    @app.get("/api/snoc/audit/events", response_model=AuditPage)
    async def audit_events(
        page: int = 1,
        page_size: int = 25,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> AuditPage:
        page, page_size = _page(page, page_size)
        return queries.audit(page=page, page_size=page_size)

    @app.get("/api/snoc/model-runs", response_model=CategoryResponse)
    async def model_runs(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> CategoryResponse:
        return CategoryResponse(range=window.range.value, data=queries.model_run_counts(window))

    @app.get("/api/snoc/operations/metrics", response_model=DashboardSummary)
    async def operation_metrics(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> DashboardSummary:
        return queries.summary(window)

    @app.get("/api/snoc/operations/by-action", response_model=CategoryResponse)
    async def operations_by_action(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> CategoryResponse:
        return CategoryResponse(
            range=window.range.value,
            data=queries.category_counts(window, outcomes=False),
        )

    @app.get("/api/snoc/operations/errors", response_model=CategoryResponse)
    async def operation_errors(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> CategoryResponse:
        return CategoryResponse(
            range=window.range.value,
            data=queries.escalation_counts(window),
        )

    @app.get("/api/snoc/operations/latency", response_model=TrendResponse)
    async def operation_latency(
        window: TimeWindow = WINDOW_DEPENDENCY,
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> TrendResponse:
        granularity, data = queries.trends(window)
        return TrendResponse(range=window.range.value, granularity=granularity, data=data)

    @app.get("/api/snoc/dq/executive", response_model=DQExecutive)
    @app.get("/api/snoc/dq/runs/latest", response_model=DQExecutive)
    async def dq_executive(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> DQExecutive:
        payload = queries.dq_executive()
        if payload is None:
            raise HTTPException(503, "public.dq_executive_summary is unavailable")
        return payload

    @app.get("/api/snoc/dq/dimensions", response_model=DQPayload)
    async def dq_dimensions(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> DQPayload:
        return _dq_payload(queries, "dimensions")

    @app.get("/api/snoc/dq/tables", response_model=DQPayload)
    async def dq_tables(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> DQPayload:
        return _dq_payload(queries, "tables")

    @app.get("/api/snoc/dq/sources", response_model=DQPayload)
    async def dq_sources(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> DQPayload:
        return _dq_payload(queries, "sources")

    @app.get("/api/snoc/dq/columns", response_model=DQPayload)
    async def dq_columns(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> DQPayload:
        return _dq_payload(queries, "columns")

    @app.get("/api/snoc/dq/rules", response_model=DQPayload)
    async def dq_rules(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> DQPayload:
        return _dq_payload(queries, "rules")

    @app.get("/api/snoc/model/snapshot", response_model=ModelSnapshot)
    @app.get("/api/snoc/model/confusion-matrix", response_model=ModelSnapshot)
    @app.get("/api/snoc/model/class-metrics", response_model=ModelSnapshot)
    async def model_snapshot(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
    ) -> ModelSnapshot:
        return ModelSnapshot(
            available=False,
            label="Model evaluation snapshot",
            reason="No versioned model evaluation artifact is configured for this service.",
        )

    @app.get("/api/snoc/workflow/health", response_model=WorkflowResponse)
    @app.get("/api/snoc/workflow/stages", response_model=WorkflowResponse)
    async def workflow(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
        queries: DashboardQueries = QUERIES_DEPENDENCY,
    ) -> WorkflowResponse:
        window = parse_time_window(DateRange.WEEK)
        summary = queries.summary(window)
        total = summary.operational.total_requests
        stages = [
            WorkflowStage(
                name="IMAP email reception",
                status="unavailable" if not configured.imap_host else "configured",
                processed_count=total,
                error_count=summary.operational.failed,
                average_duration_ms=None,
                last_successful_event=None,
                description="Raw MIME is persisted before consequential processing.",
            ),
            WorkflowStage(
                name="Active Directory / LDAP whitelist",
                status="configured" if configured.authorized_sender_set else "unavailable",
                processed_count=total,
                error_count=summary.operational.rejected,
                average_duration_ms=None,
                last_successful_event=None,
                description="Authorization is deterministic and precedes model inference.",
            ),
            WorkflowStage(
                name="Local AI inference and structured extraction",
                status=(
                    "demo" if configured.effective_llm_provider.value == "demo" else "configured"
                ),
                processed_count=total,
                error_count=None,
                average_duration_ms=None,
                last_successful_event=None,
                description="Analyzer and independent verifier emit schema-validated JSON.",
            ),
            WorkflowStage(
                name="Deterministic routing and SNOC API",
                status="demo" if configured.dry_run else "configured",
                processed_count=summary.operational.auto_resolved,
                error_count=summary.operational.failed,
                average_duration_ms=None,
                last_successful_event=None,
                description="Fixed adapters enforce validation, revision, and idempotency.",
            ),
            WorkflowStage(
                name="SMTP response outbox",
                status="demo" if configured.dry_run else "configured",
                processed_count=None,
                error_count=None,
                average_duration_ms=None,
                last_successful_event=None,
                description="Transactional outbox retries delivery without rerunning actions.",
            ),
            WorkflowStage(
                name="Audit and observability",
                status="ready",
                processed_count=total,
                error_count=None,
                average_duration_ms=summary.operational.average_processing_ms,
                last_successful_event=None,
                description="State transitions, model runs, decisions, and executions are durable.",
            ),
        ]
        return WorkflowResponse(mode="demo" if configured.dry_run else "live", stages=stages)

    @app.get("/api/snoc/business-api/health", response_model=ComponentStatus)
    async def business_health(
        _principal: Principal = PRINCIPAL_DEPENDENCY,
    ) -> ComponentStatus:
        return ComponentStatus(
            name="business_api",
            status=(
                "demo"
                if configured.dry_run
                else "configured"
                if configured.business_api_base_url
                else "unavailable"
            ),
            detail="No operational request is sent by this health endpoint.",
            checked_at=datetime.now(UTC),
        )

    return app
