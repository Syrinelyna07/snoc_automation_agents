"""Read-only, parameterized query service for dashboard and CACTUV views."""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from snoc_agent.api.filters import TimeWindow
from snoc_agent.api.schemas import (
    AuditEvent,
    AuditPage,
    CategoryCount,
    DashboardSummary,
    DQColumn,
    DQDimension,
    DQExecutive,
    DQRule,
    DQSource,
    DQTable,
    OperationalSummary,
    OperationRow,
    PageMeta,
    RecentRequest,
    RequestPage,
    RequestRow,
    TrendPoint,
)
from snoc_agent.db.models import (
    BusinessRequest,
    EmailMessage,
    Escalation,
    Execution,
    ModelRun,
    Operation,
    ValidationDecision,
)
from snoc_agent.domain.enums import Direction, ExecutionStatus, OperationStatus, ProcessingStatus

DQModel = TypeVar("DQModel", bound=BaseModel)
DQRow = DQDimension | DQTable | DQSource | DQColumn | DQRule

_DQ_SELECTS: dict[str, tuple[str, str, type[BaseModel]]] = {
    "dimensions": (
        "public.dq_dimension_summary",
        "dimension, dimension_score, total_rules, passed_rules, failed_rules, "
        "error_rules, failed_checks",
        DQDimension,
    ),
    "tables": (
        "public.dq_table_summary",
        "table_name, source_variant, table_quality_score, total_rules, passed_rules, "
        "failed_rules, error_rules, failed_checks",
        DQTable,
    ),
    "sources": (
        "public.dq_source_summary",
        "source_variant, source_quality_score, total_rules, passed_rules, failed_rules, "
        "error_rules, failed_checks",
        DQSource,
    ),
    "columns": (
        "public.dq_column_summary",
        "table_name, source_variant, column_name, total_rules, passed_rules, failed_rules, "
        "error_rules, total_records_checked, total_passed_records, total_failed_records, "
        "column_dq_score",
        DQColumn,
    ),
    "rules": (
        "public.dq_rule_details",
        "run_id, executed_at, project_name, rule_id, table_name, column_name, dimension, "
        "severity, failed_rows, passed_rows, total_rows, score, status, comparison_score, "
        "error_message, rule_family_id, source_variant",
        DQRule,
    ),
}


