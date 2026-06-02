from __future__ import annotations

from typing import Any

RUNTIME_PRESETS: dict[str, dict[str, Any]] = {
    "ollama": {
        "provider": "ollama",
        "title": "Ollama",
        "default_api_url": "http://127.0.0.1:11434/v1",
        "default_api_key": "ollama",
        "requires_api_url": False,
        "requires_api_key": False,
        "notes": [
            "Use this when the user runs Ollama locally.",
            "The OpenAI-compatible endpoint usually lives at http://127.0.0.1:11434/v1.",
        ],
    },
    "vllm": {
        "provider": "vllm",
        "title": "vLLM",
        "default_api_url": "http://127.0.0.1:8000/v1",
        "default_api_key": "EMPTY",
        "requires_api_url": False,
        "requires_api_key": False,
        "notes": [
            "Use this when the user serves a model with vLLM's OpenAI-compatible API.",
            "Many local setups use http://127.0.0.1:8000/v1.",
        ],
    },
    "lmstudio": {
        "provider": "lmstudio",
        "title": "LM Studio",
        "default_api_url": "http://127.0.0.1:1234/v1",
        "default_api_key": "lm-studio",
        "requires_api_url": False,
        "requires_api_key": False,
        "notes": [
            "Use this when the user enabled the local server in LM Studio.",
            "The default local server URL is usually http://127.0.0.1:1234/v1.",
        ],
    },
    "llamacpp": {
        "provider": "llamacpp",
        "title": "llama.cpp",
        "default_api_url": "http://127.0.0.1:8080/v1",
        "default_api_key": "llama.cpp",
        "requires_api_url": False,
        "requires_api_key": False,
        "notes": [
            "Use this when the user runs llama.cpp server mode with OpenAI compatibility enabled.",
            "A common local URL is http://127.0.0.1:8080/v1.",
        ],
    },
    "openai_compatible": {
        "provider": "openai_compatible",
        "title": "Custom OpenAI-Compatible Runtime",
        "default_api_url": None,
        "default_api_key": "local-subagent",
        "requires_api_url": True,
        "requires_api_key": False,
        "notes": [
            "Use this for any other OpenAI-compatible endpoint.",
            "Ask the user for the exact /v1 base URL if it is not one of the built-in presets.",
        ],
    },
}


def get_runtime_preset(provider: str) -> dict[str, Any]:
    try:
        return dict(RUNTIME_PRESETS[provider])
    except KeyError as exc:
        supported = ", ".join(sorted(RUNTIME_PRESETS))
        raise ValueError(
            f"Unsupported runtime provider: {provider}. Supported providers: {supported}."
        ) from exc
