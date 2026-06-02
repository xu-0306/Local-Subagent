from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

DEFAULT_RUNTIME_SETTINGS = {
    "runtime_provider": "ollama",
    "model_base_url": "http://127.0.0.1:11434/v1",
    "model_api_key": "ollama",
    "model_name": "qwen3",
    "temperature": 0.2,
    "max_tokens": 2000,
}
RUNTIME_ENV_FIELD_MAP = {
    "LOCAL_SUBAGENT_RUNTIME_PROVIDER": "runtime_provider",
    "LOCAL_SUBAGENT_MODEL_BASE_URL": "model_base_url",
    "LOCAL_SUBAGENT_MODEL_API_KEY": "model_api_key",
    "LOCAL_SUBAGENT_MODEL_NAME": "model_name",
    "LOCAL_SUBAGENT_TEMPERATURE": "temperature",
    "LOCAL_SUBAGENT_MAX_TOKENS": "max_tokens",
}


@dataclass(slots=True)
class AppConfig:
    app_name: str
    database_path: Path
    export_dir: Path
    config_path: Path
    runtime_provider: str
    runtime_source: str
    model_base_url: str
    model_api_key: str
    model_name: str
    temperature: float
    max_tokens: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppConfig":
        config_path = resolve_runtime_config_path(env)
        config_values = load_runtime_config_file(config_path)
        runtime_values, runtime_source = _resolve_runtime_values(env, config_values)
        return cls(
            app_name=env.get("LOCAL_SUBAGENT_APP_NAME", "local-subagent"),
            database_path=Path(
                env.get("LOCAL_SUBAGENT_DATABASE_PATH", "local_subagent.db")
            ),
            export_dir=Path(env.get("LOCAL_SUBAGENT_EXPORT_DIR", "exports")),
            config_path=config_path,
            runtime_provider=str(runtime_values["runtime_provider"]),
            runtime_source=runtime_source,
            model_base_url=str(runtime_values["model_base_url"]),
            model_api_key=str(runtime_values["model_api_key"]),
            model_name=str(runtime_values["model_name"]),
            temperature=float(runtime_values["temperature"]),
            max_tokens=int(runtime_values["max_tokens"]),
        )


def resolve_runtime_config_path(env: Mapping[str, str]) -> Path:
    explicit_path = env.get("LOCAL_SUBAGENT_CONFIG_PATH")
    if explicit_path:
        return Path(explicit_path)

    codex_home = env.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home) / "local-subagent-runtime.json"

    home_dir = _resolve_home_dir(env)
    if _is_claude_environment(env):
        return home_dir / ".claude" / "local-subagent-runtime.json"
    if _is_codex_environment(env):
        return home_dir / ".codex" / "local-subagent-runtime.json"
    return home_dir / ".local-subagent" / "runtime.json"


def load_runtime_config_file(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_runtime_config_file(
    config_path: Path,
    *,
    runtime_provider: str,
    model_base_url: str,
    model_api_key: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(
            {
                "runtime_provider": runtime_provider,
                "model_base_url": model_base_url,
                "model_api_key": model_api_key,
                "model_name": model_name,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _resolve_runtime_values(
    env: Mapping[str, str],
    config_values: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    resolved: dict[str, Any] = dict(DEFAULT_RUNTIME_SETTINGS)
    runtime_sources: list[str] = []

    for env_key, field_name in RUNTIME_ENV_FIELD_MAP.items():
        if field_name in config_values:
            resolved[field_name] = config_values[field_name]
            runtime_sources.append("config_file")
        if env_key in env:
            resolved[field_name] = env[env_key]
            runtime_sources.append("env")

    if "env" in runtime_sources and "config_file" in runtime_sources:
        source = "mixed"
    elif "env" in runtime_sources:
        source = "env"
    elif "config_file" in runtime_sources:
        source = "config_file"
    else:
        source = "defaults"
    return resolved, source


def _resolve_home_dir(env: Mapping[str, str]) -> Path:
    home_value = env.get("HOME") or env.get("USERPROFILE")
    if home_value:
        return Path(home_value)
    return Path.home()


def _is_codex_environment(env: Mapping[str, str]) -> bool:
    return any(
        key in env
        for key in (
            "CODEX_THREAD_ID",
            "CODEX_SHELL",
            "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
            "CODEX_CI",
        )
    )


def _is_claude_environment(env: Mapping[str, str]) -> bool:
    return any(
        key in env
        for key in (
            "CLAUDECODE",
            "CLAUDE_CODE_ENTRYPOINT",
            "CLAUDECODE_ENTRYPOINT",
        )
    )
