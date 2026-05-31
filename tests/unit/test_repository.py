from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from local_subagent.domain import (
    ExportRecord,
    MessageRecord,
    ReviewRecord,
    RunRecord,
    ToolRequestRecord,
    ToolResultRecord,
)
from local_subagent.storage import SQLiteRepository


def _utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_repository_persists_all_core_records(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "runs.db")
    run = RunRecord(
        run_id="run-1",
        task="Summarize the test plan",
        model_name="qwen3",
        status="active",
        created_at=_utc("2026-06-01T01:00:00Z"),
        updated_at=_utc("2026-06-01T01:00:00Z"),
    )

    repository.create_run(run)

    message = MessageRecord(
        message_id="msg-1",
        run_id="run-1",
        role="assistant",
        content="I need to inspect the repo.",
        sequence=1,
        created_at=_utc("2026-06-01T01:00:01Z"),
    )
    repository.add_message(message)

    tool_request = ToolRequestRecord(
        tool_request_id="tool-request-1",
        run_id="run-1",
        message_id="msg-1",
        tool_name="read_file",
        arguments={"path": "README.md"},
        reason="Need context",
        risk_label="low",
        created_at=_utc("2026-06-01T01:00:02Z"),
    )
    repository.add_tool_request(tool_request)

    tool_result = ToolResultRecord(
        tool_result_id="tool-result-1",
        run_id="run-1",
        tool_request_id="tool-request-1",
        decision="approved",
        observation="README content read",
        created_at=_utc("2026-06-01T01:00:03Z"),
    )
    repository.add_tool_result(tool_result)

    review = ReviewRecord(
        review_id="review-1",
        run_id="run-1",
        score=7,
        errors=["None"],
        improvements=["Add more examples"],
        missing_parts=["Edge cases"],
        corrected_response="Updated answer",
        chosen="updated answer",
        rejected="original answer",
        created_at=_utc("2026-06-01T01:00:04Z"),
    )
    repository.add_review(review)

    export = ExportRecord(
        export_id="export-1",
        run_id="run-1",
        format="raw_trace_jsonl",
        path="exports/run-1.jsonl",
        record_count=5,
        filters={"model_name": "qwen3"},
        created_at=_utc("2026-06-01T01:00:05Z"),
    )
    repository.add_export(export)

    assert repository.get_run("run-1") == run
    assert repository.list_runs() == [run]
    assert repository.list_messages("run-1") == [message]
    assert repository.list_tool_requests("run-1") == [tool_request]
    assert repository.list_tool_results("run-1") == [tool_result]
    assert repository.get_review("run-1") == review
    assert repository.list_exports("run-1") == [export]


def test_repository_updates_run_status(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "runs.db")
    run = RunRecord(
        run_id="run-2",
        task="Write a short summary",
        model_name="qwen3",
        status="active",
        created_at=_utc("2026-06-01T02:00:00Z"),
        updated_at=_utc("2026-06-01T02:00:00Z"),
    )
    repository.create_run(run)

    updated = repository.update_run_status(
        "run-2",
        status="completed",
        updated_at=_utc("2026-06-01T02:10:00Z"),
    )

    assert updated.status == "completed"
    assert updated.updated_at == _utc("2026-06-01T02:10:00Z")
    assert repository.get_run("run-2") == updated


def test_repository_allows_sparse_review_records(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "runs.db")
    run = RunRecord(
        run_id="run-3",
        task="Review an answer",
        model_name="qwen3",
        status="active",
        created_at=_utc("2026-06-01T03:00:00Z"),
        updated_at=_utc("2026-06-01T03:00:00Z"),
    )
    repository.create_run(run)

    review = ReviewRecord(
        review_id="review-3",
        run_id="run-3",
        score=None,
        errors=[],
        improvements=[],
        missing_parts=[],
        corrected_response=None,
        chosen=None,
        rejected=None,
        created_at=_utc("2026-06-01T03:00:01Z"),
    )

    repository.add_review(review)

    assert repository.get_review("run-3") == review


def test_repository_allows_sparse_tool_request_metadata(tmp_path: Path):
    repository = SQLiteRepository(tmp_path / "runs.db")
    run = RunRecord(
        run_id="run-4",
        task="Inspect a workspace",
        model_name="qwen3",
        status="active",
        created_at=_utc("2026-06-01T04:00:00Z"),
        updated_at=_utc("2026-06-01T04:00:00Z"),
    )
    repository.create_run(run)

    message = MessageRecord(
        message_id="msg-4",
        run_id="run-4",
        role="assistant",
        content="Need a tool.",
        sequence=1,
        created_at=_utc("2026-06-01T04:00:01Z"),
    )
    repository.add_message(message)

    tool_request = ToolRequestRecord(
        tool_request_id="tool-request-4",
        run_id="run-4",
        message_id="msg-4",
        tool_name="shell",
        arguments={"cmd": "pwd"},
        reason=None,
        risk_label=None,
        created_at=_utc("2026-06-01T04:00:02Z"),
    )

    repository.add_tool_request(tool_request)

    assert repository.list_tool_requests("run-4") == [tool_request]
