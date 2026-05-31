from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from local_subagent.config import AppConfig
from local_subagent.domain import (
    ExportRecord,
    MessageRecord,
    ReviewRecord as StoredReviewRecord,
    RunRecord,
    ToolRequestRecord,
    ToolResultRecord,
)
from local_subagent.exporters.jsonl import (
    TraceRecord,
    export_preference,
    export_raw_trace,
    export_reward,
    export_sft,
)
from local_subagent.review.service import ReviewRecord as ReviewInputRecord
from local_subagent.review.service import record_review
from local_subagent.runtime import LocalModelAdapter, SubagentResponse
from local_subagent.storage import SQLiteRepository


class SubagentService:
    def __init__(
        self,
        *,
        config: AppConfig,
        repository: SQLiteRepository,
        adapter: LocalModelAdapter,
    ) -> None:
        self._config = config
        self._repository = repository
        self._adapter = adapter

    @classmethod
    def from_config(cls, config: AppConfig) -> "SubagentService":
        return cls(
            config=config,
            repository=SQLiteRepository(config.database_path),
            adapter=LocalModelAdapter(
                base_url=config.model_base_url,
                api_key=config.model_api_key,
                model_name=config.model_name,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            ),
        )

    def start_task(
        self,
        *,
        task: str,
        context: Mapping[str, Any] | None = None,
        model_profile: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = _now()
        run_id = _new_id("run")
        run = RunRecord(
            run_id=run_id,
            task=task,
            model_name=str((model_profile or {}).get("model", self._config.model_name)),
            status="running",
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._repository.create_run(run)

        user_message = MessageRecord(
            message_id=_new_id("msg"),
            run_id=run_id,
            role="user",
            content=_compose_task_message(task, context=context, model_profile=model_profile),
            sequence=1,
            created_at=timestamp,
        )
        self._repository.add_message(user_message)

        response = self._adapter.complete(_conversation_for_model(run_id, self._repository))
        return self._store_response(run_id, response)

    def step(
        self,
        *,
        run_id: str,
        message: str,
        context_delta: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_run(run_id)
        sequence = len(self._repository.list_messages(run_id)) + 1
        self._repository.add_message(
            MessageRecord(
                message_id=_new_id("msg"),
                run_id=run_id,
                role="user",
                content=_compose_follow_up_message(message, context_delta=context_delta),
                sequence=sequence,
                created_at=_now(),
            )
        )
        response = self._adapter.complete(_conversation_for_model(run_id, self._repository))
        return self._store_response(run_id, response)

    def submit_tool_result(
        self,
        *,
        run_id: str,
        tool_request_id: str,
        decision: str,
        observation: str,
    ) -> dict[str, Any]:
        self._require_run(run_id)
        tool_request = self._repository.get_tool_request(tool_request_id)
        if tool_request is None:
            raise ValueError(f"Unknown tool_request_id: {tool_request_id}")
        if tool_request.run_id != run_id:
            raise ValueError(
                f"Tool request {tool_request_id} does not belong to run {run_id}"
            )
        if self._repository.get_tool_result_for_request(tool_request_id) is not None:
            raise ValueError(
                f"Tool request {tool_request_id} already has a recorded result"
            )
        self._repository.add_tool_result(
            ToolResultRecord(
                tool_result_id=_new_id("tool_result"),
                run_id=run_id,
                tool_request_id=tool_request_id,
                decision=decision,
                observation=observation,
                created_at=_now(),
            )
        )
        return self.step(
            run_id=run_id,
            message=(
                f"Tool request {tool_request_id} was {decision}. "
                f"Observation: {observation}"
            ),
        )

    def record_review(
        self,
        *,
        run_id: str,
        score: int | None = None,
        errors: list[str] | None = None,
        improvements: list[str] | None = None,
        missing_parts: list[str] | None = None,
        corrected_response: str | None = None,
        chosen: str | None = None,
        rejected: str | None = None,
    ) -> dict[str, Any]:
        self._require_run(run_id)
        if self._repository.get_review(run_id) is not None:
            raise ValueError(f"Run {run_id} already has a stored review")
        timestamp = _now()
        stored_review = StoredReviewRecord(
            review_id=_new_id("review"),
            run_id=run_id,
            score=score,
            errors=list(errors or []),
            improvements=list(improvements or []),
            missing_parts=list(missing_parts or []),
            corrected_response=corrected_response,
            chosen=chosen,
            rejected=rejected,
            created_at=timestamp,
        )
        self._repository.add_review(stored_review)

        assessment = record_review(
            ReviewInputRecord(
                run_id=run_id,
                score=score,
                errors=list(errors or []),
                improvements=list(improvements or []),
                missing_parts=list(missing_parts or []),
                corrected_response=corrected_response,
                chosen=chosen,
                rejected=rejected,
            )
        )
        self._repository.update_run_status(
            run_id,
            status="reviewed",
            updated_at=timestamp,
        )
        return {
            "review_id": stored_review.review_id,
            "dataset_readiness": sorted(assessment.ready_formats),
        }

    def export_dataset(
        self,
        *,
        format: str,
        run_id: str | None = None,
        filters: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if format not in {
            "raw_trace_jsonl",
            "sft_jsonl",
            "preference_jsonl",
            "reward_jsonl",
        }:
            raise ValueError(f"Unsupported export format: {format}")

        runs = [self._require_run(run_id)] if run_id else self._repository.list_runs()
        lines: list[str] = []
        exported_run_ids: list[str] = []
        for run in runs:
            line = self._export_line_for_run(run.run_id, format)
            if line is None:
                continue
            lines.append(line)
            exported_run_ids.append(run.run_id)

        export_dir = Path(self._config.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        export_path = export_dir / f"{format}-{_new_id('export')}.jsonl"
        export_path.write_text(
            "\n".join(lines) + ("\n" if lines else ""),
            encoding="utf-8",
        )

        self._repository.add_export(
            ExportRecord(
                export_id=_new_id("export_record"),
                run_id=run_id if len(exported_run_ids) == 1 else None,
                format=format,
                path=str(export_path),
                record_count=len(lines),
                filters=dict(filters or {}),
                created_at=_now(),
            )
        )

        return {
            "export_path": str(export_path),
            "record_count": len(lines),
        }

    def get_run(self, *, run_id: str) -> dict[str, Any]:
        run = self._require_run(run_id)
        review = self._repository.get_review(run_id)
        return {
            "run": _serialize(run),
            "messages": [_serialize(item) for item in self._repository.list_messages(run_id)],
            "tool_requests": [
                _serialize(item) for item in self._repository.list_tool_requests(run_id)
            ],
            "tool_results": [
                _serialize(item) for item in self._repository.list_tool_results(run_id)
            ],
            "review": _serialize(review) if review is not None else None,
        }

    def list_runs(self) -> list[dict[str, Any]]:
        return [_serialize(run) for run in self._repository.list_runs()]

    def _store_response(
        self,
        run_id: str,
        response: SubagentResponse,
    ) -> dict[str, Any]:
        timestamp = _now()
        sequence = len(self._repository.list_messages(run_id)) + 1
        message = MessageRecord(
            message_id=_new_id("msg"),
            run_id=run_id,
            role="assistant",
            content=response.message,
            sequence=sequence,
            created_at=timestamp,
        )
        self._repository.add_message(message)

        stored_requests: list[dict[str, Any]] = []
        for request in response.tool_requests:
            tool_request = ToolRequestRecord(
                tool_request_id=_new_id("tool_request"),
                run_id=run_id,
                message_id=message.message_id,
                tool_name=request.name,
                arguments=request.arguments,
                reason=request.reason,
                risk_label=request.risk_label,
                created_at=timestamp,
            )
            self._repository.add_tool_request(tool_request)
            stored_requests.append(
                {
                    "tool_request_id": tool_request.tool_request_id,
                    "name": tool_request.tool_name,
                    "arguments": dict(tool_request.arguments),
                    "reason": tool_request.reason,
                    "risk_label": tool_request.risk_label,
                }
            )

        status = "completed" if response.done else (
            "awaiting_tool_review" if stored_requests else "running"
        )
        self._repository.update_run_status(run_id, status=status, updated_at=timestamp)

        return {
            "run_id": run_id,
            "message": response.message,
            "tool_requests": stored_requests,
            "done": response.done,
            "confidence": response.confidence,
            "assumptions": list(response.assumptions),
        }

    def _require_run(self, run_id: str | None) -> RunRecord:
        if run_id is None:
            raise ValueError("run_id is required")
        run = self._repository.get_run(run_id)
        if run is None:
            raise ValueError(f"Unknown run_id: {run_id}")
        return run

    def _export_line_for_run(self, run_id: str, format: str) -> str | None:
        trace = TraceRecord(
            run_id=run_id,
            task=self._require_run(run_id).task,
            messages=[
                {"role": message.role, "content": message.content}
                for message in self._repository.list_messages(run_id)
            ],
            tool_requests=[
                {
                    "tool_request_id": request.tool_request_id,
                    "name": request.tool_name,
                    "arguments": dict(request.arguments),
                    "reason": request.reason,
                    "risk_label": request.risk_label,
                }
                for request in self._repository.list_tool_requests(run_id)
            ],
            tool_results=[
                {
                    "tool_result_id": result.tool_result_id,
                    "tool_request_id": result.tool_request_id,
                    "decision": result.decision,
                    "observation": result.observation,
                }
                for result in self._repository.list_tool_results(run_id)
            ],
        )
        review = self._repository.get_review(run_id)
        review_input = _to_review_input(run_id, review)
        readiness = record_review(review_input).ready_formats
        if format != "raw_trace_jsonl" and format not in readiness:
            return None

        if format == "raw_trace_jsonl":
            return export_raw_trace(trace, review_input)
        if format == "sft_jsonl":
            return export_sft(trace, review_input)
        if format == "preference_jsonl":
            return export_preference(trace, review_input)
        return export_reward(trace, review_input)


def _compose_task_message(
    task: str,
    *,
    context: Mapping[str, Any] | None,
    model_profile: Mapping[str, Any] | None,
) -> str:
    sections = [task]
    if context:
        sections.append(f"Context:\n{json.dumps(dict(context), ensure_ascii=False, indent=2)}")
    if model_profile:
        sections.append(
            f"Model profile:\n{json.dumps(dict(model_profile), ensure_ascii=False, indent=2)}"
        )
    return "\n\n".join(sections)


def _compose_follow_up_message(
    message: str,
    *,
    context_delta: Mapping[str, Any] | None,
) -> str:
    if not context_delta:
        return message
    return (
        f"{message}\n\n"
        f"Context update:\n{json.dumps(dict(context_delta), ensure_ascii=False, indent=2)}"
    )


def _conversation_for_model(
    run_id: str,
    repository: SQLiteRepository,
) -> list[dict[str, str]]:
    return [
        {"role": message.role, "content": message.content}
        for message in repository.list_messages(run_id)
    ]


def _to_review_input(
    run_id: str,
    review: StoredReviewRecord | None,
) -> ReviewInputRecord:
    if review is None:
        return ReviewInputRecord(run_id=run_id)
    return ReviewInputRecord(
        run_id=run_id,
        score=review.score,
        errors=list(review.errors),
        improvements=list(review.improvements),
        missing_parts=list(review.missing_parts),
        corrected_response=review.corrected_response,
        chosen=review.chosen,
        rejected=review.rejected,
    )


def _serialize(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "__dataclass_fields__"):
        return _serialize(asdict(value))
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return value


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)
