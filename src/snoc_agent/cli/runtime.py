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
from snoc_agent.ai.verifier import SemanticVerifier
from snoc_agent.ai.vllm_deployments import VLLMDeployment, resolve_vllm_deployment
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
    analyzer_backend: LLMBackend
    verifier_backend: LLMBackend
    business_api: BusinessAPI
    smtp_transport: SMTPTransport
    processor: InboundProcessor | Any
    legacy_processor: InboundProcessor
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
) -> tuple[LLMBackend, LLMBackend, EmailAnalyzer, SemanticVerifier]:
    analyzer_provider = settings.effective_analyzer_provider
    verifier_provider = settings.effective_verifier_provider

    def _stage_model(
        provider: LLMProvider,
        override: str | None,
        *,
        configured_model: str,
        hf_model: str,
        hf_provider: str,
        vllm_deployment: str,
    ) -> tuple[str, str, VLLMDeployment | None]:
        if provider == LLMProvider.VLLM:
            if not settings.effective_vllm_api_key:
                raise ValueError(
                    "VLLM_API_KEY is required whenever LLM_PROVIDER=vllm, including DRY_RUN"
                )
            deployment = resolve_vllm_deployment(
                override or vllm_deployment,
                settings.vllm_deployments,
            )
            return deployment.model_id, deployment.model_id, deployment
        if provider == LLMProvider.HUGGINGFACE:
            if not settings.effective_hf_token:
                raise ValueError(
                    "HF_TOKEN is required whenever LLM_PROVIDER=huggingface, including DRY_RUN"
                )
            base = canonical_hf_model_id(override or hf_model)
            routed = resolve_hf_model_route(
                base,
                hf_provider or None,
                settings.hf_provider_policy,
                settings.hf_routing_suffix_enabled,
            ).routed_model_id
            return base, routed, None
        base = override or configured_model
        return base, base, None

    analyzer_base, analyzer_routed, analyzer_deployment = _stage_model(
        analyzer_provider,
        analyzer_model,
        configured_model=settings.analyzer_model,
        hf_model=settings.effective_hf_analyzer_model,
        hf_provider=settings.hf_analyzer_provider,
        vllm_deployment=settings.vllm_analyzer_deployment.value,
    )
    verifier_base, verifier_routed, verifier_deployment = _stage_model(
        verifier_provider,
        verifier_model,
        configured_model=settings.verifier_model,
        hf_model=settings.effective_hf_verifier_model,
        hf_provider=settings.hf_verifier_provider,
        vllm_deployment=settings.vllm_verifier_deployment.value,
    )

    def _build_backend(
        provider: LLMProvider,
        deployment: VLLMDeployment | None,
    ) -> LLMBackend:
        if provider == LLMProvider.HUGGINGFACE:
            return HuggingFaceInferenceBackend(
                base_url=settings.effective_hf_base_url,
                api_key=settings.effective_hf_token,
                timeout_seconds=settings.hf_request_timeout_seconds,
                budget_tracker=budget_tracker,
                pricing_resolver=pricing_resolver,
            )
        if provider == LLMProvider.VLLM:
            if deployment is None:
                raise RuntimeError("vLLM provider requires a resolved deployment")
            return OpenAICompatibleBackend(
                base_url=deployment.base_url,
                api_key=settings.effective_vllm_api_key,
                timeout_seconds=settings.vllm_request_timeout_seconds,
                backend_name=LLMProvider.VLLM.value,
                reported_provider_fallback=deployment.name.value,
                send_thinking_parameters=False,
                budget_tracker=budget_tracker,
            )
        if provider == LLMProvider.OPENAI_COMPATIBLE:
            return OpenAICompatibleBackend(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key.get_secret_value(),
                timeout_seconds=settings.llm_timeout_seconds,
            )
        return DemoLLMBackend()

    analyzer_backend = _build_backend(analyzer_provider, analyzer_deployment)
    verifier_backend = _build_backend(verifier_provider, verifier_deployment)

    def _generation_config(
        *,
        stage: str,
        provider: LLMProvider,
        base_model: str,
        resolved_model: str,
    ) -> GenerationConfig:
        if provider == LLMProvider.HUGGINGFACE:
            max_tokens = (
                settings.hf_max_output_tokens_analyzer
                if stage == "analyzer"
                else settings.hf_max_output_tokens_verifier
            )
            retries = settings.hf_max_retries
            retry_base = settings.hf_retry_base_seconds
            use_schema = settings.hf_use_json_schema
            allow_object = settings.hf_allow_json_object_fallback
            allow_prompt = settings.hf_allow_prompt_json_fallback
            extra_body = settings.hf_extra_body
        elif provider == LLMProvider.VLLM:
            max_tokens = (
                settings.vllm_max_output_tokens_analyzer
                if stage == "analyzer"
                else settings.vllm_max_output_tokens_verifier
            )
            retries = settings.vllm_max_retries
            retry_base = settings.vllm_retry_base_seconds
            use_schema = settings.vllm_use_json_schema
            allow_object = settings.vllm_allow_json_object_fallback
            allow_prompt = settings.vllm_allow_prompt_json_fallback
            extra_body = {}
        else:
            max_tokens = None
            retries = settings.llm_max_retries
            retry_base = 2.0
            use_schema = settings.llm_json_schema_mode
            allow_object = False
            allow_prompt = False
            extra_body = {}
        temperature = (
            settings.analyzer_temperature if stage == "analyzer" else settings.verifier_temperature
        )
        return GenerationConfig(
            model=resolved_model,
            base_model=base_model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            max_retries=retries,
            retry_base_seconds=retry_base,
            supports_logprobs=settings.llm_supports_logprobs,
            enable_thinking=(
                settings.qwen3_enable_thinking
                if provider == LLMProvider.OPENAI_COMPATIBLE
                and settings.qwen3_send_thinking_parameter
                and "qwen3" in base_model.casefold()
                else None
            ),
            use_json_schema=use_schema,
            allow_json_object_fallback=allow_object,
            allow_prompt_json_fallback=allow_prompt,
            quantization=settings.model_quantization or None,
            extra_body=extra_body,
        )

    analyzer = EmailAnalyzer(
        analyzer_backend,
        _generation_config(
            stage="analyzer",
            provider=analyzer_provider,
            base_model=analyzer_base,
            resolved_model=analyzer_routed,
        ),
    )
    verifier = SemanticVerifier(
        verifier_backend,
        _generation_config(
            stage="verifier",
            provider=verifier_provider,
            base_model=verifier_base,
            resolved_model=verifier_routed,
        ),
    )
    return analyzer_backend, verifier_backend, analyzer, verifier


