from __future__ import annotations

import os
import math

from app.providers.base import ModelProvider
from app.providers.ollama import OllamaModelProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive finite number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _native_ollama(vision_model: str, text_model: str) -> OllamaModelProvider:
    return OllamaModelProvider(
        host=os.getenv("SMARTOPS_OLLAMA_HOST", "http://host.docker.internal:11434"),
        text_model=text_model,
        vision_model=vision_model,
        timeout_seconds=_env_float("SMARTOPS_MODEL_TIMEOUT_SECONDS", 30.0),
    )


def get_model_provider() -> ModelProvider:
    """Select the configured provider, optionally backed by native Ollama.

    The fallback may only be local Ollama: falling back never changes billing
    or sends evidence to a different external service.
    """
    primary = _primary_provider()
    fallback = os.getenv("SMARTOPS_MODEL_FALLBACK", "").strip().lower()
    if not fallback:
        return primary
    if fallback != "ollama":
        raise ValueError("SMARTOPS_MODEL_FALLBACK supports only 'ollama' (local, no data leaves the machine)")
    if isinstance(primary, OllamaModelProvider):
        return primary
    from app.providers.fallback import FallbackProvider
    return FallbackProvider(primary, _native_ollama(
        os.getenv("SMARTOPS_FALLBACK_VISION_MODEL", "qwen2.5vl:3b"),
        os.getenv("SMARTOPS_FALLBACK_TEXT_MODEL", "llama3.2:3b")))


def _primary_provider() -> ModelProvider:
    provider = os.getenv("SMARTOPS_MODEL_PROVIDER", "ollama").lower()
    if provider in {'openrouter', 'openai-compatible', 'meta'}:
        defaults = {'openrouter': 'https://openrouter.ai/api/v1',
                    'meta': 'https://api.meta.ai/v1', 'openai-compatible': ''}
        api_key = os.getenv('SMARTOPS_MODEL_API_KEY', '')
        if provider != 'openai-compatible' and not api_key:
            raise ValueError('SMARTOPS_MODEL_API_KEY is required for the selected provider')
        return OpenAICompatibleProvider(
            host=os.getenv('SMARTOPS_MODEL_BASE_URL') or defaults[provider], api_key=api_key,
            text_model=os.getenv('SMARTOPS_TEXT_MODEL', ''), vision_model=os.getenv('SMARTOPS_VISION_MODEL', ''),
            timeout_seconds=_env_float('SMARTOPS_MODEL_TIMEOUT_SECONDS', 30),
            free_only=provider == 'openrouter' and os.getenv('SMARTOPS_OPENROUTER_FREE_ONLY', 'true').lower() != 'false',
            data_collection=os.getenv('SMARTOPS_OPENROUTER_DATA_COLLECTION', 'deny'))
    if provider != "ollama":
        raise ValueError(
            f"Unsupported model provider: {provider}. "
            "Implement it in app/providers/ behind the ModelProvider contract."
        )

    return _native_ollama(os.getenv("SMARTOPS_VISION_MODEL", "qwen2.5vl:3b"),
                          os.getenv("SMARTOPS_TEXT_MODEL", "llama3.2:3b"))
