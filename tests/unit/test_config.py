from pathlib import Path

from local_subagent.config import AppConfig


def test_app_config_defaults():
    config = AppConfig.from_env({})

    assert config.app_name == "local-subagent"
    assert config.database_path == Path("local_subagent.db")
    assert config.export_dir == Path("exports")
    assert config.model_base_url == "http://127.0.0.1:11434/v1"
    assert config.model_api_key == "ollama"
    assert config.model_name == "qwen3"
    assert config.temperature == 0.2
    assert config.max_tokens == 2000


def test_app_config_reads_environment_overrides():
    config = AppConfig.from_env(
        {
            "LOCAL_SUBAGENT_DATABASE_PATH": "data/runs.db",
            "LOCAL_SUBAGENT_EXPORT_DIR": "artifacts",
            "LOCAL_SUBAGENT_MODEL_BASE_URL": "http://localhost:8000/v1",
            "LOCAL_SUBAGENT_MODEL_API_KEY": "secret",
            "LOCAL_SUBAGENT_MODEL_NAME": "llama-test",
            "LOCAL_SUBAGENT_TEMPERATURE": "0.6",
            "LOCAL_SUBAGENT_MAX_TOKENS": "4096",
        }
    )

    assert config.database_path == Path("data/runs.db")
    assert config.export_dir == Path("artifacts")
    assert config.model_base_url == "http://localhost:8000/v1"
    assert config.model_api_key == "secret"
    assert config.model_name == "llama-test"
    assert config.temperature == 0.6
    assert config.max_tokens == 4096

