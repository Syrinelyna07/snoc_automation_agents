from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from snoc_agent.ai.backend import ChatMessage, GenerationConfig
from snoc_agent.ai.cost import BudgetTracker
from snoc_agent.ai.errors import InferenceError, InferenceErrorCategory
from snoc_agent.ai.hf_discovery import HFModelCatalog
from snoc_agent.ai.huggingface_backend import HuggingFaceInferenceBackend
from snoc_agent.config import Settings
from snoc_agent.evaluation.hf_smoke import require_known_route_pricing

LIVE_SETTINGS = Settings()

pytestmark = [
    pytest.mark.hf_live,
    pytest.mark.skipif(
        not LIVE_SETTINGS.effective_hf_token or not LIVE_SETTINGS.run_hf_live_tests,
        reason="set HF_TOKEN and RUN_HF_LIVE_TESTS=true to run tiny live router tests",
    ),
]


class LiveProbe(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ok: bool


def test_hf_models_and_qwen_structured_outputs_are_compatible(tmp_path) -> None:
    token = LIVE_SETTINGS.effective_hf_token
    base_url = LIVE_SETTINGS.effective_hf_base_url
    max_cost = LIVE_SETTINGS.hf_live_test_max_cost_usd
    catalog = HFModelCatalog(
        base_url=base_url,
        token=token,
        cache_path=tmp_path / "models.json",
        cache_ttl_seconds=0,
        timeout_seconds=LIVE_SETTINGS.hf_request_timeout_seconds,
        max_retries=LIVE_SETTINGS.hf_max_retries,
        retry_base_seconds=LIVE_SETTINGS.hf_retry_base_seconds,
    )
    backend = None
    try:
        model_ids = {item.model_id for item in catalog.list_models(refresh=True)}
        required = {"Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen3-8B"}
        missing = required - model_ids
        if missing:
            pytest.fail(f"configured live-test models currently unavailable: {sorted(missing)}")
        routes = [(base_model, f"{base_model}:cheapest") for base_model in sorted(required)]
        try:
            pricing_by_model = require_known_route_pricing(catalog, routes)
        except InferenceError as exc:
            if exc.category == InferenceErrorCategory.BUDGET_EXHAUSTED:
                pytest.skip(
                    "router does not expose deterministic pricing for the selected policy routes; "
                    "pin a priced provider to run the strict live cost test"
                )
            raise
        tracker = BudgetTracker(
            budget_usd=max_cost,
            stop_before_usd=max_cost,
            allow_unknown_cost=False,
        )
        backend = HuggingFaceInferenceBackend(
            base_url=base_url,
            api_key=token,
            timeout_seconds=LIVE_SETTINGS.hf_request_timeout_seconds,
            budget_tracker=tracker,
            pricing_resolver=lambda model, _provider: pricing_by_model.get(model, {}),
        )
        for base_model, routed_model in routes:
            result = backend.generate_structured(
                messages=[
                    ChatMessage(
                        role="system",
                        content="Return only the requested JSON object; do not explain.",
                    ),
                    ChatMessage(role="user", content='Return {"ok": true}.'),
                ],
                response_model=LiveProbe,
                config=GenerationConfig(
                    model=routed_model,
                    base_model=base_model,
                    temperature=0,
                    # Qwen3 may spend a small output budget on reasoning before
                    # returning the final schema object. Keep the live probe
                    # bounded by the configured verifier ceiling instead of an
                    # incompatible fixed 64-token cap.
                    max_output_tokens=LIVE_SETTINGS.hf_max_output_tokens_verifier,
                    max_retries=0,
                    use_json_schema=True,
                    allow_json_object_fallback=True,
                    allow_prompt_json_fallback=True,
                ),
            )
            assert result.parsed == LiveProbe(ok=True)
            assert result.structured_output_mode in {
                "json_schema",
                "json_object",
                "prompt_json",
            }
            assert result.total_cost_usd is not None
            assert result.cost_basis != "unknown"
            assert result.prompt_tokens is None or result.prompt_tokens >= 0
            assert result.completion_tokens is None or result.completion_tokens >= 0
            if result.prompt_tokens is not None and result.completion_tokens is not None:
                assert result.total_tokens == result.prompt_tokens + result.completion_tokens
            assert tracker.unknown_cost_request_count == 0
        assert tracker.cost_so_far_usd < max_cost
    finally:
        if backend is not None:
            backend.close()
        catalog.close()
