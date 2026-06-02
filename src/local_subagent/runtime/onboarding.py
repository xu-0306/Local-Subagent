from __future__ import annotations

from typing import Any

from local_subagent.errors import LocalSubagentError
from local_subagent.runtime.presets import RUNTIME_PRESETS, get_runtime_preset


def list_runtime_presets() -> list[dict[str, Any]]:
    presets: list[dict[str, Any]] = []
    for provider in sorted(RUNTIME_PRESETS):
        preset = get_runtime_preset(provider)
        preset["required_fields"] = _required_fields_for_preset(preset)
        presets.append(preset)
    return presets


def build_runtime_settings(
    *,
    provider: str,
    api_url: str | None,
    api_key: str | None,
    model_name: str | None,
    temperature: float | None,
    max_tokens: int | None,
    fallback_model_name: str,
    fallback_temperature: float,
    fallback_max_tokens: int,
) -> tuple[dict[str, Any], list[str]]:
    try:
        preset = get_runtime_preset(provider)
    except ValueError as exc:
        raise LocalSubagentError(str(exc)) from exc

    settings = {
        "runtime_provider": provider,
        "model_base_url": (api_url or preset["default_api_url"] or "").strip(),
        "model_api_key": (api_key or preset["default_api_key"] or "").strip(),
        "model_name": (model_name or fallback_model_name).strip(),
        "temperature": fallback_temperature if temperature is None else float(temperature),
        "max_tokens": fallback_max_tokens if max_tokens is None else int(max_tokens),
    }
    missing_fields = _missing_fields(settings, preset)
    return settings, missing_fields


def _required_fields_for_preset(preset: dict[str, Any]) -> list[str]:
    required_fields: list[str] = []
    if preset["requires_api_url"]:
        required_fields.append("api_url")
    if preset["requires_api_key"]:
        required_fields.append("api_key")
    return required_fields


def _missing_fields(
    settings: dict[str, Any],
    preset: dict[str, Any],
) -> list[str]:
    missing_fields: list[str] = []
    if preset["requires_api_url"] and not settings["model_base_url"]:
        missing_fields.append("api_url")
    if preset["requires_api_key"] and not settings["model_api_key"]:
        missing_fields.append("api_key")
    return missing_fields
