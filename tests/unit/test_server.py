import asyncio
from pathlib import Path

from fastmcp import FastMCP

from local_subagent.config import AppConfig
from local_subagent.server import create_server


def test_create_server_returns_fastmcp_instance():
    server = create_server(
        config=AppConfig.from_env(
            {
                "LOCAL_SUBAGENT_DATABASE_PATH": str(Path("test-server.db")),
                "LOCAL_SUBAGENT_EXPORT_DIR": "test-exports",
            }
        ),
        service=DummyService(),
    )

    assert isinstance(server, FastMCP)
    assert server.name == "local-subagent"
    assert "mediated subagent" in (server.instructions or "").lower()


def test_create_server_registers_expected_tools():
    server = create_server(
        config=AppConfig.from_env(
            {
                "LOCAL_SUBAGENT_DATABASE_PATH": str(Path("test-server.db")),
                "LOCAL_SUBAGENT_EXPORT_DIR": "test-exports",
            }
        ),
        service=DummyService(),
    )

    assert set(asyncio.run(server.get_tools())) == {
        "subagent_start_task",
        "subagent_step",
        "subagent_submit_tool_result",
        "subagent_record_review",
        "subagent_export_dataset",
        "subagent_get_run",
        "subagent_list_runs",
    }


class DummyService:
    def start_task(self, **_: object) -> dict[str, object]:
        return {}

    def step(self, **_: object) -> dict[str, object]:
        return {}

    def submit_tool_result(self, **_: object) -> dict[str, object]:
        return {}

    def record_review(self, **_: object) -> dict[str, object]:
        return {}

    def export_dataset(self, **_: object) -> dict[str, object]:
        return {}

    def get_run(self, **_: object) -> dict[str, object]:
        return {}

    def list_runs(self) -> list[dict[str, object]]:
        return []
