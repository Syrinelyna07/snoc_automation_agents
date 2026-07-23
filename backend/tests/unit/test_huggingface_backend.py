from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from snoc_agent.ai.backend import ChatMessage, GenerationConfig
from snoc_agent.ai.cost import BudgetTracker
from snoc_agent.ai.errors import InferenceError, InferenceErrorCategory
from snoc_agent.ai.hf_discovery import HFModelCatalog
from snoc_agent.ai.huggingface_backend import HuggingFaceInferenceBackend
from snoc_agent.ai.provider import resolve_hf_model_route
from snoc_agent.config import Settings


class ProbeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ok: bool


def config(**overrides: object) -> GenerationConfig:
    values = {
        "model": "Qwen/Qwen3-8B:cheapest",
        "base_model": "Qwen/Qwen3-8B",
        "max_retries": 0,
        "retry_base_seconds": 0.01,
        "use_json_schema": True,
    }
    values.update(overrides)
    return GenerationConfig(**values)  # type: ignore[arg-type]


def completion(
    request: httpx.Request,
    *,
    message: dict[str, object] | None = None,
    usage: dict[str, int] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    payload: dict[str, object] = {
        "model": "Qwen/Qwen3-8B",
        "choices": [{"message": message or {"content": '{"ok":true}'}}],
    }
    if usage is not None:
        payload["usage"] = usage
    return httpx.Response(200, json=payload, headers=headers, request=request)


def backend(
    handler: httpx.MockTransport,
    **kwargs: object,
) -> HuggingFaceInferenceBackend:
    client = httpx.Client(transport=handler)
    return HuggingFaceInferenceBackend(
        base_url="https://router.huggingface.co/v1",
        client=client,
        sleep=lambda _seconds: None,
        jitter=lambda: 0.0,
        **kwargs,
    )


def generate(model_backend: HuggingFaceInferenceBackend, generation_config: GenerationConfig):
    return model_backend.generate_structured(
        messages=[ChatMessage(role="user", content="return ok")],
        response_model=ProbeSchema,
        config=generation_config,
    )


def test_route_resolution_prefers_explicit_provider_and_can_disable_suffix() -> None:
    explicit = resolve_hf_model_route("Qwen/Qwen3-8B", "cerebras", "cheapest", True)
    policy = resolve_hf_model_route("Qwen/Qwen3-8B", None, "fastest", True)
    disabled = resolve_hf_model_route("Qwen/Qwen3-8B:cheapest", None, "preferred", False)

    assert explicit.routed_model_id == "Qwen/Qwen3-8B:cerebras"
    assert policy.routed_model_id == "Qwen/Qwen3-8B:fastest"
    assert disabled.routed_model_id == "Qwen/Qwen3-8B"


def test_hf_configuration_precedence_uses_explicit_value_then_alias_then_default() -> None:
    aliases = Settings(
        _env_file=None,
        llm_provider="huggingface",
        llm_base_url="https://compat.example/v1",
        analyzer_model="Org/Alias-Analyzer",
        verifier_model="Org/Alias-Verifier",
    )
    explicit = aliases.model_copy(
        update={
            "hf_router_base_url": "https://router.example/v1",
            "hf_analyzer_model": "Org/HF-Analyzer",
            "hf_verifier_model": "Org/HF-Verifier",
        }
    )
    defaults = Settings(
        _env_file=None,
        llm_provider="huggingface",
        analyzer_model="",
        verifier_model="",
    )

    assert aliases.effective_hf_base_url == "https://compat.example/v1"
    assert aliases.effective_hf_analyzer_model == "Org/Alias-Analyzer"
    assert aliases.effective_hf_verifier_model == "Org/Alias-Verifier"
    assert explicit.effective_hf_base_url == "https://router.example/v1"
    assert explicit.effective_hf_analyzer_model == "Org/HF-Analyzer"
    assert explicit.effective_hf_verifier_model == "Org/HF-Verifier"
    assert defaults.effective_hf_base_url == "https://router.huggingface.co/v1"
    assert defaults.effective_hf_analyzer_model == "Qwen/Qwen2.5-7B-Instruct"
    assert defaults.effective_hf_verifier_model == "Qwen/Qwen3-8B"


def test_settings_validation_errors_never_include_hf_token() -> None:
    secret = "hf_TEST_SECRET_MUST_NOT_APPEAR"

    with pytest.raises(ValueError) as caught:
        Settings(
            hf_token=secret,
            hf_run_budget_usd=Decimal("1"),
            hf_stop_before_budget_usd=Decimal("2"),
        )

    assert secret not in str(caught.value)


def test_route_resolution_rejects_an_invalid_policy() -> None:
    with pytest.raises(ValueError, match="fastest, cheapest, or preferred"):
        resolve_hf_model_route("Qwen/Qwen3-8B", None, "random", True)


def test_hf_sends_strict_schema_but_not_qwen_thinking_parameters() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return completion(request, headers={"Inference-Id": "inference-123"})

    result = generate(
        backend(httpx.MockTransport(handler)),
        config(enable_thinking=True),
    )

    assert requests[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "ProbeSchema",
            "strict": True,
            "schema": ProbeSchema.model_json_schema(),
        },
    }
    assert "chat_template_kwargs" not in requests[0]
    assert result.provider_request_id == "inference-123"
    assert result.structured_output_mode == "json_schema"
    assert result.reasoning_output is None


