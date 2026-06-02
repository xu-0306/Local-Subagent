from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from local_subagent.config import AppConfig
from local_subagent.config import save_runtime_config_file
from local_subagent.domain import (
    ExportRecord,
    MessageRecord,
    ReviewRecord as StoredReviewRecord,
    RunRecord,
    ToolRequestRecord,
    ToolResultRecord,
)
from local_subagent.errors import LocalSubagentError
from local_subagent.exporters.jsonl import (
    TraceRecord,
    export_preference,
    export_raw_trace,
    export_reward,
    export_sft,
)
from local_subagent.review.service import ReviewRecord as ReviewInputRecord
from local_subagent.review.service import record_review
from local_subagent.runtime import (
    LocalModelAdapter,
    SubagentResponse,
    build_runtime_settings,
    list_runtime_presets,
)
from local_subagent.storage import SQLiteRepository

SUPPORTED_MODEL_PROFILE_KEYS = {"model", "temperature", "max_tokens"}
SUPPORTED_EXPORT_FILTER_KEYS = {
    "model_name",
    "status",
    "min_score",
    "max_score",
    "created_after",
    "created_before",
}


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
        _validate_allowed_keys(
            model_profile,
            allowed_keys=SUPPORTED_MODEL_PROFILE_KEYS,
            error_prefix="Unsupported model_profile keys",
        )
        timestamp = _now()
        run_id = _new_id("run")
        runtime_profile = _runtime_overrides(model_profile)
        run = RunRecord(
            run_id=run_id,
            task=task,
            model_name=runtime_profile.get("model_name", self._config.model_name),
            runtime_profile=runtime_profile,
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

        response = self._adapter.complete(
            _conversation_for_model(run_id, self._repository),
            **runtime_profile,
        )
        return self._store_response(run_id, response)

    def get_runtime_status(self) -> dict[str, Any]:
        return {
            "runtime_provider": self._config.runtime_provider,
            "runtime_source": self._config.runtime_source,
            "config_path": str(self._config.config_path),
            "needs_setup": self._config.runtime_source == "defaults",
            "effective_config": {
                "provider": self._config.runtime_provider,
                "api_url": self._config.model_base_url,
                "api_key_present": bool(self._config.model_api_key),
                "model_name": self._config.model_name,
                "temperature": self._config.temperature,
                "max_tokens": self._config.max_tokens,
            },
            "next_step": _runtime_next_step(self._config.runtime_source),
        }

    def list_runtime_presets(self) -> dict[str, Any]:
        return {
            "presets": list_runtime_presets(),
            "config_path": str(self._config.config_path),
        }

    def configure_runtime(
        self,
        *,
        provider: str,
        model_name: str | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        previous_runtime_source = self._config.runtime_source
        settings, missing_fields = build_runtime_settings(
            provider=provider,
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            fallback_model_name=self._config.model_name,
            fallback_temperature=self._config.temperature,
            fallback_max_tokens=self._config.max_tokens,
        )
        if missing_fields:
            missing = ", ".join(missing_fields)
            return {
                "saved": False,
                "provider": provider,
                "config_path": str(self._config.config_path),
                "missing_fields": missing_fields,
                "message": (
                    f"Ask the user for {missing}, then call subagent_configure_runtime again, "
                    f"or edit {self._config.config_path} manually."
                ),
            }

        save_runtime_config_file(
            self._config.config_path,
            runtime_provider=str(settings["runtime_provider"]),
            model_base_url=str(settings["model_base_url"]),
            model_api_key=str(settings["model_api_key"]),
            model_name=str(settings["model_name"]),
            temperature=float(settings["temperature"]),
            max_tokens=int(settings["max_tokens"]),
        )
        self._apply_runtime_settings(settings, runtime_source="config_file")

        message = (
            "Runtime configuration saved. Validate the runtime before starting a subagent task."
        )
        if previous_runtime_source in {"env", "mixed"}:
            message = (
                "Runtime configuration saved, but environment variables may still override "
                "the config file for future launches. Validate the runtime before starting a task."
            )

        return {
            "saved": True,
            "provider": provider,
            "config_path": str(self._config.config_path),
            "effective_config": {
                "api_url": self._config.model_base_url,
                "api_key_present": bool(self._config.model_api_key),
                "model_name": self._config.model_name,
                "temperature": self._config.temperature,
                "max_tokens": self._config.max_tokens,
            },
            "message": message,
        }

    def validate_runtime(
        self,
        *,
        provider: str | None = None,
        model_name: str | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        runtime_provider = provider or self._config.runtime_provider
        settings, missing_fields = build_runtime_settings(
            provider=runtime_provider,
            api_url=api_url,
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            fallback_model_name=self._config.model_name,
            fallback_temperature=self._config.temperature,
            fallback_max_tokens=self._config.max_tokens,
        )
        if missing_fields:
            missing = ", ".join(missing_fields)
            return {
                "ok": False,
                "provider": runtime_provider,
                "message": (
                    f"Runtime validation needs {missing} before it can connect. "
                    f"Ask the user for the missing values or edit {self._config.config_path}."
                ),
                "missing_fields": missing_fields,
            }

        try:
            payload = self._adapter.validate_connection(
                base_url=str(settings["model_base_url"]),
                api_key=str(settings["model_api_key"]),
            )
        except LocalSubagentError as exc:
            return {
                "ok": False,
                "provider": runtime_provider,
                "api_url": str(settings["model_base_url"]),
                "model_name": str(settings["model_name"]),
                "message": str(exc),
                "available_models": [],
                "model_available": False,
            }

        available_models = [
            item
            for item in payload.get("available_models", [])
            if isinstance(item, str)
        ]
        selected_model = str(settings["model_name"])
        model_available = selected_model in available_models if available_models else True
        if model_available:
            message = (
                f"Connected to {runtime_provider} at {settings['model_base_url']} and the model "
                f"{selected_model} is available."
            )
        else:
            message = (
                f"Connected to {runtime_provider} at {settings['model_base_url']}, but the configured "
                f"model {selected_model} was not listed by /models."
            )
        return {
            "ok": model_available,
            "provider": runtime_provider,
            "api_url": str(settings["model_base_url"]),
            "model_name": selected_model,
            "available_models": available_models,
            "model_available": model_available,
            "message": message,
        }

    def step(
        self,
        *,
        run_id: str,
        message: str,
        context_delta: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        run = self._require_run(run_id)
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
        response = self._adapter.complete(
            _conversation_for_model(run_id, self._repository),
            **run.runtime_profile,
        )
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
            raise LocalSubagentError(
                f"Unknown tool_request_id: {tool_request_id}. Fetch the run again before "
                "submitting a tool result."
            )
        if tool_request.run_id != run_id:
            raise LocalSubagentError(
                f"Tool request {tool_request_id} does not belong to run {run_id}. "
                "Use the tool request from the same run."
            )
        if self._repository.get_tool_result_for_request(tool_request_id) is not None:
            raise LocalSubagentError(
                f"Tool request {tool_request_id} already has a recorded result. "
                "Do not submit the same tool request twice."
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
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        self._require_run(run_id)
        existing_review = self._repository.get_review(run_id)
        if existing_review is not None and not replace_existing:
            raise LocalSubagentError(
                f"Run {run_id} already has a stored review. Use the existing review or "
                "clear it before recording another."
            )
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
        if existing_review is None:
            self._repository.add_review(stored_review)
        else:
            self._repository.replace_review(stored_review)

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
        _validate_allowed_keys(
            filters,
            allowed_keys=SUPPORTED_EXPORT_FILTER_KEYS,
            error_prefix="Unsupported export filters",
        )
        if format not in {
            "raw_trace_jsonl",
            "sft_jsonl",
            "preference_jsonl",
            "reward_jsonl",
        }:
            raise LocalSubagentError(
                f"Unsupported export format: {format}. Use raw_trace_jsonl, "
                "sft_jsonl, preference_jsonl, or reward_jsonl."
            )

        runs = [self._require_run(run_id)] if run_id else self._repository.list_runs()
        runs = self._apply_export_filters(runs, filters=filters)
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

    def list_runs(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        model_name: str | None = None,
        status: str | None = None,
        min_score: int | None = None,
        max_score: int | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
    ) -> dict[str, Any]:
        if offset < 0:
            raise LocalSubagentError("offset must be greater than or equal to 0.")
        if limit is not None and limit < 1:
            raise LocalSubagentError("limit must be greater than or equal to 1.")

        runs = self._apply_export_filters(
            self._repository.list_runs(),
            filters={
                key: value
                for key, value in {
                    "model_name": model_name,
                    "status": status,
                    "min_score": min_score,
                    "max_score": max_score,
                    "created_after": created_after,
                    "created_before": created_before,
                }.items()
                if value is not None
            },
        )
        total_count = len(runs)
        page = runs[offset:]
        if limit is not None:
            page = page[:limit]
        count = len(page)
        next_offset = offset + count if offset + count < total_count else None
        return {
            "items": [_serialize(run) for run in page],
            "count": count,
            "offset": offset,
            "limit": limit,
            "has_more": next_offset is not None,
            "next_offset": next_offset,
            "total_count": total_count,
        }

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
            raise LocalSubagentError("run_id is required.")
        run = self._repository.get_run(run_id)
        if run is None:
            raise LocalSubagentError(
                f"Unknown run_id: {run_id}. Call subagent_list_runs or start a new task."
            )
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

    def _apply_export_filters(
        self,
        runs: list[RunRecord],
        *,
        filters: Mapping[str, Any] | None,
    ) -> list[RunRecord]:
        if not filters:
            return runs

        filtered = runs

        model_name = filters.get("model_name")
        if model_name is not None:
            filtered = [run for run in filtered if run.model_name == model_name]

        status = filters.get("status")
        if status is not None:
            filtered = [run for run in filtered if run.status == status]

        created_after = filters.get("created_after")
        if created_after is not None:
            created_after_dt = _parse_filter_datetime(created_after, "created_after")
            filtered = [run for run in filtered if run.created_at > created_after_dt]

        created_before = filters.get("created_before")
        if created_before is not None:
            created_before_dt = _parse_filter_datetime(created_before, "created_before")
            filtered = [run for run in filtered if run.created_at < created_before_dt]

        min_score = filters.get("min_score")
        max_score = filters.get("max_score")
        if min_score is not None or max_score is not None:
            filtered = [
                run
                for run in filtered
                if _score_matches(
                    self._repository.get_review(run.run_id),
                    min_score=min_score,
                    max_score=max_score,
                )
            ]

        return filtered

    def _apply_runtime_settings(
        self,
        settings: Mapping[str, Any],
        *,
        runtime_source: str,
    ) -> None:
        self._config.runtime_provider = str(settings["runtime_provider"])
        self._config.runtime_source = runtime_source
        self._config.model_base_url = str(settings["model_base_url"])
        self._config.model_api_key = str(settings["model_api_key"])
        self._config.model_name = str(settings["model_name"])
        self._config.temperature = float(settings["temperature"])
        self._config.max_tokens = int(settings["max_tokens"])

        if isinstance(self._adapter, LocalModelAdapter):
            self._adapter = LocalModelAdapter(
                base_url=self._config.model_base_url,
                api_key=self._config.model_api_key,
                model_name=self._config.model_name,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
            )


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


def _parse_filter_datetime(raw: Any, field_name: str) -> datetime:
    if not isinstance(raw, str):
        raise LocalSubagentError(
            f"{field_name} must be an ISO-8601 datetime string."
        )
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError as exc:
        raise LocalSubagentError(
            f"{field_name} must be an ISO-8601 datetime string."
        ) from exc


def _score_matches(
    review: StoredReviewRecord | None,
    *,
    min_score: Any,
    max_score: Any,
) -> bool:
    if review is None or review.score is None:
        return False

    score = review.score
    if min_score is not None and score < int(min_score):
        return False
    if max_score is not None and score > int(max_score):
        return False
    return True


def _runtime_overrides(
    model_profile: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not model_profile:
        return {}

    overrides: dict[str, Any] = {}
    model_name = model_profile.get("model")
    if isinstance(model_name, str) and model_name:
        overrides["model_name"] = model_name

    temperature = model_profile.get("temperature")
    if temperature is not None:
        overrides["temperature"] = float(temperature)

    max_tokens = model_profile.get("max_tokens")
    if max_tokens is not None:
        overrides["max_tokens"] = int(max_tokens)

    return overrides


def _validate_allowed_keys(
    values: Mapping[str, Any] | None,
    *,
    allowed_keys: set[str],
    error_prefix: str,
) -> None:
    if not values:
        return

    unexpected = sorted(set(values) - allowed_keys)
    if not unexpected:
        return

    allowed = ", ".join(sorted(allowed_keys))
    unexpected_keys = ", ".join(unexpected)
    raise LocalSubagentError(
        f"{error_prefix}: {unexpected_keys}. Supported keys: {allowed}."
    )


def _runtime_next_step(runtime_source: str) -> str:
    if runtime_source == "defaults":
        return (
            "Ask the user which runtime they use, then call subagent_list_runtime_presets "
            "and subagent_configure_runtime before validating the connection."
        )
    if runtime_source == "mixed":
        return (
            "Runtime settings are split between environment variables and the config file. "
            "Validate the current connection and warn the user that environment variables override saved config."
        )
    if runtime_source == "env":
        return (
            "Runtime settings are coming from environment variables. Validate the connection or "
            "tell the user to edit those environment variables if changes are needed."
        )
    return (
        "Validate the current runtime connection before starting a subagent task."
    )
