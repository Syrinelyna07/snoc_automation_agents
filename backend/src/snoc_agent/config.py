"""Typed configuration loaded from environment variables or an optional .env file."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from snoc_agent.ai.provider import HFProviderPolicy, LLMProvider


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

    app_env: str = "development"
    log_level: str = "INFO"
    timezone: str = "UTC"
    database_url: str = "sqlite:///./snoc_agent.db"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    imap_mailbox: str = "INBOX"
    imap_ssl: bool = True
    imap_use_ssl: bool | None = None
    imap_poll_seconds: int = 30
    imap_max_message_bytes: int | None = None
    imap_search_criterion: str = "ALL"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    smtp_from_address: str = "snoc-agent@example.invalid"
    smtp_ssl: bool = False
    smtp_starttls: bool = False
    smtp_use_tls: bool | None = None
    smtp_max_retries: int = 5

    authorized_senders: str = ""
    escalation_recipient: str = "human-support@example.invalid"
    ldap_enabled: bool = False
    ldap_url: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    ldap_allowed_groups: str = ""

    llm_provider: LLMProvider | None = None
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
    analyzer_llm_base_url: str = ""
    analyzer_llm_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    analyzer_llm_model: str = ""
    analyzer_llm_endpoint: str = "/v1/chat/completions"
    verifier_llm_base_url: str = ""
    verifier_llm_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    verifier_llm_model: str = ""
    verifier_llm_endpoint: str = "/v1/chat/completions"
    llm_connect_timeout_seconds: float = 5.0
    llm_read_timeout_seconds: float = 60.0
    llm_max_output_tokens: int = 1200
    llm_response_format_mode: str = "auto"
    vllm_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    vllm_qwen_base_url: str = ""
    vllm_qwen_model: str = ""
    vllm_gemma_base_url: str = ""
    vllm_gemma_model: str = ""
    vllm_analyzer_deployment: str = "qwen"
    vllm_verifier_deployment: str = "gemma"
    vllm_request_timeout_seconds: float | None = None
    vllm_max_retries: int | None = None
    vllm_retry_base_seconds: float = 2.0
    vllm_use_json_schema: bool = True
    vllm_allow_json_object_fallback: bool = True
    vllm_allow_prompt_json_fallback: bool = True
    vllm_max_output_tokens_analyzer: int | None = None
    vllm_max_output_tokens_verifier: int | None = None
    sqlcoder_enabled: bool = False
    sqlcoder_base_url: str = ""
    sqlcoder_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    sqlcoder_model: str = ""
    sqlcoder_endpoint: str = "/v1/completions"

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
    business_api_bearer_token: SecretStr = Field(default_factory=lambda: SecretStr(""))
    business_api_timeout_seconds: float = 15.0
    business_api_max_retries: int = 2
    business_api_idempotency_guaranteed: bool = False
    business_api_vpn_path: str = "/create-account"
    business_api_otp_path: str = "/update-otp/{pdv_code}/{new_phone}"
    business_api_unblock_path: str = "/unlock-account/{pdv_code}"
    business_api_reset_path: str = "/reset-password/{pdv_code}"
    business_api_create_vpn_path: str = ""
    business_api_update_otp_path: str = ""
    business_api_unlock_account_path: str = ""
    business_api_reset_password_path: str = ""
    business_api_vpn_allowed_additional_fields: str = ""
    dry_run: bool = True
    auto_execution_enabled: bool = False
    business_api_idempotency_header: str = "Idempotency-Key"

    pdv_pattern: str = r"^\d{8}$"
    phone_pattern: str = r"^\+?\d{9,15}$"
    max_clarification_rounds: int = 1
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
    max_context_characters: int | None = None
    require_verifier: bool = True
    require_direct_evidence: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allowed_origins: str = ""
    auth_jwt_issuer: str = ""
    auth_jwt_audience: str = ""
    auth_jwt_public_key: SecretStr = Field(default_factory=lambda: SecretStr(""))

    @field_validator("pdv_pattern", "phone_pattern")
    @classmethod
    def valid_regex(cls, value: str) -> str:
        re.compile(value)
        return value

    @field_validator("imap_search_criterion")
    @classmethod
    def safe_imap_search(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 500 or "\r" in value or "\n" in value:
            raise ValueError("IMAP_SEARCH_CRITERION is invalid")
        return value

    @field_validator("vllm_analyzer_deployment", "vllm_verifier_deployment")
    @classmethod
    def known_vllm_deployment(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in {"qwen", "gemma"}:
            raise ValueError("vLLM deployment must be qwen or gemma")
        return normalized

    @field_validator(
        "imap_poll_seconds",
        "llm_max_retries",
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
        "evaluation_checkpoint_every",
        "max_raw_email_bytes",
        "max_text_part_bytes",
        "max_html_part_bytes",
        "max_attachment_count",
        "max_attachment_bytes",
        "max_model_context_characters",
        "max_latest_message_characters",
        "max_relevant_thread_characters",
        "llm_max_output_tokens",
        "database_pool_size",
        "smtp_max_retries",
        "api_port",
    )
    @classmethod
    def positive_integer(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be at least one")
        return value

    @field_validator(
        "vllm_max_output_tokens_analyzer",
        "vllm_max_output_tokens_verifier",
        "imap_max_message_bytes",
        "max_context_characters",
    )
    @classmethod
    def positive_optional_integer(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("must be at least one")
        return value

    @field_validator("vllm_max_retries")
    @classmethod
    def non_negative_optional_integer(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("must be non-negative")
        return value

    @field_validator("vllm_request_timeout_seconds")
    @classmethod
    def positive_optional_duration(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("must be greater than zero")
        return value

    @field_validator("max_model_context_characters")
    @classmethod
    def viable_model_context_limit(cls, value: int) -> int:
        if value < 256:
            raise ValueError("MAX_MODEL_CONTEXT_CHARACTERS must be at least 256")
        return value

    @field_validator(
        "llm_timeout_seconds",
        "hf_request_timeout_seconds",
        "hf_retry_base_seconds",
        "vllm_retry_base_seconds",
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
        "business_api_create_vpn_path",
        "business_api_update_otp_path",
        "business_api_unlock_account_path",
        "business_api_reset_password_path",
    )
    @classmethod
    def endpoint_path(cls, value: str) -> str:
        if not value:
            return value
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
        if self.auto_execution_enabled and self.dry_run:
            raise ValueError("AUTO_EXECUTION_ENABLED=true requires DRY_RUN=false")
        if not self.dry_run and not self.auto_execution_enabled:
            raise ValueError("DRY_RUN=false requires explicit AUTO_EXECUTION_ENABLED=true")
        if not self.dry_run and not self.business_api_base_url:
            raise ValueError("BUSINESS_API_BASE_URL is required when DRY_RUN=false")
        if not self.dry_run and not self.smtp_host:
            raise ValueError("SMTP_HOST is required when DRY_RUN=false")
        if not self.dry_run:
            provider = self.effective_llm_provider
            if provider == LLMProvider.DEMO:
                raise ValueError("a real LLM provider is required when DRY_RUN=false")
            if provider in {LLMProvider.OPENAI_COMPATIBLE, LLMProvider.VLLM} and not (
                self.effective_analyzer_base_url and self.effective_verifier_base_url
            ):
                raise ValueError("Analyzer and verifier LLM base URLs are required in live mode")
            if provider == LLMProvider.HUGGINGFACE and not self.effective_hf_token:
                raise ValueError("HF_TOKEN is required for Hugging Face inference")
        if self.smtp_ssl and self.smtp_starttls:
            raise ValueError("SMTP_SSL and SMTP_STARTTLS cannot both be enabled")
        if self.hf_stop_before_budget_usd > self.hf_run_budget_usd:
            raise ValueError("HF_STOP_BEFORE_BUDGET_USD cannot exceed HF_RUN_BUDGET_USD")
        for endpoint in (
            self.analyzer_llm_endpoint,
            self.verifier_llm_endpoint,
            self.sqlcoder_endpoint,
        ):
            if (
                not endpoint.startswith("/")
                or "://" in endpoint
                or "\r" in endpoint
                or "\n" in endpoint
            ):
                raise ValueError("LLM endpoints must be safe absolute-path references")
        if self.sqlcoder_enabled and (not self.sqlcoder_base_url or not self.sqlcoder_model):
            raise ValueError(
                "SQLCODER_BASE_URL and SQLCODER_MODEL are required when SQLCODER_ENABLED=true"
            )
        if self.app_env.casefold() in {"production", "prod"} and not (
            self.auth_jwt_issuer
            and self.auth_jwt_audience
            and self.auth_jwt_public_key.get_secret_value()
        ):
            raise ValueError("JWT issuer, audience, and public key are required in production")
        return self

    @property
    def effective_llm_provider(self) -> LLMProvider:
        if self.llm_provider is not None:
            return self.llm_provider
        return (
            LLMProvider.OPENAI_COMPATIBLE
            if self.llm_base_url
            or self.analyzer_llm_base_url
            or self.verifier_llm_base_url
            or self.vllm_qwen_base_url
            or self.vllm_gemma_base_url
            else LLMProvider.DEMO
        )

    @property
    def effective_hf_token(self) -> str:
        return self.hf_token.get_secret_value() or self.llm_api_key.get_secret_value()

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
    def effective_analyzer_base_url(self) -> str:
        deployment_url = (
            self.vllm_qwen_base_url
            if self.vllm_analyzer_deployment == "qwen"
            else self.vllm_gemma_base_url
        )
        return self.analyzer_llm_base_url or deployment_url or self.llm_base_url

    @property
    def effective_verifier_base_url(self) -> str:
        deployment_url = (
            self.vllm_qwen_base_url
            if self.vllm_verifier_deployment == "qwen"
            else self.vllm_gemma_base_url
        )
        return self.verifier_llm_base_url or deployment_url or self.llm_base_url

    @property
    def effective_analyzer_api_key(self) -> str:
        return (
            self.analyzer_llm_api_key.get_secret_value()
            or self.vllm_api_key.get_secret_value()
            or self.llm_api_key.get_secret_value()
        )

    @property
    def effective_verifier_api_key(self) -> str:
        return (
            self.verifier_llm_api_key.get_secret_value()
            or self.vllm_api_key.get_secret_value()
            or self.llm_api_key.get_secret_value()
        )

    @property
    def effective_analyzer_model(self) -> str:
        deployment_model = (
            self.vllm_qwen_model
            if self.vllm_analyzer_deployment == "qwen"
            else self.vllm_gemma_model
        )
        return self.analyzer_llm_model or deployment_model or self.analyzer_model

    @property
    def effective_verifier_model(self) -> str:
        deployment_model = (
            self.vllm_qwen_model
            if self.vllm_verifier_deployment == "qwen"
            else self.vllm_gemma_model
        )
        return self.verifier_llm_model or deployment_model or self.verifier_model

    @property
    def effective_vllm_timeout_seconds(self) -> float:
        return self.vllm_request_timeout_seconds or self.llm_read_timeout_seconds

    @property
    def effective_vllm_max_retries(self) -> int:
        return self.vllm_max_retries if self.vllm_max_retries is not None else self.llm_max_retries

    @property
    def effective_analyzer_max_output_tokens(self) -> int:
        return self.vllm_max_output_tokens_analyzer or self.llm_max_output_tokens

    @property
    def effective_verifier_max_output_tokens(self) -> int:
        return self.vllm_max_output_tokens_verifier or self.llm_max_output_tokens

    @property
    def effective_business_api_token(self) -> str:
        return (
            self.business_api_bearer_token.get_secret_value()
            or self.business_api_token.get_secret_value()
        )

    @property
    def effective_imap_ssl(self) -> bool:
        return self.imap_ssl if self.imap_use_ssl is None else self.imap_use_ssl

    @property
    def effective_smtp_ssl(self) -> bool:
        return self.smtp_ssl and self.smtp_use_tls is not True

    @property
    def effective_smtp_starttls(self) -> bool:
        return self.smtp_starttls if self.smtp_use_tls is None else self.smtp_use_tls

    @property
    def effective_max_raw_email_bytes(self) -> int:
        """Return the strictest configured raw-message size limit."""
        if self.imap_max_message_bytes is None:
            return self.max_raw_email_bytes

        return min(
            self.max_raw_email_bytes,
            self.imap_max_message_bytes,
        )

    @property
    def effective_max_context_characters(self) -> int:
        return self.max_context_characters or self.max_model_context_characters

    @property
    def effective_business_api_vpn_path(self) -> str:
        return self.business_api_create_vpn_path or self.business_api_vpn_path

    @property
    def effective_business_api_otp_path(self) -> str:
        return self.business_api_update_otp_path or self.business_api_otp_path

    @property
    def effective_business_api_unblock_path(self) -> str:
        return self.business_api_unlock_account_path or self.business_api_unblock_path

    @property
    def effective_business_api_reset_path(self) -> str:
        return self.business_api_reset_password_path or self.business_api_reset_path

    @property
    def cors_origin_set(self) -> set[str]:
        return {value.strip() for value in self.cors_allowed_origins.split(",") if value.strip()}


def load_settings(env_file: Path | None = None, **overrides: Any) -> Settings:
    """Load settings while allowing tests and CLI callers to inject overrides."""

    if env_file is None:
        return Settings(**overrides)
    return Settings(_env_file=env_file, **overrides)  # type: ignore[call-arg]
