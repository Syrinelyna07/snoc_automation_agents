"""Constructor-based dependency graph shared by CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, select

from snoc_agent.ai.analyzer import EmailAnalyzer
from snoc_agent.ai.backend import GenerationConfig, LLMBackend
from snoc_agent.ai.cost import BudgetTracker
from snoc_agent.ai.demo_backend import DemoLLMBackend
from snoc_agent.ai.hf_discovery import HFModelCatalog
from snoc_agent.ai.huggingface_backend import HuggingFaceInferenceBackend
from snoc_agent.ai.model_registry import canonical_hf_model_id
from snoc_agent.ai.openai_compatible_backend import OpenAICompatibleBackend
from snoc_agent.ai.provider import LLMProvider, resolve_hf_model_route
from snoc_agent.ai.routing_backend import RoleRoutingBackend
from snoc_agent.ai.verifier import SemanticVerifier
from snoc_agent.business_api import (
    BusinessAPI,
    BusinessAPIEndpointPaths,
    HttpBusinessAPI,
    MockBusinessAPI,
)
from snoc_agent.config import Settings
from snoc_agent.db import create_engine_and_session, create_schema
from snoc_agent.db.models import ModelRun
from snoc_agent.db.session import SessionFactory, session_scope
from snoc_agent.mail.fake_mailbox import FakeSMTPTransport
from snoc_agent.mail.interfaces import SMTPTransport
from snoc_agent.mail.smtp_client import RealSMTPTransport
from snoc_agent.workflow.authorizer import StaticSenderAuthorizer
from snoc_agent.workflow.decision_engine import HybridDecisionEngine
from snoc_agent.workflow.execution_service import ExecutionService
from snoc_agent.workflow.inbound_processor import InboundProcessor
from snoc_agent.workflow.outbox_service import OutboxService


@dataclass(slots=True)
class Runtime:
    engine: Engine
    session_factory: SessionFactory
    backend: LLMBackend
    business_api: BusinessAPI
    smtp_transport: SMTPTransport
    processor: InboundProcessor
    outbox: OutboxService
    model_catalog: HFModelCatalog | None = None
    budget_tracker: BudgetTracker | None = None


def build_model_services(
    settings: Settings,
    *,
    analyzer_model: str | None = None,
    verifier_model: str | None = None,
    budget_tracker: BudgetTracker | None = None,
    pricing_resolver: Any | None = None,
) -> tuple[LLMBackend, EmailAnalyzer, SemanticVerifier]:
    backend: LLMBackend
    provider = settings.effective_llm_provider
    analyzer_base = analyzer_model or (
        settings.effective_hf_analyzer_model
        if provider == LLMProvider.HUGGINGFACE
        else settings.effective_analyzer_model
    )
    verifier_base = verifier_model or (
        settings.effective_hf_verifier_model
        if provider == LLMProvider.HUGGINGFACE
        else settings.effective_verifier_model
    )
    analyzer_routed = analyzer_base
    verifier_routed = verifier_base
    if provider == LLMProvider.HUGGINGFACE:
        if not settings.effective_hf_token:
            raise ValueError(
                "HF_TOKEN is required whenever LLM_PROVIDER=huggingface, including DRY_RUN"
            )
        analyzer_base = canonical_hf_model_id(analyzer_base)
        verifier_base = canonical_hf_model_id(verifier_base)
        analyzer_routed = resolve_hf_model_route(
            analyzer_base,
            settings.hf_analyzer_provider or None,
            settings.hf_provider_policy,
            settings.hf_routing_suffix_enabled,
        ).routed_model_id
        verifier_routed = resolve_hf_model_route(
            verifier_base,
            settings.hf_verifier_provider or None,
            settings.hf_provider_policy,
            settings.hf_routing_suffix_enabled,
        ).routed_model_id
        backend = HuggingFaceInferenceBackend(
            base_url=settings.effective_hf_base_url,
            api_key=settings.effective_hf_token,
            timeout_seconds=settings.hf_request_timeout_seconds,
            budget_tracker=budget_tracker,
            pricing_resolver=pricing_resolver,
        )
    elif provider in {LLMProvider.OPENAI_COMPATIBLE, LLMProvider.VLLM}:
        analyzer_backend = OpenAICompatibleBackend(
            base_url=settings.effective_analyzer_base_url,
            api_key=settings.effective_analyzer_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
            connect_timeout_seconds=settings.llm_connect_timeout_seconds,
            read_timeout_seconds=settings.effective_vllm_timeout_seconds,
            endpoint=settings.analyzer_llm_endpoint,
            backend_name=provider.value,
        )
        if (
            settings.effective_verifier_base_url == settings.effective_analyzer_base_url
            and settings.effective_verifier_api_key == settings.effective_analyzer_api_key
            and settings.verifier_llm_endpoint == settings.analyzer_llm_endpoint
        ):
            verifier_backend = analyzer_backend
        else:
            verifier_backend = OpenAICompatibleBackend(
                base_url=settings.effective_verifier_base_url,
                api_key=settings.effective_verifier_api_key,
                timeout_seconds=settings.llm_timeout_seconds,
                connect_timeout_seconds=settings.llm_connect_timeout_seconds,
                read_timeout_seconds=settings.effective_vllm_timeout_seconds,
                endpoint=settings.verifier_llm_endpoint,
                backend_name=provider.value,
            )
        backend = RoleRoutingBackend(
            analyzer_model=analyzer_routed,
            analyzer_backend=analyzer_backend,
            verifier_model=verifier_routed,
            verifier_backend=verifier_backend,
        )
    else:
        backend = DemoLLMBackend()
    analyzer = EmailAnalyzer(
        backend,
        GenerationConfig(
            model=analyzer_routed,
            base_model=analyzer_base,
            temperature=settings.analyzer_temperature,
            max_output_tokens=(
                settings.hf_max_output_tokens_analyzer
                if provider == LLMProvider.HUGGINGFACE
                else settings.effective_analyzer_max_output_tokens
            ),
            max_retries=(
                settings.hf_max_retries
                if provider == LLMProvider.HUGGINGFACE
                else settings.effective_vllm_max_retries
            ),
            retry_base_seconds=(
                settings.hf_retry_base_seconds
                if provider == LLMProvider.HUGGINGFACE
                else settings.vllm_retry_base_seconds
            ),
            supports_logprobs=settings.llm_supports_logprobs,
            enable_thinking=(
                settings.qwen3_enable_thinking
                if provider in {LLMProvider.OPENAI_COMPATIBLE, LLMProvider.VLLM}
                and settings.qwen3_send_thinking_parameter
                and "qwen3" in analyzer_base.casefold()
                else None
            ),
            use_json_schema=(
                settings.hf_use_json_schema
                if provider == LLMProvider.HUGGINGFACE
                else settings.vllm_use_json_schema
            ),
            allow_json_object_fallback=(
                settings.hf_allow_json_object_fallback
                if provider == LLMProvider.HUGGINGFACE
                else settings.vllm_allow_json_object_fallback
            ),
            allow_prompt_json_fallback=(
                settings.hf_allow_prompt_json_fallback
                if provider == LLMProvider.HUGGINGFACE
                else settings.vllm_allow_prompt_json_fallback
            ),
            quantization=settings.model_quantization or None,
            extra_body=settings.hf_extra_body if provider == LLMProvider.HUGGINGFACE else {},
        ),
    )
    verifier = SemanticVerifier(
        backend,
        GenerationConfig(
            model=verifier_routed,
            base_model=verifier_base,
            temperature=settings.verifier_temperature,
            max_output_tokens=(
                settings.hf_max_output_tokens_verifier
                if provider == LLMProvider.HUGGINGFACE
                else settings.effective_verifier_max_output_tokens
            ),
            max_retries=(
                settings.hf_max_retries
                if provider == LLMProvider.HUGGINGFACE
                else settings.effective_vllm_max_retries
            ),
            retry_base_seconds=(
                settings.hf_retry_base_seconds
                if provider == LLMProvider.HUGGINGFACE
                else settings.vllm_retry_base_seconds
            ),
            supports_logprobs=settings.llm_supports_logprobs,
            enable_thinking=(
                settings.qwen3_enable_thinking
                if provider in {LLMProvider.OPENAI_COMPATIBLE, LLMProvider.VLLM}
                and settings.qwen3_send_thinking_parameter
                and "qwen3" in verifier_base.casefold()
                else None
            ),
            use_json_schema=(
                settings.hf_use_json_schema
                if provider == LLMProvider.HUGGINGFACE
                else settings.vllm_use_json_schema
            ),
            allow_json_object_fallback=(
                settings.hf_allow_json_object_fallback
                if provider == LLMProvider.HUGGINGFACE
                else settings.vllm_allow_json_object_fallback
            ),
            allow_prompt_json_fallback=(
                settings.hf_allow_prompt_json_fallback
                if provider == LLMProvider.HUGGINGFACE
                else settings.vllm_allow_prompt_json_fallback
            ),
            quantization=settings.model_quantization or None,
            extra_body=settings.hf_extra_body if provider == LLMProvider.HUGGINGFACE else {},
        ),
    )
    return backend, analyzer, verifier


def build_runtime(
    settings: Settings,
    *,
    replay_authorized_senders: set[str] | None = None,
    initialize_schema: bool = False,
) -> Runtime:
    engine, session_factory = create_engine_and_session(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    if initialize_schema:
        create_schema(engine)
    model_catalog: HFModelCatalog | None = None
    budget_tracker: BudgetTracker | None = None
    pricing_resolver = None
    if settings.effective_llm_provider == LLMProvider.HUGGINGFACE:
        if not settings.effective_hf_token:
            raise ValueError(
                "HF_TOKEN is required whenever LLM_PROVIDER=huggingface, including DRY_RUN"
            )
        model_catalog = HFModelCatalog(
            base_url=settings.effective_hf_base_url,
            token=settings.effective_hf_token,
            cache_path=settings.hf_model_list_cache_path,
            cache_ttl_seconds=settings.hf_model_list_cache_ttl_seconds,
            timeout_seconds=settings.hf_request_timeout_seconds,
            max_retries=settings.hf_max_retries,
            retry_base_seconds=settings.hf_retry_base_seconds,
        )

        def pricing_resolver(model_id: str, provider: str | None) -> dict[str, Any]:
            assert model_catalog is not None
            try:
                return model_catalog.pricing_for(model_id, provider)
            except (OSError, RuntimeError):
                # The paid response remains usable and is explicitly audited
                # as unknown cost if catalog metadata cannot be refreshed.
                return {}

        with session_scope(session_factory) as session:
            historical_runs = session.scalars(
                select(ModelRun).where(ModelRun.backend == LLMProvider.HUGGINGFACE.value)
            ).all()
        budget_tracker = BudgetTracker(
            budget_usd=settings.hf_run_budget_usd,
            stop_before_usd=settings.hf_stop_before_budget_usd,
            allow_unknown_cost=settings.hf_allow_unknown_cost,
            cost_so_far_usd=sum(
                (run.total_cost_usd for run in historical_runs if run.total_cost_usd is not None),
                start=Decimal("0"),
            ),
            request_count=sum(run.request_attempt_count for run in historical_runs),
            unknown_cost_request_count=sum(
                run.parse_attempt_count
                for run in historical_runs
                if run.total_cost_usd is None and run.parse_attempt_count > 0
            ),
            prompt_tokens=sum(run.prompt_tokens or 0 for run in historical_runs),
            completion_tokens=sum(run.completion_tokens or 0 for run in historical_runs),
        )
    backend, analyzer, verifier = build_model_services(
        settings,
        budget_tracker=budget_tracker,
        pricing_resolver=pricing_resolver,
    )
    endpoints = BusinessAPIEndpointPaths(
        vpn_access=settings.effective_business_api_vpn_path,
        otp_number_change=settings.effective_business_api_otp_path,
        account_unblock=settings.effective_business_api_unblock_path,
        password_reset=settings.effective_business_api_reset_path,
    )
    business_api: BusinessAPI
    if settings.dry_run:
        business_api = MockBusinessAPI(endpoints=endpoints)
    else:
        business_api = HttpBusinessAPI(
            base_url=settings.business_api_base_url,
            token=settings.effective_business_api_token,
            timeout_seconds=settings.business_api_timeout_seconds,
            max_retries=settings.business_api_max_retries,
            idempotency_guaranteed=settings.business_api_idempotency_guaranteed,
            idempotency_header=settings.business_api_idempotency_header,
            endpoints=endpoints,
        )
    authorized = set(settings.authorized_sender_set)
    if replay_authorized_senders:
        authorized.update(replay_authorized_senders)
    authorizer = StaticSenderAuthorizer(authorized)
    execution = ExecutionService(
        session_factory,
        business_api,
        vpn_allowed_additional_fields=settings.vpn_allowed_additional_field_set,
    )
    processor = InboundProcessor(
        session_factory=session_factory,
        settings=settings,
        analyzer=analyzer,
        verifier=verifier,
        authorizer=authorizer,
        decision_engine=HybridDecisionEngine(),
        execution_service=execution,
    )
    smtp_transport: SMTPTransport
    if settings.dry_run or not settings.smtp_host:
        smtp_transport = FakeSMTPTransport()
    else:
        smtp_transport = RealSMTPTransport(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value(),
            use_ssl=settings.effective_smtp_ssl,
            starttls=settings.effective_smtp_starttls,
        )
    outbox = OutboxService(
        session_factory,
        smtp_transport,
        sender=settings.smtp_from_address,
        max_retries=settings.smtp_max_retries,
    )
    return Runtime(
        engine=engine,
        session_factory=session_factory,
        backend=backend,
        business_api=business_api,
        smtp_transport=smtp_transport,
        processor=processor,
        outbox=outbox,
        model_catalog=model_catalog,
        budget_tracker=budget_tracker,
    )