@dataclass(slots=True)
class _TrendBucket:
    received: int = 0
    auto: int = 0
    escalated: int = 0
    failed: int = 0
    times: list[float] = field(default_factory=list)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _duration_ms(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return max(0.0, (_utc(end) - _utc(start)).total_seconds() * 1000)


def _confidence(operation: Operation) -> float | None:
    for payload in (operation.analyzer_confidence, operation.verifier_confidence):
        for key in ("raw_model_confidence", "raw_confidence", "confidence"):
            value = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(value, int | float) and not isinstance(value, bool):
                numeric = float(value)
                if math.isfinite(numeric) and 0 <= numeric <= 1:
                    return numeric
    return None


def _intent(action: str) -> str:
    return {
        "account_unblock": "Locked",
        "otp_number_change": "OTP",
        "vpn_access": "VPN",
        "password_reset": "Reset",
    }.get(action, "Irrelevant")


class DashboardQueries:
    def __init__(self, session: Session, *, dry_run: bool) -> None:
        self.session = session
        self.dry_run = dry_run

    def dq_executive(self) -> DQExecutive | None:
        try:
            row = (
                self.session.execute(
                    text(
                        "SELECT overall_quality_score, total_rules, passed_rules, failed_rules, "
                        "error_rules, failed_checks, critical_fatal_open_issues, tables_monitored, "
                        "last_execution_at FROM public.dq_executive_summary LIMIT 1"
                    )
                )
                .mappings()
                .first()
            )
        except SQLAlchemyError:
            self.session.rollback()
            return None
        return DQExecutive.model_validate(dict(row)) if row else None

    def dq_rows(self, kind: str) -> tuple[bool, list[DQRow]]:
        view, columns, model = _DQ_SELECTS[kind]
        order = {
            "dimensions": "dimension",
            "tables": "table_quality_score ASC NULLS FIRST, failed_checks DESC",
            "sources": "source_quality_score ASC NULLS FIRST",
            "columns": "column_dq_score ASC NULLS FIRST, total_failed_records DESC",
            "rules": "score ASC NULLS FIRST, failed_rows DESC",
        }[kind]
        try:
            rows = self.session.execute(
                text(f"SELECT {columns} FROM {view} ORDER BY {order}")
            ).mappings()
            parsed_rows = [model.model_validate(dict(row)) for row in rows]
            return True, [
                row
                for row in parsed_rows
                if isinstance(row, DQDimension | DQTable | DQSource | DQColumn | DQRule)
            ]
        except (SQLAlchemyError, ValueError):
            self.session.rollback()
            return False, []

    def summary(self, window: TimeWindow) -> DashboardSummary:
        emails = self.session.scalars(
            select(EmailMessage).where(
                EmailMessage.direction == Direction.INBOUND.value,
                EmailMessage.created_at >= window.start,
                EmailMessage.created_at <= window.end,
            )
        ).all()
        operations = self.session.scalars(
            select(Operation).where(
                Operation.created_at >= window.start,
                Operation.created_at <= window.end,
            )
        ).all()
        executions = self.session.scalars(
            select(Execution).where(
                Execution.created_at >= window.start,
                Execution.created_at <= window.end,
            )
        ).all()
        elapsed = [
            value
            for email in emails
            if (value := _duration_ms(email.created_at, email.updated_at)) is not None
        ]
        known = [operation for operation in operations if operation.action != "unknown"]
        eligible = [
            operation
            for operation in known
            if operation.final_decision in {"AUTO_EXECUTE", "ASK_FOR_INFORMATION"}
        ]
        dq = self.dq_executive()
        return DashboardSummary(
            range=window.range.value,
            generated_at=datetime.now(UTC),
            mode="demo" if self.dry_run else "live",
            operational=OperationalSummary(
                total_requests=len(emails),
                auto_resolved=sum(
                    execution.status == ExecutionStatus.SUCCEEDED.value for execution in executions
                ),
                in_progress=sum(
                    operation.status
                    in {
                        OperationStatus.NEW.value,
                        OperationStatus.NEEDS_INFORMATION.value,
                        OperationStatus.READY_FOR_VALIDATION.value,
                        OperationStatus.EXECUTING.value,
                    }
                    for operation in operations
                ),
                manual_review=sum(
                    operation.status == OperationStatus.ESCALATED.value for operation in operations
                ),
                rejected=sum(email.authorization_allowed is False for email in emails),
                failed=sum(
                    execution.status
                    in {ExecutionStatus.FAILED.value, ExecutionStatus.UNKNOWN.value}
                    for execution in executions
                ),
                average_processing_ms=sum(elapsed) / len(elapsed) if elapsed else None,
                readiness_rate=(100 * len(eligible) / len(known)) if known else None,
            ),
            data_quality=dq,
            unavailable_components=[] if dq else ["data_quality"],
        )

    def trends(self, window: TimeWindow) -> tuple[str, list[TrendPoint]]:
        granularity = "month" if window.range.value == "year" else "day"
        emails = self.session.scalars(
            select(EmailMessage).where(
                EmailMessage.direction == Direction.INBOUND.value,
                EmailMessage.created_at >= window.start,
                EmailMessage.created_at <= window.end,
            )
        ).all()
        buckets: dict[str, _TrendBucket] = defaultdict(_TrendBucket)
        for email in emails:
            stamp = _utc(email.created_at)
            key = stamp.strftime("%Y-%m" if granularity == "month" else "%Y-%m-%d")
            bucket = buckets[key]
            bucket.received += 1
            duration = _duration_ms(email.created_at, email.updated_at)
            if duration is not None:
                bucket.times.append(duration)
            if email.processing_status == ProcessingStatus.FAILED.value:
                bucket.failed += 1
        decisions = self.session.execute(
            select(ValidationDecision.created_at, ValidationDecision.decision).where(
                ValidationDecision.created_at >= window.start,
                ValidationDecision.created_at <= window.end,
            )
        ).all()
        for created_at, decision in decisions:
            key = _utc(created_at).strftime("%Y-%m" if granularity == "month" else "%Y-%m-%d")
            if decision == "AUTO_EXECUTE":
                buckets[key].auto += 1
            elif decision in {"ESCALATE", "REVIEW_CORRECTION"}:
                buckets[key].escalated += 1
        points = []
        for key in sorted(buckets):
            bucket = buckets[key]
            points.append(
                TrendPoint(
                    period=key,
                    received=bucket.received,
                    auto_resolved=bucket.auto,
                    escalated=bucket.escalated,
                    failed=bucket.failed,
                    average_processing_ms=(
                        sum(bucket.times) / len(bucket.times) if bucket.times else None
                    ),
                )
            )
        return granularity, points

    def category_counts(self, window: TimeWindow, *, outcomes: bool) -> list[CategoryCount]:
        operations = self.session.scalars(
            select(Operation).where(
                Operation.created_at >= window.start,
                Operation.created_at <= window.end,
            )
        ).all()
        counts: dict[str, int] = defaultdict(int)
        for operation in operations:
            name = operation.status if outcomes else _intent(operation.action)
            counts[name] += 1
        return [CategoryCount(name=name, value=counts[name]) for name in sorted(counts)]

    def recent(self, window: TimeWindow, limit: int = 25) -> list[RecentRequest]:
        rows = self.session.execute(
            select(BusinessRequest, EmailMessage, Operation)
            .join(EmailMessage, EmailMessage.id == BusinessRequest.initiating_email_id)
            .join(Operation, Operation.request_id == BusinessRequest.id)
            .where(
                BusinessRequest.created_at >= window.start,
                BusinessRequest.created_at <= window.end,
            )
            .order_by(BusinessRequest.created_at.desc())
            .limit(limit)
        ).all()
        return [
            RecentRequest(
                timestamp=_utc(request.created_at),
                request_id=request.public_reference,
                sender_group="authorized-group"
                if email.authorization_allowed
                else "unverified-group",
                intent=_intent(operation.action),
                confidence=_confidence(operation),
                pdv_code=operation.pdv_code,
                otp_present=bool(operation.phone),
                action=operation.action,
                status=operation.status,
                duration_ms=_duration_ms(request.created_at, request.completed_at),
                validation_error=request.escalation_reason,
            )
            for request, email, operation in rows
        ]

    def requests(self, *, page: int, page_size: int, manual_only: bool = False) -> RequestPage:
        conditions = []
        if manual_only:
            conditions.append(BusinessRequest.status == "ESCALATED")
        total = self.session.scalar(select(func.count(BusinessRequest.id)).where(*conditions)) or 0
        rows = self.session.execute(
            select(BusinessRequest, func.count(Operation.id))
            .outerjoin(Operation, Operation.request_id == BusinessRequest.id)
            .where(*conditions)
            .group_by(BusinessRequest.id)
            .order_by(BusinessRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return RequestPage(
            items=[
                RequestRow(
                    request_id=str(request.id),
                    public_reference=request.public_reference,
                    created_at=_utc(request.created_at),
                    status=request.status,
                    request_kind=request.request_kind,
                    operation_count=count,
                    escalation_reason=request.escalation_reason,
                )
                for request, count in rows
            ],
            pagination=PageMeta(page=page, page_size=page_size, total=total),
        )

    def operation(self, operation_id: uuid.UUID) -> OperationRow | None:
        operation = self.session.get(Operation, operation_id)
        if operation is None:
            return None
        return OperationRow(
            operation_id=str(operation.id),
            request_id=str(operation.request_id),
            action=operation.action,
            status=operation.status,
            pdv_code=operation.pdv_code,
            phone=operation.phone,
            current_revision=operation.current_revision,
            final_decision=operation.final_decision,
            execution_eligible=operation.execution_eligible,
            created_at=_utc(operation.created_at),
        )

    def audit(self, *, page: int, page_size: int) -> AuditPage:
        events: list[AuditEvent] = []
        decisions = self.session.scalars(
            select(ValidationDecision).order_by(ValidationDecision.created_at.desc()).limit(250)
        ).all()
        for decision in decisions:
            events.append(
                AuditEvent(
                    timestamp=_utc(decision.created_at),
                    event_type="policy_decision",
                    request_id=None,
                    operation_id=str(decision.operation_id),
                    state=decision.decision,
                    reason=", ".join(decision.reasons[:3]) if decision.reasons else None,
                )
            )
        executions = self.session.scalars(
            select(Execution).order_by(Execution.created_at.desc()).limit(250)
        ).all()
        for execution in executions:
            events.append(
                AuditEvent(
                    timestamp=_utc(execution.created_at),
                    event_type="business_execution",
                    request_id=None,
                    operation_id=str(execution.operation_id),
                    state=execution.status,
                    reason=None,
                )
            )
        events.sort(key=lambda event: event.timestamp, reverse=True)
        total = len(events)
        start = (page - 1) * page_size
        return AuditPage(
            items=events[start : start + page_size],
            pagination=PageMeta(page=page, page_size=page_size, total=total),
        )

    def model_run_counts(self, window: TimeWindow) -> list[CategoryCount]:
        rows = self.session.execute(
            select(ModelRun.stage, ModelRun.structured_output_valid, func.count(ModelRun.id))
            .where(
                ModelRun.created_at >= window.start,
                ModelRun.created_at <= window.end,
            )
            .group_by(ModelRun.stage, ModelRun.structured_output_valid)
        ).all()
        return [
            CategoryCount(
                name=f"{stage}:{'valid' if valid else 'invalid'}",
                value=count,
            )
            for stage, valid, count in rows
        ]

    def escalation_counts(self, window: TimeWindow) -> list[CategoryCount]:
        rows = self.session.execute(
            select(Escalation.reason_code, func.count(Escalation.id))
            .where(
                Escalation.created_at >= window.start,
                Escalation.created_at <= window.end,
            )
            .group_by(Escalation.reason_code)
        ).all()
        return [CategoryCount(name=reason, value=count) for reason, count in rows]
