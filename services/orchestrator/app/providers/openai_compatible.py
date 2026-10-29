"""Explicitly configured remote reviews; errors never trigger another provider."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from app.providers.base import ModelProvider


class OpenAICompatibleProvider(ModelProvider):
    def __init__(self, host, api_key, text_model, vision_model, timeout_seconds=30,
                 *, free_only=False, data_collection='deny', transport=None):
        url = urlsplit(host)
        if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Model endpoint must be an HTTP(S) base URL without credentials or query')
        if not text_model or not vision_model:
            raise ValueError('Configure both remote model IDs')
        if url.scheme != 'https' and url.hostname not in {'localhost', '127.0.0.1', '::1', 'host.docker.internal'}:
            raise ValueError('Remote model endpoints require HTTPS')
        if data_collection not in {'allow', 'deny'}:
            raise ValueError('Data collection must be allow or deny')
        if free_only and (url.hostname != 'openrouter.ai' or not all(m.endswith(':free') for m in (text_model, vision_model))):
            raise ValueError('Free-only mode requires explicit OpenRouter :free model IDs')
        self.host, self.api_key = host.rstrip('/'), api_key
        self.text_model, self.vision_model = text_model, vision_model
        self.timeout_seconds, self.transport = timeout_seconds, transport
        self.openrouter = url.hostname == 'openrouter.ai'
        self.data_collection = data_collection

    def _chat(self, model, content, schema):
        payload = {'model': model, 'messages': [{'role': 'user', 'content': content}],
                   'stream': False, 'max_tokens': 512}
        if schema is not None:
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'smartops_review', 'strict': False, 'schema': schema}}
        else:
            payload['response_format'] = {'type': 'json_object'}
        if self.openrouter:
            payload['provider'] = {'data_collection': self.data_collection, 'require_parameters': True}
        headers = {'Authorization': f'Bearer {self.api_key}'} if self.api_key else {}
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            response = client.post(self.host + '/chat/completions', headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        choices = body.get('choices', [])
        if not choices or choices[0].get('finish_reason') != 'stop':
            raise ValueError('Model response incomplete or unavailable')
        message = choices[0].get('message', {})
        if message.get('refusal') or not isinstance(message.get('content'), str):
            raise ValueError('Model did not provide a review')
        result = json.loads(message['content'])
        if not isinstance(result, dict):
            raise ValueError('Model review must be a JSON object')
        return result

    def review_event_evidence(self, prompt, image_paths: list[Path], schema=None):
        return self.review_event_evidence_base64(prompt, [base64.b64encode(p.read_bytes()).decode('ascii') for p in image_paths], schema)

    def review_event_evidence_base64(self, prompt, images, schema=None):
        if not images:
            raise ValueError('Vision review requires evidence images')
        content = [{'type': 'text', 'text': prompt}]
        content.extend({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + image}} for image in images)
        return self._chat(self.vision_model, content, schema)

    def summarize_incident(self, prompt, schema=None):
        return self._chat(self.text_model, prompt, schema)

    def suggest_actions(self, prompt, schema=None):
        return self.summarize_incident(prompt, schema)
