from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from snoc_agent.ai.analyzer import EmailAnalyzer
from snoc_agent.ai.backend import (
    ChatMessage,
    GenerationConfig,
    StructuredGenerationResult,
)
from snoc_agent.ai.errors import InferenceError, InferenceErrorCategory
from snoc_agent.ai.hf_discovery import HFModelInfo
from snoc_agent.ai.provider import LLMProvider
from snoc_agent.ai.schemas import (
    EmailAnalysis,
    FieldEvidence,
    ProposedOperation,
    SemanticVerification,
)
from snoc_agent.ai.verifier import SemanticVerifier
from snoc_agent.config import Settings
from snoc_agent.db import create_engine_and_session
from snoc_agent.db.models import ModelRun
from snoc_agent.db.session import session_scope
from snoc_agent.evaluation import hf_smoke
from snoc_agent.evaluation.dataset_subsets import synthetic_smoke_examples

ANALYZER_MODEL = "Qwen/Qwen2.5-7B-Instruct"
VERIFIER_MODEL = "Qwen/Qwen3-8B"


class FakeCatalog:
    closed = False

    def __init__(self, **_kwargs: Any) -> None:
        self.closed = False

    def list_models(self) -> list[HFModelInfo]:
        pricing = {"input": "0.1", "output": "0.2"}
        return [
            HFModelInfo(model_id=ANALYZER_MODEL, pricing=pricing),
            HFModelInfo(model_id=VERIFIER_MODEL, pricing=pricing),
        ]

    def alternatives(self, _model: str, **_kwargs: Any) -> list[HFModelInfo]:
        return []

    def pricing_for(self, _model: str, _provider: str | None) -> dict[str, Any]:
        return {"input": "0.1", "output": "0.2"}

    def close(self) -> None:
        self.closed = True


class SequencedBackend:
    backend_name = "huggingface"

    def __init__(self, outcomes: list[StructuredGenerationResult | Exception]) -> None:
        self.outcomes = outcomes
        self.closed = False

    def generate_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[BaseModel],
        config: GenerationConfig,
    ) -> StructuredGenerationResult:
        del messages, response_model, config
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self) -> None:
        self.closed = True


def _settings(tmp_path) -> Settings:
    return Settings(
        llm_provider=LLMProvider.HUGGINGFACE,
        hf_token="unit-hf-token",
        hf_analyzer_model=ANALYZER_MODEL,
        hf_verifier_model=VERIFIER_MODEL,
        database_url=f"sqlite:///{tmp_path / 'smoke.db'}",
        hf_model_list_cache_path=tmp_path / "models.json",
    )


def _analysis_result(pdv_code: str = "71000001") -> StructuredGenerationResult:
    parsed = EmailAnalysis(
        message_kind="new_request",
        operations=[
            ProposedOperation(
                local_operation_id="smoke-operation-1",
                action="account_unblock",
                pdv_code=pdv_code,
                phone=None,
                evidence=[
                    FieldEvidence(
                        field_name="pdv_code",
                        value=pdv_code,
                        source="latest_user_message",
                        evidence_text=pdv_code,
                        support="supported",
                    )
                ],
            )
        ],
        new_request_present=True,
        contradiction_with_stored_state=False,
    )
    return _structured_result(parsed, ANALYZER_MODEL)


def _verification_result() -> StructuredGenerationResult:
    parsed = SemanticVerification(
        action_supported="yes",
        pdv_supported="yes",
        phone_supported="not_required",
        stored_state_compatible="yes",
        contradiction_present=False,
        contradiction_type=None,
        correction_detected=False,
        new_request_detected=True,
        evidence_summary=["supported by the current message"],
    )
    return _structured_result(parsed, VERIFIER_MODEL)