def test_reasoning_field_and_think_block_are_never_parsed_as_final_json() -> None:
    responses = [
        {"reasoning_content": "private reasoning", "content": '{"ok":true}'},
        {"content": '<think>another thought</think>\n{"ok":true}'},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return completion(request, message=responses.pop(0))

    model_backend = backend(httpx.MockTransport(handler))
    first = generate(model_backend, config())
    second = generate(model_backend, config())

    assert first.parsed == ProbeSchema(ok=True)
    assert first.reasoning_output == "private reasoning"
    assert second.parsed == ProbeSchema(ok=True)
    assert second.reasoning_output == "another thought"


def test_json_schema_rejection_falls_back_to_json_object_only_when_enabled() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return httpx.Response(
                400,
                json={"error": {"message": "response_format json_schema is unsupported"}},
                request=request,
            )
        return completion(request)

    result = generate(
        backend(httpx.MockTransport(handler)),
        config(allow_json_object_fallback=True),
    )

    assert payloads[1]["response_format"] == {"type": "json_object"}
    assert result.structured_output_mode == "json_object"
    assert result.fallback_reason is not None


def test_prompt_json_fallback_and_single_repair_are_bounded() -> None:
    payloads: list[dict[str, object]] = []
    tracker = BudgetTracker(budget_usd=Decimal("1"), stop_before_usd=Decimal("0.9"))

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        payloads.append(payload)
        if len(payloads) <= 2:
            return httpx.Response(
                400,
                json={"error": {"message": "response_format is not supported"}},
                request=request,
            )
        if len(payloads) == 3:
            return completion(
                request,
                message={"content": "not json"},
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            )
        return completion(
            request,
            usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        )

    result = generate(
        backend(httpx.MockTransport(handler), budget_tracker=tracker),
        config(
            allow_json_object_fallback=True,
            allow_prompt_json_fallback=True,
        ),
    )

    assert len(payloads) == 4
    assert "response_format" not in payloads[2]
    assert result.structured_output_mode == "prompt_json"
    assert result.parse_attempt_count == 2
    assert len(result.validation_errors) == 1
    assert result.prompt_tokens == 30
    assert result.completion_tokens == 15
    assert result.total_tokens == 45
    assert tracker.request_count == 4
    assert tracker.unknown_cost_request_count == 2


def test_malformed_strict_content_is_not_retried_indefinitely() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return completion(
            request,
            message={"content": "bad"},
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    with pytest.raises(InferenceError) as caught:
        generate(
            backend(
                httpx.MockTransport(handler),
                pricing_resolver=lambda _model, _provider: {
                    "input": "0.10",
                    "output": "0.20",
                },
            ),
            config(max_retries=3),
        )

    assert caught.value.category == InferenceErrorCategory.MALFORMED_OUTPUT
    assert caught.value.structured_output_mode == "json_schema"
    assert caught.value.schema_name == "ProbeSchema"
    assert caught.value.parse_attempt_count == 1
    assert len(caught.value.validation_errors) == 1
    assert caught.value.raw_output == "bad"
    assert caught.value.total_tokens == 15
    assert caught.value.total_cost_usd == Decimal("0.000002")
    assert calls == 1


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (401, InferenceErrorCategory.AUTHENTICATION),
        (403, InferenceErrorCategory.PERMISSION),
        (404, InferenceErrorCategory.MODEL_UNAVAILABLE),
    ],
)
def test_non_transient_errors_are_classified_without_retry(
    status: int, category: InferenceErrorCategory
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"error": "failure"}, request=request)

    with pytest.raises(InferenceError) as caught:
        generate(backend(httpx.MockTransport(handler)), config(max_retries=3))

    assert caught.value.category == category
    assert calls == 1


