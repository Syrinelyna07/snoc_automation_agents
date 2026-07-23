"""Small fake-data-only Hugging Face analyzer/verifier compatibility run."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Engine

from snoc_agent.ai.backend import GenerationConfig, LLMBackend, safe_generation_settings
from snoc_agent.ai.cost import BudgetTracker, calculate_cost
from snoc_agent.ai.errors import InferenceError, InferenceErrorCategory
from snoc_agent.ai.hf_discovery import HFModelCatalog
from snoc_agent.ai.model_registry import canonical_hf_model_id
from snoc_agent.ai.provider import LLMProvider
from snoc_agent.ai.schemas import EmailAnalysis, SemanticVerification
from snoc_agent.cli.runtime import build_model_services
from snoc_agent.config import Settings
from snoc_agent.db import create_engine_and_session, create_schema
from snoc_agent.db.session import SessionFactory, session_scope
from snoc_agent.evaluation.dataset_subsets import synthetic_smoke_examples
from snoc_agent.evaluation.pipeline_predictor import (
    evaluation_context,
    evaluation_context_builder,
    evaluation_verifier_inputs,
    materialize_prediction,
)
from snoc_agent.workflow.model_audit import persist_failed_model_run, persist_model_run

_POLICY_ROUTE_SUFFIXES = frozenset({"fastest", "cheapest", "preferred"})


def require_known_route_pricing(
    catalog: HFModelCatalog,
    routes: Iterable[tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """Resolve usable pricing before a cost-capped live inference is attempted."""

    resolved_pricing: dict[str, dict[str, Any]] = {}
    unavailable: list[str] = []
    for base_model_id, resolved_model_id in routes:
        suffix = (
            resolved_model_id[len(base_model_id) + 1 :]
            if resolved_model_id.startswith(f"{base_model_id}:")
            else ""
        )
        provider = suffix if suffix and suffix not in _POLICY_ROUTE_SUFFIXES else None
        pricing = catalog.pricing_for(base_model_id, provider)
        one_token_cost = calculate_cost(
            prompt_tokens=1,
            completion_tokens=1,
            pricing_metadata=pricing,
        )
        if one_token_cost.total_cost_usd is None:
            unavailable.append(resolved_model_id)
            continue
        resolved_pricing[base_model_id] = pricing
    if unavailable:
        raise InferenceError(
            InferenceErrorCategory.BUDGET_EXHAUSTED,
            "cost-capped Hugging Face inference requires usable input and output pricing; "
            f"pricing unavailable for routes: {sorted(unavailable)}",
        )
    return resolved_pricing


def _error_category(error: BaseException) -> str:
    if isinstance(error, InferenceError):
        return error.category.value
    if isinstance(error, TypeError):
        return InferenceErrorCategory.MALFORMED_OUTPUT.value
    detail = str(error).casefold()
    if isinstance(error, ValueError) and "hf_token" in detail:
        return InferenceErrorCategory.AUTHENTICATION.value
    if isinstance(error, ValueError) and "unavailable" in detail:
        return InferenceErrorCategory.MODEL_UNAVAILABLE.value
    return InferenceErrorCategory.UNKNOWN.value


def _safe_error_message(error: BaseException, *, token: str) -> str:
    detail = " ".join(str(error).split())[:1000]
    return detail.replace(token, "[REDACTED]") if token else detail


def _write_smoke_report(report_path: Path, payload: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_name(f".{report_path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(report_path)


def _persist_failed_smoke_call(
    session_factory: SessionFactory,
    *,
    error: Exception,
    stage: str,
    prompt_version: str,
    input_context: dict[str, Any],
    config: GenerationConfig,
    response_model: type[BaseModel],
    backend_name: str,
    token: str,
) -> None:
    with session_scope(session_factory) as session:
        run = persist_failed_model_run(
            session,
            stage=stage,
            prompt_version=prompt_version,
            input_context=input_context,
            email_message_id=None,
            model_name=config.model,
            base_model_id=config.base_model,
            resolved_model_id=config.model,
            requested_route=config.model,
            backend=backend_name,
            error=error,
            error_category=_error_category(error),
            quantization=config.quantization,
            generation_settings=safe_generation_settings(config),
            json_schema=response_model.model_json_schema(),
            schema_name=response_model.__name__,
        )
        run.error = _safe_error_message(error, token=token)


def _result_audit(result: Any) -> dict[str, Any]:
    return {
        "parsed": result.parsed.model_dump(mode="json"),
        "base_model_id": result.base_model_id,
        "resolved_model_id": result.resolved_model_id,
        "reported_provider": result.reported_provider,
        "structured_output_mode": result.structured_output_mode,
        "schema_guaranteed": result.structured_output_mode == "json_schema",
        "fallback_reason": result.fallback_reason,
        "parse_attempt_count": result.parse_attempt_count,
        "reasoning_returned": result.reasoning_output is not None,
        "logprob_metrics": result.logprob_metrics,
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
        },
        "cost": {
            "input_usd": str(result.input_cost_usd) if result.input_cost_usd is not None else None,
            "output_usd": str(result.output_cost_usd)
            if result.output_cost_usd is not None
            else None,
            "total_usd": str(result.total_cost_usd) if result.total_cost_usd is not None else None,
            "basis": result.cost_basis,
        },
    }


def run_hf_smoke_test(
    settings: Settings,
    *,
    analyzer_model: str,
    verifier_model: str,
    output_dir: Path,
) -> dict[str, Any]:
    analyzer_base_model = canonical_hf_model_id(analyzer_model)
    verifier_base_model = canonical_hf_model_id(verifier_model)
    token = settings.effective_hf_token
    report_path = output_dir / "smoke_report.json"
    rows: list[dict[str, Any]] = []
    budget: BudgetTracker | None = None
    catalog: HFModelCatalog | None = None
    analyzer_backend: LLMBackend | None = None
    verifier_backend: LLMBackend | None = None
    engine: Engine | None = None
    session_factory: SessionFactory | None = None
    active_case_id: str | None = None
    active_stage: str | None = "initialization"

    def report_payload(*, status: str, error: BaseException | None = None) -> dict[str, Any]:
        budget_payload: dict[str, object]
        if budget is None:
            budget_payload = {
                "budget_usd": str(settings.hf_live_test_max_cost_usd),
                "stop_before_usd": str(settings.hf_live_test_max_cost_usd),
                "cost_so_far_usd": "0",
                "request_count": 0,
                "unknown_cost_request_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "status": "not_started",
            }
        else:
            budget_payload = budget.as_dict()
        category = _error_category(error) if error is not None else None
        return {
            "mode": "huggingface_smoke_test",
            "status": status,
            "error_category": category,
            "failure": (
                {
                    "stage": active_stage,
                    "example_id": active_case_id,
                    "error_type": type(error).__name__,
                    "message": _safe_error_message(error, token=token),
                }
                if error is not None
                else None
            ),
            "dry_run": True,
            "external_side_effects": {"imap": False, "smtp": False, "business_api": False},
            "analyzer_model": analyzer_base_model,
            "verifier_model": verifier_base_model,
            "context_limits": {
                "max_model_context_characters": settings.max_model_context_characters,
                "max_latest_message_characters": settings.max_latest_message_characters,
                "max_relevant_thread_characters": settings.max_relevant_thread_characters,
            },
            "completed_case_count": len(rows),
            "total_requests": budget.request_count if budget is not None else 0,
            "usage_and_budget": budget_payload,
            "cases": rows,
            "report_path": str(report_path),
        }

    try:
        if not token:
            raise ValueError("HF_TOKEN is required for the Hugging Face smoke test")
        smoke_settings = settings.model_copy(
            update={
                "llm_provider": LLMProvider.HUGGINGFACE,
                "dry_run": True,
                "hf_analyzer_model": analyzer_base_model,
                "hf_verifier_model": verifier_base_model,
            }
        )
        active_stage = "model_discovery"
        catalog = HFModelCatalog(
            base_url=smoke_settings.effective_hf_base_url,
            token=smoke_settings.effective_hf_token,
            cache_path=smoke_settings.hf_model_list_cache_path,
            cache_ttl_seconds=smoke_settings.hf_model_list_cache_ttl_seconds,
            timeout_seconds=smoke_settings.hf_request_timeout_seconds,
            max_retries=smoke_settings.hf_max_retries,
            retry_base_seconds=smoke_settings.hf_retry_base_seconds,
        )
        required = {analyzer_base_model, verifier_base_model}
        catalog_models = {item.model_id: item for item in catalog.list_models()}
        available = set(catalog_models)
        missing = sorted(required - available)
        if missing:
            alternatives = {
                model: [
                    item.model_id
                    for item in catalog.alternatives(model, require_structured_output=True)
                ]
                for model in missing
            }
            raise ValueError(
                f"smoke-test models unavailable: {missing}; alternatives={alternatives}"
            )
        configured_routes = (
            (analyzer_base_model, smoke_settings.hf_analyzer_provider),
            (verifier_base_model, smoke_settings.hf_verifier_provider),
        )
        for model_id, explicit_provider in configured_routes:
            info = catalog_models[model_id]
            if info.explicitly_unavailable:
                compatible_alternatives = [
                    item.model_id
                    for item in catalog.alternatives(
                        model_id,
                        provider=(
                            explicit_provider
                            if smoke_settings.hf_routing_suffix_enabled and explicit_provider
                            else None
                        ),
                        require_structured_output=True,
                    )
                ]
                raise ValueError(
                    f"model {model_id!r} is listed but unavailable; "
                    f"alternatives={compatible_alternatives}"
                )
            provider_names = info.provider_names(available_only=True)
            normalized_provider = explicit_provider.casefold().replace("_", "-")
            if (
                smoke_settings.hf_routing_suffix_enabled
                and explicit_provider
                and provider_names
                and normalized_provider not in provider_names
            ):
                compatible_alternatives = [
                    item.model_id
                    for item in catalog.alternatives(
                        model_id,
                        provider=explicit_provider,
                        require_structured_output=True,
                    )
                ]
                raise ValueError(
                    f"provider {explicit_provider!r} is unavailable for {model_id}; "
                    f"available={sorted(provider_names)}; "
                    f"alternatives={compatible_alternatives}"
                )
        budget = BudgetTracker(
            budget_usd=smoke_settings.hf_live_test_max_cost_usd,
            stop_before_usd=smoke_settings.hf_live_test_max_cost_usd,
            allow_unknown_cost=smoke_settings.hf_allow_unknown_cost,
        )
        active_stage = "service_initialization"
        analyzer_backend, verifier_backend, analyzer, verifier = build_model_services(
            smoke_settings,
            analyzer_model=analyzer_model,
            verifier_model=verifier_model,
            budget_tracker=budget,
            pricing_resolver=catalog.pricing_for,
        )
        engine, session_factory = create_engine_and_session(smoke_settings.database_url)
        create_schema(engine)
        context_builder = evaluation_context_builder(smoke_settings)
        backend_name = str(getattr(analyzer_backend, "backend_name", LLMProvider.HUGGINGFACE.value))
        for example in synthetic_smoke_examples():
            active_case_id = example.example_id
            active_stage = "smoke_analysis"
            context, _candidates = evaluation_context(example, context_builder=context_builder)
            try:
                analyzer_result = analyzer.analyze(context)
                if not isinstance(analyzer_result.parsed, EmailAnalysis):
                    raise TypeError("smoke analyzer returned the wrong Pydantic schema")
            except Exception as error:
                _persist_failed_smoke_call(
                    session_factory,
                    error=error,
                    stage="smoke_analysis",
                    prompt_version=analyzer.prompt_version,
                    input_context=context,
                    config=analyzer.config,
                    response_model=EmailAnalysis,
                    backend_name=backend_name,
                    token=token,
                )
                raise
            with session_scope(session_factory) as session:
                persist_model_run(
                    session,
                    result=analyzer_result,
                    stage="smoke_analysis",
                    prompt_version=analyzer.prompt_version,
                    input_context=context,
                    email_message_id=None,
                    generation_settings=safe_generation_settings(analyzer.config),
                )
            verifier_results = []
            verifier_audits = []
            for proposal in analyzer_result.parsed.operations:
                active_stage = "smoke_verification"
                verifier_inputs = evaluation_verifier_inputs(
                    example,
                    proposal,
                    context_builder=context_builder,
                )
                payload = verifier.input_payload(
                    proposed_operation=proposal,
                    **verifier_inputs,
                )
                try:
                    verifier_result = verifier.verify(
                        proposed_operation=proposal,
                        **verifier_inputs,
                    )
                    if not isinstance(verifier_result.parsed, SemanticVerification):
                        raise TypeError("smoke verifier returned the wrong Pydantic schema")
                except Exception as error:
                    _persist_failed_smoke_call(
                        session_factory,
                        error=error,
                        stage="smoke_verification",
                        prompt_version=verifier.prompt_version,
                        input_context=payload,
                        config=verifier.config,
                        response_model=SemanticVerification,
                        backend_name=backend_name,
                        token=token,
                    )
                    raise
                with session_scope(session_factory) as session:
                    persist_model_run(
                        session,
                        result=verifier_result,
                        stage="smoke_verification",
                        prompt_version=verifier.prompt_version,
                        input_context=payload,
                        email_message_id=None,
                        generation_settings=safe_generation_settings(verifier.config),
                    )
                verifier_results.append(verifier_result)
                verifier_audits.append(_result_audit(verifier_result))
            prediction = materialize_prediction(
                example,
                analyzer_result=analyzer_result,
                verifier_results=verifier_results,
                context_builder=context_builder,
            )
            rows.append(
                {
                    "example_id": example.example_id,
                    "subject": example.subject,
                    "body": example.body,
                    "expected": example.as_dict(),
                    "analyzer": _result_audit(analyzer_result),
                    "verifiers": verifier_audits,
                    "prediction": prediction,
                }
            )
            active_case_id = None
            active_stage = None
        payload = report_payload(status="completed")
        _write_smoke_report(report_path, payload)
        return payload
    except BaseException as error:
        _write_smoke_report(report_path, report_payload(status="failed", error=error))
        raise
    finally:
        for b in (analyzer_backend, verifier_backend):
            if b is not None:
                close = getattr(b, "close", None)
                if callable(close):
                    close()
        if catalog is not None:
            catalog.close()
        if engine is not None:
            engine.dispose()
