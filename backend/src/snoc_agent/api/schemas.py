"""Typed public response contracts. Sensitive model/email bodies are intentionally absent."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComponentStatus(APIModel):
    name: str
    status: str
    detail: str | None = None
    checked_at: datetime


class HealthResponse(APIModel):
    status: str
    mode: str
    request_id: str
    components: list[ComponentStatus] = Field(default_factory=list)


class OperationalSummary(APIModel):
    total_requests: int
    auto_resolved: int
    in_progress: int
    manual_review: int
    rejected: int
    failed: int
    average_processing_ms: float | None
    readiness_rate: float | None


class DQExecutive(APIModel):
    overall_quality_score: float | None
    total_rules: int
    passed_rules: int
    failed_rules: int
    error_rules: int
    failed_checks: int
    critical_fatal_open_issues: int
    tables_monitored: int
    last_execution_at: datetime | None


class DashboardSummary(APIModel):
    range: str
    generated_at: datetime
    mode: str
    operational: OperationalSummary
    data_quality: DQExecutive | None
    unavailable_components: list[str] = Field(default_factory=list)


class TrendPoint(APIModel):
    period: str
    received: int
    auto_resolved: int
    escalated: int
    failed: int
    average_processing_ms: float | None


class TrendResponse(APIModel):
    range: str
    granularity: str
    data: list[TrendPoint]


class CategoryCount(APIModel):
    name: str
    value: int


class CategoryResponse(APIModel):
    range: str
    data: list[CategoryCount]


class RecentRequest(APIModel):
    timestamp: datetime
    request_id: str
    sender_group: str
    intent: str
    confidence: float | None
    pdv_code: str | None
    otp_present: bool
    action: str
    status: str
    duration_ms: float | None
    validation_error: str | None


class RecentResponse(APIModel):
    range: str
    items: list[RecentRequest]


class PageMeta(APIModel):
    page: int
    page_size: int
    total: int


class RequestRow(APIModel):
    request_id: str
    public_reference: str
    created_at: datetime
    status: str
    request_kind: str
    operation_count: int
    escalation_reason: str | None


class RequestPage(APIModel):
    items: list[RequestRow]
    pagination: PageMeta


class OperationRow(APIModel):
    operation_id: str
    request_id: str
    action: str
    status: str
    pdv_code: str | None
    phone: str | None
    current_revision: int
    final_decision: str | None
    execution_eligible: bool
    created_at: datetime


class AuditEvent(APIModel):
    timestamp: datetime
    event_type: str
    request_id: str | None
    operation_id: str | None
    state: str
    reason: str | None


class AuditPage(APIModel):
    items: list[AuditEvent]
    pagination: PageMeta


class DQDimension(APIModel):
    dimension: str
    dimension_score: float | None
    total_rules: int
    passed_rules: int
    failed_rules: int
    error_rules: int
    failed_checks: int


class DQTable(APIModel):
    table_name: str
    source_variant: str | None
    table_quality_score: float | None
    total_rules: int
    passed_rules: int
    failed_rules: int
    error_rules: int
    failed_checks: int


class DQSource(APIModel):
    source_variant: str
    source_quality_score: float | None = None
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    error_rules: int = 0
    failed_checks: int = 0


class DQColumn(APIModel):
    table_name: str
    source_variant: str | None
    column_name: str
    total_rules: int
    passed_rules: int
    failed_rules: int
    error_rules: int
    total_records_checked: int
    total_passed_records: int
    total_failed_records: int
    column_dq_score: float | None


class DQRule(APIModel):
    run_id: str
    executed_at: datetime
    project_name: str | None
    rule_id: str
    table_name: str
    column_name: str | None
    dimension: str
    severity: str
    failed_rows: int
    passed_rows: int
    total_rows: int
    score: float | None
    status: str
    comparison_score: float | None
    error_message: str | None
    rule_family_id: str | None
    source_variant: str | None


class DQPayload(APIModel):
    available: bool
    reason: str | None = None
    data: list[DQDimension | DQTable | DQSource | DQColumn | DQRule] = Field(default_factory=list)


class ModelSnapshot(APIModel):
    available: bool
    label: str
    reason: str | None = None


class WorkflowStage(APIModel):
    name: str
    status: str
    processed_count: int | None
    error_count: int | None
    average_duration_ms: float | None
    last_successful_event: datetime | None
    description: str


class WorkflowResponse(APIModel):
    mode: str
    stages: list[WorkflowStage]
