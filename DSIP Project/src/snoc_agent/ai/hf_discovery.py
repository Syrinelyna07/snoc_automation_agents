"""Hugging Face router model discovery with a short-lived filesystem cache."""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx

from snoc_agent.ai.errors import InferenceError, InferenceErrorCategory, classify_http_failure


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return max(0.0, (parsed - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _explicitly_unavailable(value: object) -> bool:
    if value is False:
        return True
    if not isinstance(value, str):
        return False
    normalized = value.strip().casefold().replace("_", "-")
    return normalized in {
        "down",
        "disabled",
        "error",
        "failed",
        "inactive",
        "not-available",
        "offline",
        "unavailable",
    }


def _provider_name(row: dict[str, Any]) -> str:
    return str(row.get("provider") or row.get("name") or "").casefold().replace("_", "-")


def _structured_support(row: dict[str, Any]) -> bool | None:
    direct = row.get("supports_structured_output", row.get("supportsStructuredOutput"))
    if isinstance(direct, bool):
        return direct
    capabilities = row.get("capabilities")
    if isinstance(capabilities, dict):
        nested = capabilities.get("structured_output", capabilities.get("structured_outputs"))
        return nested if isinstance(nested, bool) else None
    return None


@dataclass(frozen=True, slots=True)
class HFModelInfo:
    model_id: str
    providers: tuple[dict[str, Any], ...] = ()
    context_length: int | None = None
    pricing: dict[str, Any] = field(default_factory=dict)
    availability: str | None = None
    supports_structured_output: bool | None = None
    latency: dict[str, Any] = field(default_factory=dict)
    throughput: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def explicitly_unavailable(self) -> bool:
        return _explicitly_unavailable(self.availability) or _explicitly_unavailable(
            self.raw.get("available")
        )

    def provider_names(self, *, available_only: bool = True) -> set[str]:
        rows = self.providers
        if available_only:
            rows = tuple(
                row
                for row in rows
                if not (
                    _explicitly_unavailable(row.get("status"))
                    or _explicitly_unavailable(row.get("availability"))
                    or _explicitly_unavailable(row.get("available"))
                )
            )
        return {_provider_name(row) for row in rows if _provider_name(row)}

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "providers": list(self.providers),
            "context_length": self.context_length,
            "pricing": self.pricing,
            "availability": self.availability,
            "supports_structured_output": self.supports_structured_output,
            "latency": self.latency,
            "throughput": self.throughput,
        }


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (str, int, float)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _model_info(item: dict[str, Any]) -> HFModelInfo:
    provider_rows = (
        item.get("providers")
        or item.get("inference_providers")
        or item.get("inferenceProviderMapping")
        or []
    )
    if isinstance(provider_rows, dict):
        providers = tuple(
            {"provider": name, **(dict(details) if isinstance(details, dict) else {})}
            for name, details in provider_rows.items()
        )
    elif isinstance(provider_rows, list):
        providers = tuple(
            dict(row) if isinstance(row, dict) else {"provider": str(row)}
            for row in provider_rows
            if isinstance(row, (str, dict))
        )
    else:
        providers = ()
    raw_pricing = item.get("pricing")
    pricing: dict[str, Any] = dict(raw_pricing) if isinstance(raw_pricing, dict) else {}
    if not pricing and len(providers) == 1 and isinstance(providers[0].get("pricing"), dict):
        pricing = dict(providers[0]["pricing"])
    context = (
        item.get("context_length") or item.get("max_context_length") or item.get("contextLength")
    )
    capabilities = item.get("capabilities")
    capabilities = capabilities if isinstance(capabilities, dict) else {}
    structured = item.get(
        "supports_structured_output",
        capabilities.get("structured_output", capabilities.get("structured_outputs")),
    )
    return HFModelInfo(
        model_id=str(item.get("id") or item.get("model_id") or ""),
        providers=providers,
        context_length=_int_or_none(context),
        pricing=dict(pricing),
        availability=(
            str(item.get("availability") or item.get("status"))
            if item.get("availability") is not None or item.get("status") is not None
            else None
        ),
        supports_structured_output=structured if isinstance(structured, bool) else None,
        latency=dict(item.get("latency") or {}) if isinstance(item.get("latency"), dict) else {},
        throughput=(
            dict(item.get("throughput") or {}) if isinstance(item.get("throughput"), dict) else {}
        ),
        raw=item,
    )


class HFModelCatalog:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        cache_path: Path,
        cache_ttl_seconds: int = 300,
        timeout_seconds: float = 120,
        max_retries: int = 3,
        retry_base_seconds: float = 2.0,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.cache_path = cache_path
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_retries = max(0, max_retries)
        self.retry_base_seconds = retry_base_seconds
        self._sleep = sleep
        self._jitter = jitter
        self._owns_client = client is None
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.client = client or httpx.Client(timeout=timeout_seconds, headers=headers)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _read_cache(self) -> list[dict[str, Any]] | None:
        try:
            cached = json.loads(self.cache_path.read_text(encoding="utf-8"))
            created_at = float(cached["created_at"])
            if cached.get("base_url") != self.base_url:
                return None
            if time.time() - created_at > self.cache_ttl_seconds:
                return None
            values = cached.get("models")
            return values if isinstance(values, list) else None
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write_cache(self, models: list[dict[str, Any]]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(f"{self.cache_path.suffix}.tmp")
        temporary.write_text(
            json.dumps(
                {"created_at": time.time(), "base_url": self.base_url, "models": models},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.cache_path)

    def _fetch_models(self) -> list[dict[str, Any]]:
        max_attempts = self.max_retries + 1
        for attempt in range(1, max_attempts + 1):
            error: InferenceError | None = None
            try:
                response = self.client.get(f"{self.base_url}/models")
            except httpx.TimeoutException as exc:
                error = InferenceError(
                    InferenceErrorCategory.TIMEOUT,
                    "Hugging Face model discovery timed out",
                )
                if attempt >= max_attempts:
                    raise error from exc
            except httpx.TransportError as exc:
                error = InferenceError(
                    InferenceErrorCategory.PROVIDER_UNAVAILABLE,
                    "Hugging Face model discovery transport failure",
                )
                if attempt >= max_attempts:
                    raise error from exc
            else:
                if response.is_error:
                    error = classify_http_failure(
                        response.status_code,
                        response.text,
                        retry_after_seconds=_retry_after(response),
                    )
                    if not error.retryable or attempt >= max_attempts:
                        raise error
                else:
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise InferenceError(
                            InferenceErrorCategory.UNKNOWN,
                            "Hugging Face /models returned invalid JSON",
                        ) from exc
                    values = payload.get("data", payload) if isinstance(payload, dict) else payload
                    if not isinstance(values, list):
                        raise InferenceError(
                            InferenceErrorCategory.UNKNOWN,
                            "Hugging Face /models returned an unexpected payload",
                        )
                    return [item for item in values if isinstance(item, dict)]
            if error is not None:
                delay = error.retry_after_seconds
                if delay is None:
                    delay = self.retry_base_seconds * (2 ** (attempt - 1))
                    delay += delay * 0.25 * self._jitter()
                self._sleep(delay)
        raise InferenceError(InferenceErrorCategory.UNKNOWN, "model discovery failed")

    def list_models(self, *, refresh: bool = False) -> list[HFModelInfo]:
        try:
            raw_models = None if refresh else self._read_cache()
            if raw_models is None:
                raw_models = self._fetch_models()
                self._write_cache(raw_models)
        except BaseException:
            if self._owns_client:
                self.close()
            raise
        return [info for item in raw_models if (info := _model_info(item)).model_id]

    def find(self, model_id: str, *, refresh: bool = False) -> HFModelInfo | None:
        base = model_id.rsplit(":", 1)[0] if ":" in model_id else model_id
        return next(
            (item for item in self.list_models(refresh=refresh) if item.model_id == base), None
        )

    def alternatives(
        self,
        model_id: str,
        *,
        limit: int = 8,
        provider: str | None = None,
        require_structured_output: bool = False,
    ) -> list[HFModelInfo]:
        """Return catalog candidates, excluding known-incompatible metadata when available."""

        family = model_id.rsplit("/", 1)[-1].split("-", 1)[0].casefold()
        normalized_provider = (provider or "").casefold().replace("_", "-")
        matches: list[HFModelInfo] = []
        for item in self.list_models():
            if family not in item.model_id.casefold() or item.model_id == model_id:
                continue
            if _explicitly_unavailable(item.availability) or _explicitly_unavailable(
                item.raw.get("available")
            ):
                continue

            named_providers = [row for row in item.providers if _provider_name(row)]
            relevant_providers = named_providers
            if normalized_provider and named_providers:
                relevant_providers = [
                    row for row in named_providers if _provider_name(row) == normalized_provider
                ]
                if not relevant_providers:
                    continue
            status_rows = relevant_providers if normalized_provider else named_providers
            if status_rows and all(
                _explicitly_unavailable(row.get("status"))
                or _explicitly_unavailable(row.get("availability"))
                or _explicitly_unavailable(row.get("available"))
                for row in status_rows
            ):
                continue

            if require_structured_output:
                supports = item.supports_structured_output
                if supports is False:
                    continue
                provider_support = [
                    value
                    for row in relevant_providers
                    if (value := _structured_support(row)) is not None
                ]
                if normalized_provider and provider_support and not any(provider_support):
                    continue
                if (
                    not normalized_provider
                    and supports is not True
                    and provider_support
                    and not any(provider_support)
                ):
                    continue
            matches.append(item)
        return matches[:limit]

    def pricing_for(self, model_id: str, provider: str | None) -> dict[str, Any]:
        info = self.find(model_id)
        if info is None:
            return {}
        if provider:
            normalized = provider.casefold().replace("_", "-")
            for row in info.providers:
                name = str(row.get("provider") or row.get("name") or "")
                if name.casefold().replace("_", "-") == normalized and isinstance(
                    row.get("pricing"), dict
                ):
                    return dict(row["pricing"])
        if info.pricing:
            return dict(info.pricing)
        if len(info.providers) == 1 and isinstance(info.providers[0].get("pricing"), dict):
            return dict(info.providers[0]["pricing"])
        return {}