def _structured_result(parsed: BaseModel, base_model: str) -> StructuredGenerationResult:
    routed = f"{base_model}:cheapest"
    return StructuredGenerationResult(
        parsed=parsed,
        raw_output=parsed.model_dump_json(),
        model_name=routed,
        backend="huggingface",
        latency_seconds=0.01,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        base_model_id=base_model,
        resolved_model_id=routed,
        requested_route=routed,
        structured_output_mode="json_schema",
        json_schema=type(parsed).model_json_schema(),
        schema_name=type(parsed).__name__,
        total_cost_usd=Decimal("0.000001"),
        cost_basis="estimated",
    )


def _services(
    backend: SequencedBackend,
) -> tuple[SequencedBackend, SequencedBackend, EmailAnalyzer, SemanticVerifier]:
    analyzer = EmailAnalyzer(
        backend,
        GenerationConfig(
            model=f"{ANALYZER_MODEL}:cheapest",
            base_model=ANALYZER_MODEL,
        ),
    )
    verifier = SemanticVerifier(
        backend,
        GenerationConfig(
            model=f"{VERIFIER_MODEL}:cheapest",
            base_model=VERIFIER_MODEL,
        ),
    )
    return backend, backend, analyzer, verifier


def _patch_smoke_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    backend: SequencedBackend,
    examples: list[Any],
) -> None:
    monkeypatch.setattr(hf_smoke, "HFModelCatalog", FakeCatalog)
    monkeypatch.setattr(hf_smoke, "synthetic_smoke_examples", lambda: examples)
    monkeypatch.setattr(
        hf_smoke,
        "build_model_services",
        lambda *_args, **_kwargs: _services(backend),
    )


def _model_runs(settings: Settings) -> list[ModelRun]:
    engine, session_factory = create_engine_and_session(settings.database_url)
    try:
        with session_scope(session_factory) as session:
            return list(session.scalars(select(ModelRun).order_by(ModelRun.created_at)))
    finally:
        engine.dispose()


