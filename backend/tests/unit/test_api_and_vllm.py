from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import ValidationError

from snoc_agent.api import create_app
from snoc_agent.api.dq import weighted_dimension_score
from snoc_agent.api.filters import DateRange, parse_time_window, range_query_values
from snoc_agent.cli.runtime import build_model_services
from snoc_agent.config import Settings
from snoc_agent.db import create_engine_and_session, create_schema


def _api_settings(tmp_path) -> Settings:
    database = tmp_path / "api.db"
    engine, _factory = create_engine_and_session(f"sqlite:///{database}")
    create_schema(engine)
    engine.dispose()
    return Settings(database_url=f"sqlite:///{database}", app_env="test")


def _get(app, path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(request())


def test_weighted_dq_score_is_record_weighted() -> None:
    assert weighted_dimension_score([(9, 10), (1, 90)]) == pytest.approx(10.0)
    assert weighted_dimension_score([]) is None
    with pytest.raises(ValueError):
        weighted_dimension_score([(2, 1)])


def test_filter_query_mapping_is_serializable() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=2)
    window = parse_time_window(DateRange.CUSTOM, start=start, end=end)
    assert window.start == start
    assert range_query_values(DateRange.CUSTOM, start, end) == {
        "range": "custom",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


def test_dashboard_is_deterministic_demo_when_operational_apis_are_unconfigured(
    tmp_path,
) -> None:
    settings = _api_settings(tmp_path)
    app = create_app(settings)
    first = _get(app, "/api/snoc/dashboard/summary?range=week")
    second = _get(app, "/api/snoc/dashboard/summary?range=week")
    assert first.status_code == 200
    assert first.json()["mode"] == "demo"
    assert first.json()["operational"] == second.json()["operational"]
    assert first.json()["data_quality"] is None
    assert "data_quality" in first.json()["unavailable_components"]


def test_dq_unavailable_does_not_fabricate_accuracy_or_timeliness(tmp_path) -> None:
    response = _get(create_app(_api_settings(tmp_path)), "/api/snoc/dq/dimensions")
    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "reason": "public.dq_dimension_summary is unavailable",
        "data": [],
    }
    assert "Accuracy" not in response.text
    assert "Timeliness" not in response.text


def test_null_values_and_empty_operational_state_do_not_crash(tmp_path) -> None:
    app = create_app(_api_settings(tmp_path))
    summary = _get(app, "/api/snoc/dashboard/summary").json()
    recent = _get(app, "/api/snoc/dashboard/recent").json()
    assert summary["operational"]["average_processing_ms"] is None
    assert summary["operational"]["readiness_rate"] is None
    assert recent["items"] == []


def test_live_execution_requires_explicit_opt_in_and_complete_safety_config() -> None:
    with pytest.raises(ValidationError, match="AUTO_EXECUTION_ENABLED"):
        Settings(dry_run=False)
    with pytest.raises(ValidationError, match="DRY_RUN=false"):
        Settings(auto_execution_enabled=True)


def test_vllm_analyzer_and_verifier_are_independently_configured() -> None:
    settings = Settings(
        llm_provider="vllm",
        analyzer_llm_base_url="https://analyzer.invalid",
        analyzer_llm_model="qwen-analyzer",
        verifier_llm_base_url="https://verifier.invalid",
        verifier_llm_model="gemma-verifier",
    )
    backend, analyzer, verifier = build_model_services(settings)
    try:
        assert analyzer.config.model == "qwen-analyzer"
        assert verifier.config.model == "gemma-verifier"
        assert analyzer.backend is backend
        assert verifier.backend is backend
    finally:
        close = getattr(backend, "close", None)
        if callable(close):
            close()


def test_vllm_deployment_aliases_map_without_exposing_keys(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=vllm",
                "VLLM_API_KEY=placeholder-only",
                "VLLM_QWEN_BASE_URL=https://qwen.invalid/v1",
                "VLLM_QWEN_MODEL=qwen-test",
                "VLLM_GEMMA_BASE_URL=https://gemma.invalid/v1",
                "VLLM_GEMMA_MODEL=gemma-test",
                "VLLM_ANALYZER_DEPLOYMENT=qwen",
                "VLLM_VERIFIER_DEPLOYMENT=gemma",
                "VLLM_MAX_OUTPUT_TOKENS_ANALYZER=1500",
                "VLLM_MAX_OUTPUT_TOKENS_VERIFIER=900",
                "IMAP_SEARCH_CRITERION=HEADER X-SNOC-Test-Run test-only",
            ]
        ),
        encoding="utf-8",
    )
    settings = Settings(_env_file=env_file)
    assert settings.effective_analyzer_base_url == "https://qwen.invalid/v1"
    assert settings.effective_verifier_base_url == "https://gemma.invalid/v1"
    assert settings.effective_analyzer_model == "qwen-test"
    assert settings.effective_verifier_model == "gemma-test"
    assert settings.effective_analyzer_max_output_tokens == 1500
    assert settings.effective_verifier_max_output_tokens == 900
    assert "placeholder-only" not in repr(settings)


def test_production_api_requires_server_side_jwt_configuration() -> None:
    with pytest.raises(ValidationError, match="JWT"):
        Settings(app_env="production")
