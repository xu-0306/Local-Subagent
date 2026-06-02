from __future__ import annotations

import json
from collections.abc import Sequence

import httpx

from local_subagent.errors import LocalSubagentError
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

    def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        model_name: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> SubagentResponse:
        payload = {
            "model": model_name or self._model_name,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                *messages,
            ],
            "temperature": self._temperature if temperature is None else temperature,
            "max_tokens": self._max_tokens if max_tokens is None else max_tokens,
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
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalSubagentError(
                "Local model response was invalid. Expected choices[0].message.content "
                "from an OpenAI-compatible chat completion response."
            ) from exc

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LocalSubagentError(
                "Local model response content must be valid JSON."
            ) from exc

        try:
            return parse_subagent_response(parsed)
        except ValueError as exc:
            raise LocalSubagentError(
                f"Local model JSON response did not match the required subagent schema: {exc}"
            ) from exc

    def validate_connection(
        self,
        *,
        base_url: str,
        api_key: str,
    ) -> dict[str, object]:
        normalized_base_url = base_url.rstrip("/")
        try:
            response = self._http_client.get(
                f"{normalized_base_url}/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                },
            )
            response.raise_for_status()
        except httpx.ConnectError as exc:
            raise LocalSubagentError(
                f"Could not reach the runtime at {normalized_base_url}. Start the local server and try again."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LocalSubagentError(
                f"Timed out while connecting to {normalized_base_url}. Check that the runtime is responsive and try again."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LocalSubagentError(
                _http_error_message(exc, normalized_base_url)
            ) from exc

        try:
            payload = response.json()
            models = [
                item["id"]
                for item in payload.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
        except (AttributeError, TypeError, ValueError) as exc:
            raise LocalSubagentError(
                f"The runtime at {normalized_base_url} responded, but /models did not return the expected OpenAI-compatible JSON payload."
            ) from exc
        return {"available_models": models}


def _http_error_message(exc: httpx.HTTPStatusError, base_url: str) -> str:
    status_code = exc.response.status_code
    if status_code == 404:
        if not base_url.endswith("/v1"):
            return (
                f"The runtime at {base_url} returned 404 for /models. "
                "If this is an OpenAI-compatible server, the base URL probably needs the /v1 suffix."
            )
        return (
            f"The runtime at {base_url} returned 404 for /models. "
            "Confirm that this server exposes an OpenAI-compatible API."
        )
    if status_code in {401, 403}:
        return (
            f"The runtime at {base_url} rejected the API key with status {status_code}. "
            "Check the configured API key and try again."
        )
    return (
        f"The runtime at {base_url} returned HTTP {status_code} during validation. "
        "Confirm the server is OpenAI-compatible and reachable."
    )