def build_runtime(
    settings: Settings,
    *,
    replay_authorized_senders: set[str] | None = None,
    initialize_schema: bool = False,
) -> Runtime:
    engine, session_factory = create_engine_and_session(settings.database_url)
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
    analyzer_backend, verifier_backend, analyzer, verifier = build_model_services(
        settings,
        budget_tracker=budget_tracker,
        pricing_resolver=pricing_resolver,
    )
    endpoints = BusinessAPIEndpointPaths(
        vpn_access=settings.business_api_vpn_path,
        otp_number_change=settings.business_api_otp_path,
        account_unblock=settings.business_api_unblock_path,
        password_reset=settings.business_api_reset_path,
    )
    business_api: BusinessAPI
    if settings.dry_run:
        business_api = MockBusinessAPI(endpoints=endpoints)
    else:
        business_api = HttpBusinessAPI(
            base_url=settings.business_api_base_url,
            token=settings.business_api_token.get_secret_value(),
            timeout_seconds=settings.business_api_timeout_seconds,
            max_retries=settings.business_api_max_retries,
            idempotency_guaranteed=settings.business_api_idempotency_guaranteed,
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
    legacy_processor = InboundProcessor(
        session_factory=session_factory,
        settings=settings,
        analyzer=analyzer,
        verifier=verifier,
        authorizer=authorizer,
        decision_engine=HybridDecisionEngine(),
        execution_service=execution,
    )
    processor: InboundProcessor | Any = legacy_processor
    if settings.workflow_engine == "langgraph":
        from snoc_agent.graph import LangGraphInboundProcessor

        processor = LangGraphInboundProcessor(legacy_processor)
    smtp_transport: SMTPTransport
    if (settings.dry_run and not settings.dry_run_send_emails) or not settings.smtp_host:
        smtp_transport = FakeSMTPTransport()
    else:
        smtp_transport = RealSMTPTransport(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value(),
            use_ssl=settings.smtp_ssl,
            starttls=settings.smtp_starttls,
        )
    outbox = OutboxService(
        session_factory,
        smtp_transport,
        sender=settings.smtp_from_address,
    )
    return Runtime(
        engine=engine,
        session_factory=session_factory,
        analyzer_backend=analyzer_backend,
        verifier_backend=verifier_backend,
        business_api=business_api,
        smtp_transport=smtp_transport,
        processor=processor,
        legacy_processor=legacy_processor,
        outbox=outbox,
        model_catalog=model_catalog,
        budget_tracker=budget_tracker,
    )
