from __future__ import annotations

import os

from app.providers.base import ModelProvider
from app.providers.ollama import OllamaModelProvider


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def get_model_provider() -> ModelProvider:
    """Provider selection is configuration-driven.

    Only local Ollama is implemented today; hosted providers (Anthropic,
    OpenAI, ...) plug in here behind the same ModelProvider contract.
    """
    provider = os.getenv("SMARTOPS_MODEL_PROVIDER", "ollama").lower()
    if provider != "ollama":
        raise ValueError(
            f"Unsupported model provider: {provider}. "
            "Implement it in app/providers/ behind the ModelProvider contract."
        )

    return OllamaModelProvider(
        host=os.getenv("SMARTOPS_OLLAMA_HOST", "http://ollama:11434"),
        text_model=os.getenv("SMARTOPS_TEXT_MODEL", "llama3.2:3b"),
        vision_model=os.getenv("SMARTOPS_VISION_MODEL", "qwen2.5vl:3b"),
        # CPU inference is slow, and the first call also loads the model into
        # memory; keep this generous for local development.
        timeout_seconds=_env_float("SMARTOPS_MODEL_TIMEOUT_SECONDS", 480.0),
    )
