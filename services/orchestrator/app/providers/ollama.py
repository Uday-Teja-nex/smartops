from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import ModelProvider


# How long Ollama keeps the model loaded after a request. A demo must not pay
# the ~2 minute CPU load in the middle of a live incident.
KEEP_ALIVE = os.getenv("SMARTOPS_OLLAMA_KEEP_ALIVE", "60m")


class OllamaModelProvider(ModelProvider):
    def __init__(
        self,
        host: str,
        text_model: str,
        vision_model: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.host = host.rstrip("/")
        self.text_model = text_model
        self.vision_model = vision_model
        self.timeout_seconds = timeout_seconds

    def availability(self) -> dict[str, Any]:
        """Is the server up, is the vision model installed, is it loaded?"""
        try:
            with httpx.Client(timeout=2.0) as client:
                tags = client.get(f"{self.host}/api/tags")
                tags.raise_for_status()
                loaded = client.get(f"{self.host}/api/ps")
                loaded.raise_for_status()
        except httpx.HTTPError as exc:
            return {"ok": False, "detail": f"Ollama unreachable ({type(exc).__name__})", "model": self.vision_model}
        installed = {item.get("name") for item in tags.json().get("models", [])}
        if self.vision_model not in installed:
            return {"ok": False, "detail": f"model {self.vision_model} is not installed in Ollama",
                    "model": self.vision_model}
        warm = self.vision_model in {item.get("name") for item in loaded.json().get("models", [])}
        return {"ok": True, "model": self.vision_model, "loaded": warm,
                "detail": "loaded and warm" if warm else "installed; first review loads it (about 2 min)"}

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.host}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _read_images(image_paths: list[Path]) -> list[str]:
        encoded: list[str] = []
        for path in image_paths:
            encoded.append(base64.b64encode(path.read_bytes()).decode("utf-8"))
        return encoded

    @staticmethod
    def _parse_message_content(response_json: dict[str, Any]) -> dict[str, Any]:
        content = response_json.get("message", {}).get("content", "").strip()
        if not content:
            return {"raw": response_json}

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"content": content, "raw": response_json}

    def review_event_evidence(
        self,
        prompt: str,
        image_paths: list[Path],
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.review_event_evidence_base64(prompt, self._read_images(image_paths), schema)

    def review_event_evidence_base64(
        self,
        prompt: str,
        images: list[str],
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": images,
                }
            ],
            "stream": False,
            "options": {"temperature": 0, "num_batch": 32, "num_ctx": 2048, "num_predict": 256},
            "keep_alive": KEEP_ALIVE,
        }
        if schema is not None:
            payload["format"] = schema

        return self._parse_message_content(self._post_chat(payload))

    def summarize_incident(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.text_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0, "num_batch": 32, "num_ctx": 2048, "num_predict": 256},
            "keep_alive": KEEP_ALIVE,
        }
        if schema is not None:
            payload["format"] = schema

        return self._parse_message_content(self._post_chat(payload))

    def suggest_actions(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.summarize_incident(prompt, schema=schema)
