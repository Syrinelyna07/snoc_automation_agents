"""Strict Pydantic contracts for untrusted model output."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FieldEvidence(StrictModel):
    field_name: str
    value: str | None
    source: Literal[
        "latest_user_message",
        "stored_request_state",
        "previous_agent_question",
        "relevant_thread_context",
        "quoted_closed_history",
        "unknown",
    ]
    evidence_text: str | None
    support: Literal["supported", "unsupported", "unclear"]


class ProposedOperation(StrictModel):
    local_operation_id: str
    action: Literal[
        "vpn_access",
        "otp_number_change",
        "account_unblock",
        "password_reset",
        "unknown",
    ]
    pdv_code: str | None
    phone: str | None
    additional_fields: dict[str, str | None] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    evidence: list[FieldEvidence] = Field(default_factory=list)
    ambiguity_reasons: list[str] = Field(default_factory=list)
    raw_action_confidence: float | None = None
    raw_field_confidence: dict[str, float | None] = Field(default_factory=dict)

    @field_validator("raw_action_confidence")
    @classmethod
    def confidence_range(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class EmailAnalysis(StrictModel):
    message_kind: Literal[
        "new_request",
        "clarification_reply",
        "correction",
        "mixed",
        "irrelevant",
        "ambiguous",
        "automated",
    ]
    referenced_existing_operation_ids: list[str] = Field(default_factory=list)
    operations: list[ProposedOperation] = Field(default_factory=list)
    new_request_present: bool
    contradiction_with_stored_state: bool
    contradiction_details: list[str] = Field(default_factory=list)
    unresolved_ambiguities: list[str] = Field(default_factory=list)


class SemanticVerification(StrictModel):
    action_supported: Literal["yes", "no", "unclear"]
    pdv_supported: Literal["yes", "no", "unclear", "not_required"]
    phone_supported: Literal["yes", "no", "unclear", "not_required"]
    stored_state_compatible: Literal["yes", "no", "unclear"]
    contradiction_present: bool
    contradiction_type: str | None
    missing_fields: list[str] = Field(default_factory=list)
    additional_fields_supported: dict[str, Literal["yes", "no", "unclear"]] = Field(
        default_factory=dict
    )
    correction_detected: bool
    new_request_detected: bool
    evidence_summary: list[str] = Field(default_factory=list)
    raw_confidence: float | None = None

    @field_validator("raw_confidence")
    @classmethod
    def confidence_range(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class ConfidenceRecord(StrictModel):
    raw_model_confidence: float | None
    logprob_margin_if_available: float | None
    analyzer_verifier_agreement: bool
    structured_output_valid: bool
    evidence_complete: bool
    correlation_strength: Literal["strong", "weak", "new", "conflict", "none"]
    hard_invariants_passed: bool