def test_smoke_early_configuration_failure_still_writes_report(tmp_path) -> None:
    output_dir = tmp_path / "output"
    settings = Settings(hf_token="")

    with pytest.raises(ValueError, match="HF_TOKEN"):
        hf_smoke.run_hf_smoke_test(
            settings,
            analyzer_model=ANALYZER_MODEL,
            verifier_model=VERIFIER_MODEL,
            output_dir=output_dir,
        )

    report = json.loads((output_dir / "smoke_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["error_category"] == "authentication"
    assert report["completed_case_count"] == 0
    assert report["usage_and_budget"]["status"] == "not_started"


def test_smoke_analyzer_failure_persists_audit_and_completed_case_report(
    tmp_path, monkeypatch
) -> None:
    error = InferenceError(
        InferenceErrorCategory.TIMEOUT,
        "analyzer timed out with unit-hf-token",
        structured_output_mode="json_schema",
        json_schema=EmailAnalysis.model_json_schema(),
        schema_name="EmailAnalysis",
        prompt_tokens=7,
        total_tokens=7,
        transport_attempt_count=2,
    )
    backend = SequencedBackend([_analysis_result(), _verification_result(), error])
    examples = synthetic_smoke_examples()[:2]
    _patch_smoke_dependencies(monkeypatch, backend=backend, examples=examples)
    settings = _settings(tmp_path)
    output_dir = tmp_path / "output"

    with pytest.raises(InferenceError) as caught:
        hf_smoke.run_hf_smoke_test(
            settings,
            analyzer_model=ANALYZER_MODEL,
            verifier_model=VERIFIER_MODEL,
            output_dir=output_dir,
        )

    assert caught.value.category == InferenceErrorCategory.TIMEOUT
    report = json.loads((output_dir / "smoke_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["error_category"] == "timeout"
    assert report["completed_case_count"] == 1
    assert [row["example_id"] for row in report["cases"]] == [examples[0].example_id]
    assert report["failure"]["stage"] == "smoke_analysis"
    assert report["failure"]["example_id"] == examples[1].example_id
    assert "unit-hf-token" not in report["failure"]["message"]
    assert "[REDACTED]" in report["failure"]["message"]

    failed = [run for run in _model_runs(settings) if not run.structured_output_valid]
    assert len(failed) == 1
    assert failed[0].stage == "smoke_analysis"
    assert failed[0].error_category == "timeout"
    assert failed[0].request_attempt_count == 2
    assert failed[0].prompt_tokens == 7
    assert "unit-hf-token" not in (failed[0].error or "")
    assert backend.closed


def test_smoke_verifier_failure_persists_audit_and_partial_report(tmp_path, monkeypatch) -> None:
    error = InferenceError(
        InferenceErrorCategory.MALFORMED_OUTPUT,
        "verifier returned malformed JSON",
        structured_output_mode="json_schema",
        json_schema=SemanticVerification.model_json_schema(),
        schema_name="SemanticVerification",
        parse_attempt_count=1,
        raw_output="not-json",
        transport_attempt_count=1,
    )
    backend = SequencedBackend([_analysis_result(), error])
    examples = synthetic_smoke_examples()[:1]
    _patch_smoke_dependencies(monkeypatch, backend=backend, examples=examples)
    settings = _settings(tmp_path)
    output_dir = tmp_path / "output"

    with pytest.raises(InferenceError) as caught:
        hf_smoke.run_hf_smoke_test(
            settings,
            analyzer_model=ANALYZER_MODEL,
            verifier_model=VERIFIER_MODEL,
            output_dir=output_dir,
        )

    assert caught.value.category == InferenceErrorCategory.MALFORMED_OUTPUT
    report = json.loads((output_dir / "smoke_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["error_category"] == "malformed_output"
    assert report["completed_case_count"] == 0
    assert report["cases"] == []
    assert report["failure"] == {
        "stage": "smoke_verification",
        "example_id": examples[0].example_id,
        "error_type": "InferenceError",
        "message": "verifier returned malformed JSON",
    }

    failed = [run for run in _model_runs(settings) if not run.structured_output_valid]
    assert len(failed) == 1
    assert failed[0].stage == "smoke_verification"
    assert failed[0].error_category == "malformed_output"
    assert failed[0].raw_output == "not-json"
    assert failed[0].schema_name == "SemanticVerification"
    assert backend.closed


def test_known_route_pricing_guard_rejects_unknown_pricing_before_live_inference() -> None:
    class UnknownPricingCatalog:
        def pricing_for(self, _model: str, _provider: str | None) -> dict[str, Any]:
            return {}

    with pytest.raises(InferenceError) as caught:
        hf_smoke.require_known_route_pricing(
            UnknownPricingCatalog(),  # type: ignore[arg-type]
            [(ANALYZER_MODEL, f"{ANALYZER_MODEL}:cheapest")],
        )

    assert caught.value.category == InferenceErrorCategory.BUDGET_EXHAUSTED
    assert "pricing unavailable" in str(caught.value)


def test_known_route_pricing_guard_uses_explicit_provider_metadata() -> None:
    calls: list[tuple[str, str | None]] = []

    class KnownPricingCatalog:
        def pricing_for(self, model: str, provider: str | None) -> dict[str, Any]:
            calls.append((model, provider))
            return {"input": "0.1", "output": "0.2"}

    pricing = hf_smoke.require_known_route_pricing(
        KnownPricingCatalog(),  # type: ignore[arg-type]
        [
            (ANALYZER_MODEL, f"{ANALYZER_MODEL}:cheapest"),
            (VERIFIER_MODEL, f"{VERIFIER_MODEL}:cerebras"),
        ],
    )

    assert calls == [(ANALYZER_MODEL, None), (VERIFIER_MODEL, "cerebras")]
    assert pricing == {
        ANALYZER_MODEL: {"input": "0.1", "output": "0.2"},
        VERIFIER_MODEL: {"input": "0.1", "output": "0.2"},
    }
