from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from app.providers.base import ModelProvider


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
            "keep_alive": "10m",
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
            "keep_alive": "10m",
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
