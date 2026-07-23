"""Provider selection and Hugging Face model-route resolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LLMProvider(StrEnum):
    DEMO = "demo"
    VLLM = "vllm"
    OPENAI_COMPATIBLE = "openai_compatible"
    HUGGINGFACE = "huggingface"


class HFProviderPolicy(StrEnum):
    FASTEST = "fastest"
    CHEAPEST = "cheapest"
    PREFERRED = "preferred"


class StructuredOutputMode(StrEnum):
    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    PROMPT_JSON = "prompt_json"


class CostBasis(StrEnum):
    EXACT = "exact"
    PROVIDER_REPORTED = "provider_reported"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ResolvedModelRoute:
    base_model_id: str
    routed_model_id: str
    route_suffix: str | None


def _strip_known_route(model_id: str) -> str:
    """Remove a final HF routing suffix while preserving organization/model colons."""

    value = model_id.strip()
    if ":" not in value:
        return value
    base, suffix = value.rsplit(":", 1)
    if base and suffix and "/" in base:
        return base
    return value


def resolve_hf_model_route(
    base_model_id: str,
    explicit_provider: str | None,
    provider_policy: HFProviderPolicy | str,
    suffix_enabled: bool = True,
) -> ResolvedModelRoute:
    """Resolve exactly one routed identifier; explicit providers take precedence."""

    base = _strip_known_route(base_model_id)
    if not base:
        raise ValueError("base model ID must not be empty")
    explicit = (explicit_provider or "").strip()
    suffix = explicit or str(provider_policy)
    policies = {policy.value for policy in HFProviderPolicy}
    if not explicit and suffix not in policies:
        raise ValueError("Hugging Face provider policy must be fastest, cheapest, or preferred")
    if suffix not in policies and not suffix.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Hugging Face provider route contains unsupported characters")
    if not suffix_enabled:
        return ResolvedModelRoute(base, base, None)
    return ResolvedModelRoute(base, f"{base}:{suffix}", suffix)
