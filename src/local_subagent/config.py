from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class AppConfig:
    app_name: str
    database_path: Path
    export_dir: Path
    model_base_url: str
    model_api_key: str
    model_name: str
    temperature: float
    max_tokens: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppConfig":
        return cls(
            app_name=env.get("LOCAL_SUBAGENT_APP_NAME", "local-subagent"),
            database_path=Path(
                env.get("LOCAL_SUBAGENT_DATABASE_PATH", "local_subagent.db")
            ),
            export_dir=Path(env.get("LOCAL_SUBAGENT_EXPORT_DIR", "exports")),
            model_base_url=env.get(
                "LOCAL_SUBAGENT_MODEL_BASE_URL", "http://127.0.0.1:11434/v1"
            ),
            model_api_key=env.get("LOCAL_SUBAGENT_MODEL_API_KEY", "ollama"),
            model_name=env.get("LOCAL_SUBAGENT_MODEL_NAME", "qwen3"),
            temperature=float(env.get("LOCAL_SUBAGENT_TEMPERATURE", "0.2")),
            max_tokens=int(env.get("LOCAL_SUBAGENT_MAX_TOKENS", "2000")),
        )

