from __future__ import annotations

import asyncio
import json
from pathlib import Path

from local_subagent.config import AppConfig
from local_subagent.runtime import SubagentResponse, ToolRequest
from local_subagent.server import create_server
from local_subagent.service import SubagentService
from local_subagent.storage import SQLiteRepository


class FakeAdapter:
    def __init__(self, responses: list[SubagentResponse]) -> None:
        self._responses = list(responses)

    def complete(self, messages: list[dict[str, str]]) -> SubagentResponse:
        if not self._responses:
            raise AssertionError("No fake responses remaining")
        return self._responses.pop(0)


def _run_tool(server, tool_name: str, arguments: dict[str, object]):
    tools = asyncio.run(server.get_tools())
    result = asyncio.run(tools[tool_name].run(arguments))
    return json.loads(result[0].text)


def test_fake_local_model_round_trip(tmp_path: Path):
    config = AppConfig.from_env(
        {
            "LOCAL_SUBAGENT_DATABASE_PATH": str(tmp_path / "runs.db"),
            "LOCAL_SUBAGENT_EXPORT_DIR": str(tmp_path / "exports"),
            "LOCAL_SUBAGENT_MODEL_NAME": "qwen3",
        }
    )
    service = SubagentService(
        config=config,
        repository=SQLiteRepository(config.database_path),
        adapter=FakeAdapter(
            [
                SubagentResponse(
                    message="Need the current directory.",
                    tool_requests=[
                        ToolRequest(
                            name="shell",
                            arguments={"cmd": "pwd"},
                            reason="Locate the repository root",
                            risk_label="low",
                        )
                    ],
                    done=False,
                ),
                SubagentResponse(
                    message="Repository inspection complete.",
                    done=True,
                    confidence=0.95,
                ),
            ]
        ),
    )
    server = create_server(config=config, service=service)

    start = _run_tool(
        server,
        "subagent_start_task",
        {
            "task": "Inspect the repository",
            "context": {"files": ["README.md"]},
        },
    )
    tool_request_id = start["tool_requests"][0]["tool_request_id"]

    step = _run_tool(
        server,
        "subagent_submit_tool_result",
        {
            "run_id": start["run_id"],
            "tool_request_id": tool_request_id,
            "decision": "approved",
            "observation": "H:/_python/LocalSubagent",
        },
    )
    review = _run_tool(
        server,
        "subagent_record_review",
        {
            "run_id": start["run_id"],
            "score": 8,
            "errors": [],
            "improvements": ["keep the answer concise"],
            "missing_parts": [],
            "corrected_response": "Repository inspection complete.",
        },
    )
    export = _run_tool(
        server,
        "subagent_export_dataset",
        {
            "format": "raw_trace_jsonl",
            "run_id": start["run_id"],
        },
    )
    run_details = _run_tool(
        server,
        "subagent_get_run",
        {"run_id": start["run_id"]},
    )

    export_path = Path(export["export_path"])
    assert start["done"] is False
    assert step["done"] is True
    assert review["dataset_readiness"] == [
        "raw_trace_jsonl",
        "reward_jsonl",
        "sft_jsonl",
    ]
    assert export["record_count"] == 1
    assert export_path.exists()
    assert run_details["run"]["status"] == "reviewed"
    assert len(run_details["tool_requests"]) == 1
    assert json.loads(export_path.read_text(encoding="utf-8"))["run_id"] == start["run_id"]