def test_rate_limit_honors_retry_after_and_transient_timeout_retries() -> None:
    sleeps: list[float] = []
    calls = 0
    tracker = BudgetTracker(budget_usd=Decimal("1"), stop_before_usd=Decimal("0.9"))

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, request=request)
        if calls == 2:
            raise httpx.ReadTimeout("slow", request=request)
        return completion(request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    model_backend = HuggingFaceInferenceBackend(
        base_url="https://router.huggingface.co/v1",
        client=client,
        sleep=sleeps.append,
        jitter=lambda: 0.0,
        budget_tracker=tracker,
    )
    result = generate(model_backend, config(max_retries=2, retry_base_seconds=0.5))

    assert result.attempts == 3
    assert sleeps == [3.0, 1.0]
    assert tracker.request_count == 3


def test_provider_rejecting_extra_parameter_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert json.loads(request.content)["reasoning_effort"] == "high"
        return httpx.Response(
            400,
            json={"error": {"message": "unsupported parameter reasoning_effort"}},
            request=request,
        )

    with pytest.raises(InferenceError) as caught:
        generate(
            backend(httpx.MockTransport(handler)),
            config(extra_body={"reasoning_effort": "high"}, max_retries=3),
        )

    assert caught.value.category == InferenceErrorCategory.INVALID_REQUEST
    assert "high" not in str(caught.value)
    assert calls == 1


def test_usage_pricing_and_unknown_cost_are_handled_without_inventing_prices() -> None:
    responses = [
        {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        None,
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return completion(request, usage=responses.pop(0))

    priced = backend(
        httpx.MockTransport(handler),
        pricing_resolver=lambda _model, _provider: {"input": "0.10", "output": "0.20"},
    )
    first = generate(priced, config())
    second = generate(priced, config())

    assert first.total_tokens == 1500
    assert first.input_cost_usd == Decimal("0.0001")
    assert first.output_cost_usd == Decimal("0.0001")
    assert first.total_cost_usd == Decimal("0.0002")
    assert first.cost_basis == "estimated"
    assert second.total_cost_usd is None
    assert second.cost_basis == "unknown"


def test_provider_reported_input_and_output_costs_are_exact() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        response = completion(
            request,
            usage={"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
        )
        payload = response.json()
        payload["input_cost"] = "0.000001"
        payload["output_cost"] = "0.000002"
        return httpx.Response(200, json=payload, request=request)

    result = generate(backend(httpx.MockTransport(handler)), config())

    assert result.input_cost_usd == Decimal("0.000001")
    assert result.output_cost_usd == Decimal("0.000002")
    assert result.total_cost_usd == Decimal("0.000003")
    assert result.cost_basis == "exact"


@pytest.mark.parametrize("external_value", ["-1", "NaN", "Infinity"])
def test_invalid_external_cost_metadata_cannot_weaken_budget(
    external_value: str,
) -> None:
    result = generate(
        backend(
            httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "model": "Qwen/Qwen3-8B",
                        "cost": external_value,
                        "choices": [{"message": {"content": '{"ok":true}'}}],
                        "usage": {
                            "prompt_tokens": -10,
                            "completion_tokens": "NaN",
                            "total_tokens": "Infinity",
                        },
                    },
                    request=request,
                )
            ),
            pricing_resolver=lambda _model, _provider: {
                "input": external_value,
                "output": external_value,
            },
        ),
        config(),
    )

    assert result.prompt_tokens is None
    assert result.completion_tokens is None
    assert result.total_tokens is None
    assert result.total_cost_usd is None
    assert result.cost_basis == "unknown"


def test_budget_exhaustion_blocks_request_before_transport() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return completion(request)

    tracker = BudgetTracker(
        budget_usd=Decimal("0.10"),
        stop_before_usd=Decimal("0.09"),
        cost_so_far_usd=Decimal("0.09"),
    )
    with pytest.raises(InferenceError) as caught:
        generate(backend(httpx.MockTransport(handler), budget_tracker=tracker), config())

    assert caught.value.category == InferenceErrorCategory.BUDGET_EXHAUSTED
    assert called is False


def test_unknown_cost_policy_persists_first_response_then_blocks_next_request() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return completion(request)

    tracker = BudgetTracker(
        budget_usd=Decimal("1"),
        stop_before_usd=Decimal("0.9"),
        allow_unknown_cost=False,
    )
    model_backend = backend(httpx.MockTransport(handler), budget_tracker=tracker)

    first = generate(model_backend, config())
    with pytest.raises(InferenceError) as caught:
        generate(model_backend, config())

    assert first.cost_basis == "unknown"
    assert tracker.status == "stopped_unknown_cost"
    assert tracker.request_count == 1
    assert caught.value.category == InferenceErrorCategory.BUDGET_EXHAUSTED
    assert calls == 1


def test_model_catalog_caches_flexible_metadata(tmp_path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "Qwen/Qwen3-8B",
                        "providers": [
                            {
                                "provider": "nscale",
                                "status": "live",
                                "pricing": {"input": 0.07, "output": 0.18},
                            }
                        ],
                        "context_length": 40960,
                        "supports_structured_output": False,
                    }
                ]
            },
            request=request,
        )

    catalog = HFModelCatalog(
        base_url="https://router.huggingface.co/v1",
        token="test-token",
        cache_path=tmp_path / "models.json",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    first = catalog.list_models()
    second = catalog.list_models()

    assert calls == 1
    assert first == second
    assert first[0].context_length == 40960
    assert first[0].supports_structured_output is False
    assert catalog.pricing_for("Qwen/Qwen3-8B", "nscale") == {
        "input": 0.07,
        "output": 0.18,
    }


def test_model_catalog_retries_only_transient_failures_with_retry_after_and_jitter(
    tmp_path,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, request=request)
        if calls == 2:
            raise httpx.ReadTimeout("slow catalog", request=request)
        return httpx.Response(
            200,
            json={"data": [{"id": "Qwen/Qwen3-8B"}]},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    catalog = HFModelCatalog(
        base_url="https://router.huggingface.co/v1",
        token="test-token",
        cache_path=tmp_path / "models.json",
        max_retries=2,
        retry_base_seconds=2,
        client=client,
        sleep=sleeps.append,
        jitter=lambda: 1.0,
    )

    assert [item.model_id for item in catalog.list_models()] == ["Qwen/Qwen3-8B"]
    assert calls == 3
    assert sleeps == [3.0, 5.0]
    client.close()


def test_model_catalog_does_not_retry_authentication_and_closes_owned_client(
    tmp_path, monkeypatch
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": "invalid token"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "snoc_agent.ai.hf_discovery.httpx.Client",
        lambda **_kwargs: client,
    )
    catalog = HFModelCatalog(
        base_url="https://router.huggingface.co/v1",
        token="test-token",
        cache_path=tmp_path / "models.json",
        max_retries=3,
        sleep=lambda _seconds: pytest.fail("authentication failure must not be retried"),
    )

    with pytest.raises(InferenceError) as caught:
        catalog.list_models()

    assert caught.value.category == InferenceErrorCategory.AUTHENTICATION
    assert calls == 1
    assert client.is_closed


def test_model_catalog_alternatives_filter_known_provider_status_and_capability(tmp_path) -> None:
    rows = [
        {
            "id": "Qwen/Qwen3-14B",
            "providers": [
                {
                    "provider": "nscale",
                    "status": "live",
                    "supports_structured_output": True,
                }
            ],
        },
        {
            "id": "Qwen/Qwen3-32B",
            "providers": [
                {
                    "provider": "nscale",
                    "status": "offline",
                    "supports_structured_output": True,
                }
            ],
        },
        {
            "id": "Qwen/Qwen3-30B",
            "providers": [
                {
                    "provider": "other-provider",
                    "status": "live",
                    "supports_structured_output": True,
                }
            ],
        },
        {
            "id": "Qwen/Qwen3-4B",
            "providers": [
                {
                    "provider": "nscale",
                    "status": "live",
                    "supports_structured_output": False,
                }
            ],
        },
        {"id": "Qwen/Qwen3-1B"},
        {"id": "Qwen/Qwen3-0.6B", "availability": "unavailable"},
    ]

    catalog = HFModelCatalog(
        base_url="https://router.huggingface.co/v1",
        token="test-token",
        cache_path=tmp_path / "models.json",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"data": rows}, request=request)
            )
        ),
    )

    alternatives = catalog.alternatives(
        "Qwen/Qwen3-8B",
        provider="nscale",
        require_structured_output=True,
    )

    assert [item.model_id for item in alternatives] == ["Qwen/Qwen3-14B", "Qwen/Qwen3-1B"]
    catalog.client.close()


def test_chat_probe_rejects_success_envelope_without_assistant_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "Qwen/Qwen3-8B",
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 0, "total_tokens": 2},
            },
            request=request,
        )

    with pytest.raises(InferenceError) as caught:
        backend(httpx.MockTransport(handler)).probe_chat(model="Qwen/Qwen3-8B:cheapest")

    assert caught.value.category == InferenceErrorCategory.MALFORMED_OUTPUT
    assert caught.value.total_tokens == 2
