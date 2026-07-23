"""Route analyzer and verifier generations to independently configured backends."""

from __future__ import annotations

from pydantic import BaseModel

from snoc_agent.ai.backend import (
    ChatMessage,
    GenerationConfig,
    LLMBackend,
    StructuredGenerationResult,
)


class RoleRoutingBackend:
    """A narrow dispatcher; model roles remain fixed by application configuration."""

    def __init__(
        self,
        *,
        analyzer_model: str,
        analyzer_backend: LLMBackend,
        verifier_model: str,
        verifier_backend: LLMBackend,
    ) -> None:
        self._routes = {
            analyzer_model: analyzer_backend,
            verifier_model: verifier_backend,
        }
        self._backends = tuple(dict.fromkeys((analyzer_backend, verifier_backend)))

    def generate_structured(
        self,
        *,
        messages: list[ChatMessage],
        response_model: type[BaseModel],
        config: GenerationConfig,
    ) -> StructuredGenerationResult:
        backend = self._routes.get(config.model)
        if backend is None:
            raise ValueError("model is not assigned to an operational LLM role")
        return backend.generate_structured(
            messages=messages,
            response_model=response_model,
            config=config,
        )

    def health(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for model, backend in self._routes.items():
            check = getattr(backend, "health_check", None)
            results[model] = bool(check()) if callable(check) else True
        return results

    def close(self) -> None:
        for backend in self._backends:
            close = getattr(backend, "close", None)
            if callable(close):
                close()
