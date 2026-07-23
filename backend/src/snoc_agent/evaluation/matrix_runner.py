"""Cost-aware, persistent analyzer/verifier matrix evaluation."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any

from sqlalchemy import select

from snoc_agent.ai.analyzer import EmailAnalyzer
from snoc_agent.ai.cost import BudgetTracker
from snoc_agent.ai.errors import InferenceError
from snoc_agent.ai.hf_discovery import HFModelCatalog
from snoc_agent.ai.model_registry import MODEL_PAIRS, ModelPair, canonical_hf_model_id
from snoc_agent.ai.prompts import ANALYZER_PROMPT_VERSION, VERIFIER_PROMPT_VERSION
from snoc_agent.ai.provider import LLMProvider
from snoc_agent.ai.schemas import EmailAnalysis, SemanticVerification
from snoc_agent.ai.verifier import SemanticVerifier
from snoc_agent.cli.runtime import build_model_services
from snoc_agent.config import Settings
from snoc_agent.db import create_engine_and_session, create_schema
from snoc_agent.db.base import utc_now
from snoc_agent.db.models import EvaluationInference, EvaluationRun, ModelRun
from snoc_agent.db.session import SessionFactory, session_scope
from snoc_agent.evaluation.comparison import compare_runs
from snoc_agent.evaluation.dataset_loader import EvaluationExample
from snoc_agent.evaluation.inference_cache import (
    CacheMode,
    PersistentInferenceCache,
    canonical_hash,
)
from snoc_agent.evaluation.metrics import evaluate_predictions
from snoc_agent.evaluation.offline_runner import ModelConfiguration, OfflineRun
from snoc_agent.evaluation.pipeline_predictor import (
    evaluation_context,
    evaluation_context_builder,
    evaluation_verifier_inputs,
    materialize_prediction,
)
from snoc_agent.evaluation.reports import write_comparison_report, write_offline_run_report


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _failure_attribution(
    examples: list[EvaluationExample],
    runs: dict[str, OfflineRun],
    *,
    provider: LLMProvider,
) -> dict[str, Any]:
    """Separate legacy demo candidates from real-stage and policy diagnostics."""

    demo_candidate_ids = [
        example.example_id
        for example in examples
        if bool(example.metadata.get("demo_unsafe_candidate"))
    ]
    ground_truth_problem_ids = [
        example.example_id
        for example in examples
        if not example.scorable or not example.operation_scorable
    ]
    real_measurement = provider != LLMProvider.DEMO
    per_run: dict[str, Any] = {}
    for run_name, offline_run in runs.items():
        rows = offline_run.evaluation.rows
        analyzer_failures = [
            row["example_id"]
            for row in rows
            if row["operation_scored"] and not row["joint_action_and_fields_exact_match"]
        ]
        verifier_failures = [
            row["example_id"]
            for row in rows
            if row["analyzer_verifier_agreement"] is False or not row["structured_output_valid"]
        ]
        decision_policy_failures = [
            row["example_id"]
            for row in rows
            if row["unsafe_auto_execute"]
            or row["validation_pass_but_wrong"]
            or row["validation_fail_but_correct"]
            or row["false_escalation"]
        ]
        per_run[run_name] = {
            "real_model_analyzer_failures": analyzer_failures if real_measurement else [],
            "verifier_failures": verifier_failures if real_measurement else [],
            "decision_policy_failures": decision_policy_failures if real_measurement else [],
            "data_or_ground_truth_problems": ground_truth_problem_ids,
        }
    return {
        "provider": provider.value,
        "real_model_measurement_performed": real_measurement,
        "hugging_face_measurement_performed": provider == LLMProvider.HUGGINGFACE,
        "demo_backend_failures": {
            "measurement_type": "deterministic_demo_not_qwen",
            "count": len(demo_candidate_ids),
            "example_ids": demo_candidate_ids,
        },
        "runs": per_run,
        "classification_note": (
            "Analyzer failures are operation-level extraction mismatches; verifier failures "
            "are structured failures or analyzer/verifier disagreement; decision-policy "
            "failures are unsafe execution, validation, or false-escalation diagnostics. "
            "Categories may overlap."
        ),
    }


def _failed_prediction(stage: str, error: InferenceError) -> dict[str, Any]:
    """Materialize a safe evaluation row without inventing a structured model result."""

    return {
        "predicted_label": "unknown",
        "operations": [],
        "decisions": ["escalate"],
        "structured_output_valid": False,
        "structured_output_modes": [error.structured_output_mode or "failed"],
        "structured_output_schema_guaranteed": False,
        "analyzer_verifier_agreement": False,
        "contradiction_present": None,
        "validation_passed": False,
        "prompt_tokens": error.prompt_tokens,
        "completion_tokens": error.completion_tokens,
        "total_tokens": error.total_tokens,
        "total_cost_usd": (str(error.total_cost_usd) if error.total_cost_usd is not None else None),
        "cost_bases": [error.cost_basis],
        "incremental_prompt_tokens": error.prompt_tokens,
        "incremental_completion_tokens": error.completion_tokens,
        "incremental_total_cost_usd": (
            str(error.total_cost_usd) if error.total_cost_usd is not None else None
        ),
        "incremental_cost_known": error.total_cost_usd is not None,
        "cache_hits": 0,
        "raw_confidence": None,
        "logprob_margin": None,
        "error": f"{stage}:{error.category.value}",
    }


def _new_or_resumed_run(
    session_factory: SessionFactory,
    *,
    resume: bool,
    dataset_path: Path,
    dataset_hash: str,
    configuration: dict[str, Any],
    configuration_hash: str,
    output_dir: Path,
    budget_usd: Decimal,
    stop_before_usd: Decimal,
    resumable_command: str,
) -> EvaluationRun:
    with session_scope(session_factory) as session:
        run = None
        if resume:
            run = session.scalar(
                select(EvaluationRun)
                .where(
                    EvaluationRun.dataset_hash == dataset_hash,
                    EvaluationRun.configuration_hash == configuration_hash,
                    EvaluationRun.output_dir == str(output_dir),
                    EvaluationRun.status != "complete",
                )
                .order_by(EvaluationRun.created_at.desc())
                .limit(1)
            )
        if run is None:
            run = EvaluationRun(
                status="running",
                dataset_path=str(dataset_path),
                dataset_hash=dataset_hash,
                configuration_hash=configuration_hash,
                configuration=configuration,
                output_dir=str(output_dir),
                budget_usd=budget_usd,
                stop_before_budget_usd=stop_before_usd,
                cost_so_far_usd=Decimal("0"),
                budget_status="within_budget",
                request_count=0,
                unknown_cost_request_count=0,
                prompt_tokens=0,
                completion_tokens=0,
                checkpoint_row=0,
                resumable_command=resumable_command,
            )
            session.add(run)
            session.flush()
        else:
            run.status = "running"
            run.resumable_command = resumable_command
            run.budget_usd = budget_usd
            run.stop_before_budget_usd = stop_before_usd
            run.final_error_category = None
            run.completed_at = None
        return run


def _sync_run(
    session_factory: SessionFactory,
    run_id: uuid.UUID,
    budget: BudgetTracker,
    *,
    checkpoint_row: int | None = None,
    estimated_remaining_calls: int | None = None,
    status: str | None = None,
    error_category: str | None = None,
) -> None:
    with session_scope(session_factory) as session:
        run = session.get(EvaluationRun, run_id)
        if run is None:
            raise LookupError("evaluation run disappeared")
        run.cost_so_far_usd = budget.cost_so_far_usd
        run.budget_status = budget.status
        run.request_count = budget.request_count
        run.unknown_cost_request_count = budget.unknown_cost_request_count
        run.prompt_tokens = budget.prompt_tokens
        run.completion_tokens = budget.completion_tokens
        if checkpoint_row is not None:
            run.checkpoint_row = checkpoint_row
        if estimated_remaining_calls is not None:
            run.estimated_remaining_calls = estimated_remaining_calls
        if status is not None:
            run.status = status
        if error_category is not None:
            run.final_error_category = error_category
        if status == "complete":
            run.final_error_category = None
            run.completed_at = utc_now()


def _restored_budget(
    session_factory: SessionFactory,
    run: EvaluationRun,
    *,
    budget_usd: Decimal,
    stop_before_usd: Decimal,
    allow_unknown_cost: bool,
) -> BudgetTracker:
    """Rebuild spend from atomically linked attempts so a crash cannot reset the guard."""

    run_ids: set[uuid.UUID] = set()
    with session_scope(session_factory) as session:
        inferences = session.scalars(
            select(EvaluationInference).where(
                EvaluationInference.evaluation_run_id == run.id,
            )
        ).all()
        for inference in inferences:
            attempt_ids = list(inference.attempt_model_run_ids or [])
            if inference.cache_hit and inference.model_run_id is not None:
                # Older rows may have appended the referenced global-cache source
                # to the attempt list.  It did not incur spend in this evaluation.
                cached_source_id = str(inference.model_run_id)
                attempt_ids = [value for value in attempt_ids if value != cached_source_id]
            if not attempt_ids and not inference.cache_hit and inference.model_run_id is not None:
                attempt_ids = [str(inference.model_run_id)]
            for raw_id in attempt_ids:
                try:
                    run_ids.add(uuid.UUID(raw_id))
                except (TypeError, ValueError):
                    continue
        model_runs = [
            model_run
            for model_run_id in run_ids
            if (model_run := session.get(ModelRun, model_run_id)) is not None
        ]
    if not model_runs:
        return BudgetTracker(
            budget_usd=budget_usd,
            stop_before_usd=stop_before_usd,
            allow_unknown_cost=allow_unknown_cost,
            cost_so_far_usd=Decimal(str(run.cost_so_far_usd or 0)),
            request_count=run.request_count,
            unknown_cost_request_count=run.unknown_cost_request_count,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
        )
    return BudgetTracker(
        budget_usd=budget_usd,
        stop_before_usd=stop_before_usd,
        allow_unknown_cost=allow_unknown_cost,
        cost_so_far_usd=sum(
            (
                Decimal(str(model_run.total_cost_usd))
                for model_run in model_runs
                if model_run.total_cost_usd is not None
            ),
            Decimal("0"),
        ),
        request_count=sum(model_run.request_attempt_count for model_run in model_runs),
        unknown_cost_request_count=sum(
            model_run.parse_attempt_count
            for model_run in model_runs
            if model_run.total_cost_usd is None and model_run.parse_attempt_count > 0
        ),
        prompt_tokens=sum(model_run.prompt_tokens or 0 for model_run in model_runs),
        completion_tokens=sum(model_run.completion_tokens or 0 for model_run in model_runs),
    )


def _catalog_for(
    settings: Settings,
    *,
    analyzer_models: tuple[str, ...],
    verifier_models: tuple[str, ...],
) -> HFModelCatalog | None:
    if settings.effective_llm_provider != LLMProvider.HUGGINGFACE:
        return None
    if not settings.effective_hf_token:
        raise ValueError("HF_TOKEN is required for Hugging Face evaluation")
    catalog = HFModelCatalog(
        base_url=settings.effective_hf_base_url,
        token=settings.effective_hf_token,
        cache_path=settings.hf_model_list_cache_path,
        cache_ttl_seconds=settings.hf_model_list_cache_ttl_seconds,
        timeout_seconds=settings.hf_request_timeout_seconds,
        max_retries=settings.hf_max_retries,
        retry_base_seconds=settings.hf_retry_base_seconds,
    )
    try:
        discovered = {item.model_id: item for item in catalog.list_models()}
        available = set(discovered)
        analyzer_required = {canonical_hf_model_id(model) for model in analyzer_models}
        verifier_required = {canonical_hf_model_id(model) for model in verifier_models}
        required = analyzer_required | verifier_required
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
                f"configured matrix models unavailable: {missing}; alternatives={alternatives}"
            )
        unavailable = sorted(
            model_id for model_id in required if discovered[model_id].explicitly_unavailable
        )
        if unavailable:
            alternatives = {
                model: [
                    item.model_id
                    for item in catalog.alternatives(model, require_structured_output=True)
                ]
                for model in unavailable
            }
            raise ValueError(
                f"configured matrix models are listed but unavailable: {unavailable}; "
                f"alternatives={alternatives}"
            )
        for stage, explicit_provider, stage_models in (
            ("analyzer", settings.hf_analyzer_provider, analyzer_required),
            ("verifier", settings.hf_verifier_provider, verifier_required),
        ):
            if not explicit_provider or not settings.hf_routing_suffix_enabled:
                continue
            normalized = explicit_provider.casefold().replace("_", "-")
            for model_id in stage_models:
                provider_names = discovered[model_id].provider_names(available_only=True)
                if provider_names and normalized not in provider_names:
                    compatible_alternatives = [
                        item.model_id
                        for item in catalog.alternatives(
                            model_id,
                            provider=explicit_provider,
                            require_structured_output=True,
                        )
                    ]
                    raise ValueError(
                        f"{stage} provider {explicit_provider!r} is unavailable for {model_id}; "
                        f"available={sorted(provider_names)}; "
                        f"alternatives={compatible_alternatives}"
                    )
        return catalog
    except BaseException:
        catalog.close()
        raise


def run_persistent_matrix(
    settings: Settings,
    *,
    dataset_path: Path,
    examples: list[EvaluationExample],
    output_dir: Path,
    cache_mode: CacheMode,
    resume: bool,
    budget_usd: Decimal,
    checkpoint_every: int,
    resumable_command: str,
    model_pairs: Mapping[str, ModelPair] | None = None,
) -> dict[str, Any]:
    """Run each unique inference once, then materialize all four policies."""

    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_hash = _file_hash(dataset_path)
    pairs = dict(model_pairs or MODEL_PAIRS)
    if not pairs:
        raise ValueError("at least one analyzer/verifier pair is required")
    analyzer_models = tuple(dict.fromkeys(pair.analyzer_model for pair in pairs.values()))
    verifier_models = tuple(dict.fromkeys(pair.verifier_model for pair in pairs.values()))
    endpoint_namespace = canonical_hash(
        {
            "provider": settings.effective_llm_provider.value,
            "base_url": (
                settings.effective_hf_base_url
                if settings.effective_llm_provider == LLMProvider.HUGGINGFACE
                else settings.llm_base_url
            ),
        }
    )
    configuration = {
        "provider": settings.effective_llm_provider.value,
        "endpoint_namespace_hash": endpoint_namespace,
        "selected_example_count": len(examples),
        "selected_example_ids_hash": canonical_hash([example.example_id for example in examples]),
        "analyzer_models": analyzer_models,
        "verifier_models": verifier_models,
        "pairs": {
            name: {
                "analyzer_model": pair.analyzer_model,
                "verifier_model": pair.verifier_model,
            }
            for name, pair in pairs.items()
        },
        "provider_policy": settings.hf_provider_policy.value,
        "analyzer_provider": settings.hf_analyzer_provider or None,
        "verifier_provider": settings.hf_verifier_provider or None,
        "routing_suffix_enabled": settings.hf_routing_suffix_enabled,
        "context_limits": {
            "max_model_context_characters": settings.max_model_context_characters,
            "max_latest_message_characters": settings.max_latest_message_characters,
            "max_relevant_thread_characters": settings.max_relevant_thread_characters,
        },
        "prompt_versions": {
            "analyzer": ANALYZER_PROMPT_VERSION,
            "verifier": VERIFIER_PROMPT_VERSION,
        },
        "schema_hashes": {
            "analyzer": canonical_hash(EmailAnalysis.model_json_schema()),
            "verifier": canonical_hash(SemanticVerification.model_json_schema()),
        },
        "generation": {
            "analyzer_temperature": settings.analyzer_temperature,
            "verifier_temperature": settings.verifier_temperature,
            "analyzer_max_tokens": settings.hf_max_output_tokens_analyzer,
            "verifier_max_tokens": settings.hf_max_output_tokens_verifier,
            "max_retries": settings.hf_max_retries,
            "retry_base_seconds": settings.hf_retry_base_seconds,
            "supports_logprobs": settings.llm_supports_logprobs,
            "json_schema": settings.hf_use_json_schema,
            "json_object_fallback": settings.hf_allow_json_object_fallback,
            "prompt_json_fallback": settings.hf_allow_prompt_json_fallback,
            "extra_body_hash": canonical_hash(settings.hf_extra_body),
            "quantization": settings.model_quantization or None,
        },
    }
    configuration_hash = canonical_hash(configuration)
    stop_before = min(settings.hf_stop_before_budget_usd, budget_usd * Decimal("0.95"))
    engine, session_factory = create_engine_and_session(settings.database_url)
    create_schema(engine)
    run = _new_or_resumed_run(
        session_factory,
        resume=resume,
        dataset_path=dataset_path,
        dataset_hash=dataset_hash,
        configuration=configuration,
        configuration_hash=configuration_hash,
        output_dir=output_dir,
        budget_usd=budget_usd,
        stop_before_usd=stop_before,
        resumable_command=resumable_command,
    )
    budget = _restored_budget(
        session_factory,
        run,
        budget_usd=budget_usd,
        stop_before_usd=stop_before,
        allow_unknown_cost=settings.hf_allow_unknown_cost,
    )
    catalog: HFModelCatalog | None = None
    services: dict[str, tuple[Any, EmailAnalyzer, SemanticVerifier]] = {}
    last_completed_row = int(run.checkpoint_row or 0)
    try:
        catalog = _catalog_for(
            settings,
            analyzer_models=analyzer_models,
            verifier_models=verifier_models,
        )
        pricing_resolver = catalog.pricing_for if catalog is not None else None
        service_models = tuple(dict.fromkeys((*analyzer_models, *verifier_models)))
        for model in service_models:
            services[model] = build_model_services(
                settings,
                analyzer_model=model,
                verifier_model=model,
                budget_tracker=budget,
                pricing_resolver=pricing_resolver,
            )

        def progress() -> None:
            _sync_run(session_factory, run.id, budget)

        cache = PersistentInferenceCache(
            session_factory,
            evaluation_run_id=run.id,
            cache_mode=cache_mode,
            resume=resume,
            provider_namespace=endpoint_namespace,
            backend_name=settings.effective_llm_provider.value,
            on_progress=progress,
        )
        context_builder = evaluation_context_builder(settings)
        predictions: dict[str, list[dict[str, Any]]] = {name: [] for name in pairs}
        route_capability_errors: dict[tuple[str, str], InferenceError] = {}
        started_at = datetime.now(UTC)
        logical_inference_count = 0

        def enforce_post_response_budget(result: Any) -> None:
            # A valid response is persisted by the cache before this check.  If
            # that response reaches the known-cost threshold or reveals that
            # pricing is unknown under a strict policy, stop without sending a
            # further call.  Cached/resumed results incur no new spend.
            if not result.cache_hit and budget.status in {"stopped", "stopped_unknown_cost"}:
                budget.before_attempt()

        for row_number, example in enumerate(examples, 1):
            context, _candidates = evaluation_context(example, context_builder=context_builder)
            analyses: dict[str, Any] = {}
            for analyzer_model in analyzer_models:
                _backend, analyzer, _verifier = services[analyzer_model]
                analysis_result: Any = route_capability_errors.get(("analysis", analyzer_model))
                if analysis_result is None:
                    try:
                        analysis_result = cache.get_or_run(
                            example_id=example.example_id,
                            stage="analysis",
                            analyzer_source_model_id=None,
                            prompt_version=analyzer.prompt_version,
                            input_context=context,
                            response_model=EmailAnalysis,
                            config=analyzer.config,
                            invoke=partial(analyzer.analyze, context),
                        )
                    except InferenceError as exc:
                        if exc.category.value not in {
                            "malformed_output",
                            "structured_output_unsupported",
                        }:
                            raise
                        analysis_result = exc
                        if exc.category.value == "structured_output_unsupported":
                            route_capability_errors[("analysis", analyzer_model)] = exc
                logical_inference_count += 1
                analyses[analyzer_model] = analysis_result
                if not isinstance(analysis_result, InferenceError):
                    enforce_post_response_budget(analysis_result)

            verifier_memo: dict[tuple[str, str], Any] = {}
            verifier_results: dict[tuple[str, str], list[Any]] = {}
            for analyzer_model, analysis_result in analyses.items():
                if isinstance(analysis_result, InferenceError):
                    continue
                analysis = analysis_result.parsed
                if not isinstance(analysis, EmailAnalysis):
                    raise TypeError("cached analyzer result has the wrong schema")
                for verifier_model in verifier_models:
                    _backend, _analyzer, verifier = services[verifier_model]
                    stage_results = []
                    for proposal in analysis.operations:
                        verifier_inputs = evaluation_verifier_inputs(
                            example,
                            proposal,
                            context_builder=context_builder,
                        )
                        payload = verifier.input_payload(
                            proposed_operation=proposal,
                            **verifier_inputs,
                        )
                        proposal_hash = canonical_hash(payload)
                        memo_key = (verifier_model, proposal_hash)
                        result = verifier_memo.get(memo_key) or route_capability_errors.get(
                            ("verification", verifier_model)
                        )
                        if result is None:
                            try:
                                result = cache.get_or_run(
                                    example_id=example.example_id,
                                    stage="verification",
                                    analyzer_source_model_id=analyzer_model,
                                    prompt_version=verifier.prompt_version,
                                    input_context=payload,
                                    response_model=SemanticVerification,
                                    config=verifier.config,
                                    proposal_hash=proposal_hash,
                                    invoke=partial(
                                        verifier.verify,
                                        proposed_operation=proposal,
                                        **verifier_inputs,
                                    ),
                                )
                            except InferenceError as exc:
                                if exc.category.value not in {
                                    "malformed_output",
                                    "structured_output_unsupported",
                                }:
                                    raise
                                result = exc
                                if exc.category.value == "structured_output_unsupported":
                                    route_capability_errors[("verification", verifier_model)] = exc
                            logical_inference_count += 1
                            verifier_memo[memo_key] = result
                            if not isinstance(result, InferenceError):
                                enforce_post_response_budget(result)
                        stage_results.append(result)
                    verifier_results[(analyzer_model, verifier_model)] = stage_results

            for run_name, pair in pairs.items():
                pair_analysis = analyses[pair.analyzer_model]
                pair_verifiers = verifier_results.get(
                    (pair.analyzer_model, pair.verifier_model), []
                )
                failure = (
                    pair_analysis
                    if isinstance(pair_analysis, InferenceError)
                    else next(
                        (result for result in pair_verifiers if isinstance(result, InferenceError)),
                        None,
                    )
                )
                if isinstance(failure, InferenceError):
                    stage = (
                        "analysis" if isinstance(pair_analysis, InferenceError) else "verification"
                    )
                    predictions[run_name].append(_failed_prediction(stage, failure))
                else:
                    predictions[run_name].append(
                        materialize_prediction(
                            example,
                            analyzer_result=pair_analysis,
                            verifier_results=pair_verifiers,
                            context_builder=context_builder,
                        )
                    )
            average_per_row = logical_inference_count / row_number
            remaining = round(max(0, len(examples) - row_number) * average_per_row)
            _sync_run(
                session_factory,
                run.id,
                budget,
                checkpoint_row=row_number,
                estimated_remaining_calls=remaining,
            )
            last_completed_row = row_number
            if row_number % checkpoint_every == 0 or row_number == len(examples):
                _atomic_json(
                    output_dir / "checkpoint.json",
                    {
                        "evaluation_run_id": run.id,
                        "dataset_hash": dataset_hash,
                        "configuration_hash": configuration_hash,
                        "completed_rows": row_number,
                        "total_rows": len(examples),
                        "budget": budget.as_dict(),
                        "resume_command": resumable_command,
                    },
                )

        finished_at = datetime.now(UTC)
        runs: dict[str, OfflineRun] = {}
        artifacts: dict[str, Any] = {}
        for run_name, pair in pairs.items():
            run_predictions = predictions[run_name]
            offline_run = OfflineRun(
                configuration=ModelConfiguration(
                    analyzer_model=pair.analyzer_model,
                    verifier_model=pair.verifier_model,
                    analyzer_backend=settings.effective_llm_provider.value,
                    verifier_backend=settings.effective_llm_provider.value,
                    prompt_versions={
                        "analyzer": ANALYZER_PROMPT_VERSION,
                        "verifier": VERIFIER_PROMPT_VERSION,
                    },
                    metadata={
                        "ground_truth_visible_to_predictor": False,
                        "evaluation_run_id": str(run.id),
                        "demo_backend_measurement": settings.effective_llm_provider
                        == LLMProvider.DEMO,
                    },
                ),
                examples=tuple(examples),
                predictions=tuple(run_predictions),
                evaluation=evaluate_predictions(examples, run_predictions),
                started_at=started_at,
                finished_at=finished_at,
            )
            runs[run_name] = offline_run
            report_dir = output_dir if len(pairs) == 1 else output_dir / run_name
            paths = write_offline_run_report(report_dir, offline_run)
            artifacts[run_name] = {key: str(value) for key, value in asdict(paths).items()}
        comparison = compare_runs(runs, baseline_run=next(iter(pairs)))
        comparison_paths = write_comparison_report(output_dir, comparison)
        attribution = _failure_attribution(
            examples,
            runs,
            provider=settings.effective_llm_provider,
        )
        attribution_path = output_dir / "failure_attribution.json"
        _atomic_json(attribution_path, attribution)
        _sync_run(
            session_factory,
            run.id,
            budget,
            checkpoint_row=len(examples),
            estimated_remaining_calls=0,
            status="complete",
        )
        result = {
            "evaluation_run_id": str(run.id),
            "mode": settings.effective_llm_provider.value,
            "demo_backend_measurement": settings.effective_llm_provider == LLMProvider.DEMO,
            "examples_per_run": len(examples),
            "budget": budget.as_dict(),
            "runs": artifacts,
            "comparison": comparison.as_dict(),
            "comparison_artifacts": {
                key: str(value) for key, value in asdict(comparison_paths).items()
            },
            "failure_attribution": str(attribution_path),
        }
        _atomic_json(output_dir / "evaluation_run.json", result)
        return result
    except BaseException as exc:
        category = (
            exc.category.value
            if isinstance(exc, InferenceError)
            else "manual_interrupt"
            if isinstance(exc, KeyboardInterrupt)
            else "unknown"
        )
        budget_stopped = category == "budget_exhausted"
        status = "budget_stopped" if budget_stopped else "paused"
        _sync_run(
            session_factory,
            run.id,
            budget,
            checkpoint_row=last_completed_row,
            status=status,
            error_category=category,
        )
        interrupted_result = {
            "evaluation_run_id": str(run.id),
            "dataset_hash": dataset_hash,
            "configuration_hash": configuration_hash,
            "completed_rows": last_completed_row,
            "total_rows": len(examples),
            "status": status,
            "error_category": category,
            "budget": budget.as_dict(),
            "resume_command": resumable_command,
            "resume_requires_budget_or_pricing_review": budget_stopped,
        }
        _atomic_json(output_dir / "checkpoint.json", interrupted_result)
        if isinstance(exc, (InferenceError, KeyboardInterrupt)):
            _atomic_json(output_dir / "evaluation_run.json", interrupted_result)
            return interrupted_result
        raise
    finally:
        for backend, _analyzer, _verifier in services.values():
            close = getattr(backend, "close", None)
            if callable(close):
                close()
        if catalog is not None:
            catalog.close()
        engine.dispose()
