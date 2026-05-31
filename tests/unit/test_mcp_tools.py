from __future__ import annotations

import json
from pathlib import Path

from local_subagent.config import AppConfig
from local_subagent.runtime import SubagentResponse, ToolRequest
from local_subagent.service import SubagentService
from local_subagent.storage import SQLiteRepository


class FakeAdapter:
    def __init__(self, responses: list[SubagentResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> SubagentResponse:
        self.calls.append([dict(message) for message in messages])
        if not self._responses:
            raise AssertionError("No fake responses remaining")
        return self._responses.pop(0)


def _service(tmp_path: Path, responses: list[SubagentResponse]) -> tuple[SubagentService, SQLiteRepository, FakeAdapter]:
    config = AppConfig.from_env(
        {
            "LOCAL_SUBAGENT_DATABASE_PATH": str(tmp_path / "runs.db"),
            "LOCAL_SUBAGENT_EXPORT_DIR": str(tmp_path / "exports"),
            "LOCAL_SUBAGENT_MODEL_NAME": "qwen3",
        }
    )
    repository = SQLiteRepository(config.database_path)
    adapter = FakeAdapter(responses)
    return (
        SubagentService(config=config, repository=repository, adapter=adapter),
        repository,
        adapter,
    )


def test_start_task_persists_run_and_returns_initial_response(tmp_path: Path):
    service, repository, adapter = _service(
        tmp_path,
        [
            SubagentResponse(
                message="Need a directory listing.",
                tool_requests=[
                    ToolRequest(
                        name="shell",
                        arguments={"cmd": "pwd"},
                        reason="Need the current workspace path",
                        risk_label="low",
                    )
                ],
                done=False,
                confidence=0.4,
                assumptions=["The repository root is the current directory."],
            )
        ],
    )

    result = service.start_task(
        task="Inspect the repository layout",
        context={"files": ["README.md"]},
        model_profile={"model": "qwen3"},
    )

    assert result["run_id"]
    assert result["message"] == "Need a directory listing."
    assert result["done"] is False
    assert result["tool_requests"] == [
        {
            "tool_request_id": result["tool_requests"][0]["tool_request_id"],
            "name": "shell",
            "arguments": {"cmd": "pwd"},
            "reason": "Need the current workspace path",
            "risk_label": "low",
        }
    ]

    run = repository.get_run(result["run_id"])
    assert run is not None
    assert run.status == "awaiting_tool_review"
    assert len(repository.list_messages(result["run_id"])) == 2
    assert "Inspect the repository layout" in adapter.calls[0][-1]["content"]


def test_submit_tool_result_records_decision_and_completes_run(tmp_path: Path):
    service, repository, _ = _service(
        tmp_path,
        [
            SubagentResponse(
                message="Need shell output.",
                tool_requests=[
                    ToolRequest(name="shell", arguments={"cmd": "pwd"})
                ],
                done=False,
            ),
            SubagentResponse(
                message="The repo root is ready to inspect.",
                done=True,
                confidence=0.9,
            ),
        ],
    )

    start = service.start_task(task="Inspect the repo")
    tool_request_id = start["tool_requests"][0]["tool_request_id"]

    result = service.submit_tool_result(
        run_id=start["run_id"],
        tool_request_id=tool_request_id,
        decision="approved",
        observation="H:/_python/LocalSubagent",
    )

    assert result["done"] is True
    assert result["message"] == "The repo root is ready to inspect."
    assert repository.get_run(start["run_id"]).status == "completed"
    assert repository.list_tool_results(start["run_id"])[0].observation == "H:/_python/LocalSubagent"


def test_record_review_reports_dataset_readiness(tmp_path: Path):
    service, repository, _ = _service(
        tmp_path,
        [SubagentResponse(message="Done.", done=True)],
    )
    start = service.start_task(task="Answer a question")

    result = service.record_review(
        run_id=start["run_id"],
        score=8,
        errors=["missed a detail"],
        improvements=["add a concrete example"],
        missing_parts=[],
        corrected_response="Corrected answer",
        chosen="Corrected answer",
        rejected="Original answer",
    )

    assert result["review_id"]
    assert set(result["dataset_readiness"]) == {
        "raw_trace_jsonl",
        "sft_jsonl",
        "preference_jsonl",
        "reward_jsonl",
    }
    assert repository.get_review(start["run_id"]) is not None


def test_export_dataset_writes_jsonl_file(tmp_path: Path):
    service, _, _ = _service(
        tmp_path,
        [SubagentResponse(message="Done.", done=True)],
    )
    start = service.start_task(task="Summarize the repository")
    service.record_review(
        run_id=start["run_id"],
        score=7,
        errors=[],
        improvements=[],
        missing_parts=[],
        corrected_response="Summary",
    )

    result = service.export_dataset(format="raw_trace_jsonl", run_id=start["run_id"])
    export_path = Path(result["export_path"])

    assert result["record_count"] == 1
    assert export_path.exists()
    payload = json.loads(export_path.read_text(encoding="utf-8").strip())
    assert payload["run_id"] == start["run_id"]
