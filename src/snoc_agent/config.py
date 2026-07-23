"""Typed configuration loaded from environment variables or an optional .env file."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from snoc_agent.ai.provider import HFProviderPolicy, LLMProvider, VLLMDeploymentName
from snoc_agent.ai.vllm_deployments import VLLMDeployment


class Settings(BaseSettings):
    """Application settings.

    Secrets are represented with ``SecretStr`` so accidental repr/logging does not expose them.
    Empty endpoints select local fake/dry-run adapters in CLI replay mode.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    database_url: str = "sqlite:///./snoc_agent.db"
    workflow_engine: Literal["legacy", "langgraph"] = "legacy"

    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    imap_mailbox: str = "INBOX"
    imap_ssl: bool = True
    imap_poll_seconds: int = 30
    imap_search_criterion: str = "ALL"

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    smtp_from_address: str = "snoc-agent@example.invalid"
    system_email_address: str = ""
    smtp_ssl: bool = True
    smtp_starttls: bool = False

    authorized_senders: str = ""
    escalation_recipient: str = "human-support@example.invalid"
    sender_imap_mailbox: str = "[Gmail]/All Mail"

    llm_provider: LLMProvider | None = None
    analyzer_provider: LLMProvider | None = None
    verifier_provider: LLMProvider | None = None
    llm_base_url: str = ""
    llm_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    analyzer_model: str = "Qwen2.5-7B-Instruct"
    verifier_model: str = "Qwen3-8B"
    analyzer_temperature: float = 0.0
    verifier_temperature: float = 0.0
    analyzer_min_raw_confidence: float | None = None
    verifier_min_raw_confidence: float | None = None
    qwen3_enable_thinking: bool = False
    qwen3_send_thinking_parameter: bool = True
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    llm_supports_logprobs: bool = False
    llm_json_schema_mode: bool = True
    model_quantization: str = ""

    # Two independently hosted OpenAI-compatible vLLM deployments. The role
    # selectors are aliases, while model IDs remain the exact IDs advertised
    # by each deployment's /v1/models response.
    vllm_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    vllm_qwen_base_url: str = "https://qwen.example.com/v1"
    vllm_qwen_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    vllm_gemma_base_url: str = "https://gemma.example.com/v1"
    vllm_gemma_model: str = "google/gemma-4-12B-it"
    vllm_analyzer_deployment: VLLMDeploymentName = VLLMDeploymentName.GEMMA
    vllm_verifier_deployment: VLLMDeploymentName = VLLMDeploymentName.GEMMA
    vllm_request_timeout_seconds: float = 120.0
    vllm_max_retries: int = 2
    vllm_retry_base_seconds: float = 2.0
    vllm_use_json_schema: bool = True
    vllm_allow_json_object_fallback: bool = True
    vllm_allow_prompt_json_fallback: bool = True
    vllm_max_output_tokens_analyzer: int = 4096
    vllm_max_output_tokens_verifier: int = 4096
    run_vllm_live_tests: bool = False

    hf_token: SecretStr = Field(default_factory=lambda: SecretStr(""))
    # Empty provider-specific values deliberately fall through to the legacy
    # aliases below.  The effective properties then apply the safe HF defaults.
    hf_router_base_url: str = ""
    hf_analyzer_model: str = ""
    hf_verifier_model: str = ""
    hf_provider_policy: HFProviderPolicy = HFProviderPolicy.CHEAPEST
    hf_analyzer_provider: str = ""
    hf_verifier_provider: str = ""
    hf_routing_suffix_enabled: bool = True
    hf_request_timeout_seconds: float = 120.0
    hf_max_retries: int = 3
    hf_retry_base_seconds: float = 2.0
    hf_use_json_schema: bool = True
    hf_allow_json_object_fallback: bool = True
    hf_allow_prompt_json_fallback: bool = True
    hf_max_output_tokens_analyzer: int = 1200
    hf_max_output_tokens_verifier: int = 700
    hf_extra_body_json: str = "{}"
    hf_run_budget_usd: Decimal = Decimal("20")
    hf_stop_before_budget_usd: Decimal = Decimal("19")
    hf_require_budget_confirmation: bool = False
    hf_allow_unknown_cost: bool = True
    hf_model_list_cache_ttl_seconds: int = 300
    hf_model_list_cache_path: Path = Path("var/cache/hf_models.json")
    hf_live_test_max_cost_usd: Decimal = Decimal("0.10")
    run_hf_live_tests: bool = False
    evaluation_checkpoint_every: int = 10

    business_api_base_url: str = ""
    business_api_token: SecretStr = Field(default_factory=lambda: SecretStr(""))
    business_api_timeout_seconds: float = 15.0
    business_api_max_retries: int = 2
    business_api_idempotency_guaranteed: bool = False
    business_api_vpn_path: str = "/create-account"
    business_api_otp_path: str = "/update-otp/{pdv_code}/{new_phone}"
    business_api_unblock_path: str = "/unlock-account/{pdv_code}"
    business_api_reset_path: str = "/reset-password/{pdv_code}"
    business_api_vpn_allowed_additional_fields: str = ""
    dry_run: bool = True
    dry_run_send_emails: bool = False

    pdv_pattern: str = r"^\d{8}$"
    phone_pattern: str = r"^\+?\d{9,15}$"
    max_clarification_rounds: int = 1
    enforce_evidence_provenance: bool = True
    store_raw_eml: bool = True
    raw_eml_directory: Path = Path("var/raw_eml")
    log_email_content: bool = False
    max_raw_email_bytes: int = 10 * 1024 * 1024
    max_text_part_bytes: int = 1024 * 1024
    max_html_part_bytes: int = 2 * 1024 * 1024
    max_attachment_count: int = 20
    max_attachment_bytes: int = 5 * 1024 * 1024
    max_model_context_characters: int = 24_000
    max_latest_message_characters: int = 12_000
    max_relevant_thread_characters: int = 4_000

    @field_validator("pdv_pattern", "phone_pattern")
    @classmethod
    def valid_regex(cls, value: str) -> str:
        re.compile(value)
        return value

    @field_validator(
        "imap_poll_seconds",
        "llm_max_retries",
        "vllm_max_retries",
        "hf_max_retries",
        "business_api_max_retries",
        "max_clarification_rounds",
        "hf_model_list_cache_ttl_seconds",
    )
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be non-negative")
        return value

    @field_validator(
        "hf_max_output_tokens_analyzer",
        "hf_max_output_tokens_verifier",
        "vllm_max_output_tokens_analyzer",
        "vllm_max_output_tokens_verifier",
        "evaluation_checkpoint_every",
        "max_raw_email_bytes",
        "max_text_part_bytes",
        "max_html_part_bytes",
        "max_attachment_count",
        "max_attachment_bytes",
        "max_model_context_characters",
        "max_latest_message_characters",
        "max_relevant_thread_characters",
    )
    @classmethod
    def positive_integer(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least one")
        return value

    @field_validator("max_model_context_characters")
    @classmethod
    def viable_model_context_limit(cls, value: int) -> int:
        if value < 256:
            raise ValueError("MAX_MODEL_CONTEXT_CHARACTERS must be at least 256")
        return value

    @field_validator(
        "llm_timeout_seconds",
        "vllm_request_timeout_seconds",
        "vllm_retry_base_seconds",
        "hf_request_timeout_seconds",
        "hf_retry_base_seconds",
    )
    @classmethod
    def positive_duration(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value

    @field_validator("hf_run_budget_usd", "hf_stop_before_budget_usd", "hf_live_test_max_cost_usd")
    @classmethod
    def non_negative_money(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value < 0:
            raise ValueError("cost limits must be non-negative")
        return value

    @field_validator("hf_extra_body_json")
    @classmethod
    def valid_extra_body(cls, value: str) -> str:
        try:
            parsed = json.loads(value or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("HF_EXTRA_BODY_JSON must contain valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("HF_EXTRA_BODY_JSON must contain one JSON object")
        reserved = {
            "model",
            "messages",
            "response_format",
            "temperature",
            "max_tokens",
            "stream",
            "authorization",
        }
        collision = sorted(reserved.intersection(key.casefold() for key in parsed))
        if collision:
            raise ValueError(
                "HF_EXTRA_BODY_JSON cannot override reserved fields: " + ", ".join(collision)
            )
        return value or "{}"

    @field_validator("analyzer_min_raw_confidence", "verifier_min_raw_confidence")
    @classmethod
    def optional_confidence_threshold(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1:
            raise ValueError("confidence threshold must be between 0 and 1")
        return value

    @field_validator(
        "business_api_vpn_path",
        "business_api_otp_path",
        "business_api_unblock_path",
        "business_api_reset_path",
    )
    @classmethod
    def endpoint_path(cls, value: str) -> str:
        if not value.startswith("/") or "://" in value or "\r" in value or "\n" in value:
            raise ValueError("business API endpoint must be a safe absolute-path reference")
        return value

    @field_validator("business_api_vpn_allowed_additional_fields")
    @classmethod
    def safe_vpn_additional_field_names(cls, value: str) -> str:
        reserved = {"pdv_code", "phone", "idempotency_key"}
        names = [name.strip() for name in value.split(",") if name.strip()]
        invalid = [
            name
            for name in names
            if name in reserved or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", name) is None
        ]
        if invalid:
            raise ValueError(
                "VPN additional field names must be safe, non-reserved identifiers: "
                + ", ".join(sorted(invalid))
            )
        return ",".join(dict.fromkeys(names))

    @model_validator(mode="after")
    def live_execution_has_endpoint(self) -> Settings:
        if not self.dry_run and not self.business_api_base_url:
            raise ValueError("BUSINESS_API_BASE_URL is required when DRY_RUN=false")
        if not self.dry_run and not self.smtp_host:
            raise ValueError("SMTP_HOST is required when DRY_RUN=false")
        if not self.dry_run:
            provider = self.effective_llm_provider
            if provider == LLMProvider.DEMO:
                raise ValueError("a real LLM provider is required when DRY_RUN=false")
            if provider == LLMProvider.OPENAI_COMPATIBLE and not self.llm_base_url:
                raise ValueError("LLM_BASE_URL is required when DRY_RUN=false")
            if provider == LLMProvider.HUGGINGFACE and not self.effective_hf_token:
                raise ValueError("HF_TOKEN is required for Hugging Face inference")
            if provider == LLMProvider.VLLM and not self.effective_vllm_api_key:
                raise ValueError("VLLM_API_KEY is required for vLLM inference")
        if self.smtp_ssl and self.smtp_starttls:
            raise ValueError("SMTP_SSL and SMTP_STARTTLS cannot both be enabled")
        if self.hf_stop_before_budget_usd > self.hf_run_budget_usd:
            raise ValueError("HF_STOP_BEFORE_BUDGET_USD cannot exceed HF_RUN_BUDGET_USD")
        return self

    @property
    def effective_llm_provider(self) -> LLMProvider:
        if self.llm_provider is not None:
            return self.llm_provider
        return LLMProvider.OPENAI_COMPATIBLE if self.llm_base_url else LLMProvider.DEMO

    @property
    def effective_analyzer_provider(self) -> LLMProvider:
        if self.analyzer_provider is not None:
            return self.analyzer_provider
        return self.effective_llm_provider

    @property
    def effective_verifier_provider(self) -> LLMProvider:
        if self.verifier_provider is not None:
            return self.verifier_provider
        return self.effective_llm_provider

    @property
    def effective_hf_token(self) -> str:
        return self.hf_token.get_secret_value() or self.llm_api_key.get_secret_value()

    @property
    def effective_vllm_api_key(self) -> str:
        return self.vllm_api_key.get_secret_value() or self.llm_api_key.get_secret_value()

    @property
    def vllm_deployments(self) -> tuple[VLLMDeployment, VLLMDeployment]:
        return (
            VLLMDeployment(
                VLLMDeploymentName.QWEN,
                self.vllm_qwen_base_url,
                self.vllm_qwen_model,
            ),
            VLLMDeployment(
                VLLMDeploymentName.GEMMA,
                self.vllm_gemma_base_url,
                self.vllm_gemma_model,
            ),
        )

    @property
    def effective_hf_base_url(self) -> str:
        return self.hf_router_base_url or self.llm_base_url or "https://router.huggingface.co/v1"

    @property
    def effective_hf_analyzer_model(self) -> str:
        return self.hf_analyzer_model or self.analyzer_model or "Qwen/Qwen2.5-7B-Instruct"

    @property
    def effective_hf_verifier_model(self) -> str:
        return self.hf_verifier_model or self.verifier_model or "Qwen/Qwen3-8B"

    @property
    def hf_extra_body(self) -> dict[str, Any]:
        parsed = json.loads(self.hf_extra_body_json or "{}")
        return dict(parsed)

    @property
    def authorized_sender_set(self) -> set[str]:
        return {
            address.strip().casefold()
            for address in self.authorized_senders.split(",")
            if address.strip()
        }

    @property
    def vpn_allowed_additional_field_set(self) -> frozenset[str]:
        return frozenset(
            name.strip()
            for name in self.business_api_vpn_allowed_additional_fields.split(",")
            if name.strip()
        )

    @property
    def outbound_email_enabled(self) -> bool:
        """Allow real email delivery independently from telecom-operation simulation.

        DRY_RUN always keeps business operations on the mock API. Email delivery remains
        disabled by default in that mode, but production-like mailbox tests may explicitly
        opt in without enabling the real business API.
        """

        return not self.dry_run or self.dry_run_send_emails

    @property
    def effective_system_email_address(self) -> str:
        return self.system_email_address or self.smtp_from_address


def load_settings(env_file: Path | None = None, **overrides: Any) -> Settings:
    """Load settings while allowing tests and CLI callers to inject overrides."""

    if env_file is None:
        return Settings(**overrides)
    return Settings(_env_file=env_file, **overrides)  # type: ignore[call-arg]
