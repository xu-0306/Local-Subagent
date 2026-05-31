from __future__ import annotations

import json
from collections.abc import Sequence

import httpx

from local_subagent.runtime.prompts import SUBAGENT_SYSTEM_PROMPT
from local_subagent.runtime.protocol import SubagentResponse, parse_subagent_response


class LocalModelAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_name: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        system_prompt: str = SUBAGENT_SYSTEM_PROMPT,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model_name = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._system_prompt = system_prompt
        self._http_client = http_client or httpx.Client()

    def complete(self, messages: Sequence[dict[str, str]]) -> SubagentResponse:
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                *messages,
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
        }
        response = self._http_client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Model response content must be valid JSON") from exc

        return parse_subagent_response(parsed)
