"""Named Qwen analyzer/verifier combinations for offline comparisons."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPair:
    name: str
    analyzer_model: str
    verifier_model: str


MODEL_PAIRS = {
    pair.name: pair
    for pair in (
        ModelPair("qwen25_qwen25", "Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct"),
        ModelPair("qwen3_qwen3", "Qwen/Qwen3-8B", "Qwen/Qwen3-8B"),
        ModelPair("qwen25_qwen3", "Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen3-8B"),
        ModelPair("qwen3_qwen25", "Qwen/Qwen3-8B", "Qwen/Qwen2.5-7B-Instruct"),
    )
}

VLLM_MODEL_PAIRS = {
    pair.name: pair
    for pair in (
        ModelPair("qwen_qwen", "qwen", "qwen"),
        ModelPair("qwen_gemma", "qwen", "gemma"),
        ModelPair("gemma_qwen", "gemma", "qwen"),
        ModelPair("gemma_gemma", "gemma", "gemma"),
    )
}

HF_MODEL_ALIASES = {
    "Qwen2.5-7B-Instruct": "Qwen/Qwen2.5-7B-Instruct",
    "Qwen3-8B": "Qwen/Qwen3-8B",
}


def canonical_hf_model_id(model_id: str) -> str:
    canonical = HF_MODEL_ALIASES.get(model_id, model_id).strip()
    if "/" in canonical and ":" in canonical:
        return canonical.rsplit(":", 1)[0]
    return canonical
