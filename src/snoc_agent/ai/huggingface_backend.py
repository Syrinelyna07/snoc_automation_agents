"""First-class Hugging Face Inference Providers backend."""

from __future__ import annotations

from snoc_agent.ai.openai_compatible_backend import OpenAICompatibleBackend


class HuggingFaceInferenceBackend(OpenAICompatibleBackend):
    """OpenAI-compatible transport with portable Hugging Face defaults."""

    def __init__(self, **kwargs: object) -> None:
        kwargs["backend_name"] = "huggingface"
        kwargs["send_thinking_parameters"] = False
        super().__init__(**kwargs)  # type: ignore[arg-type]
