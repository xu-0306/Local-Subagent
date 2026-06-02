from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class RunRecord:
    run_id: str
    task: str
    model_name: str
    runtime_profile: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MessageRecord:
    message_id: str
    run_id: str
    role: str
    content: str
    sequence: int
    created_at: datetime


@dataclass(slots=True)
class ToolRequestRecord:
    tool_request_id: str
    run_id: str
    message_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str | None
    risk_label: str | None
    created_at: datetime


@dataclass(slots=True)
class ToolResultRecord:
    tool_result_id: str
    run_id: str
    tool_request_id: str
    decision: str
    observation: str
    created_at: datetime


@dataclass(slots=True)
class ReviewRecord:
    review_id: str
    run_id: str
    score: int | None
    errors: list[str]
    improvements: list[str]
    missing_parts: list[str]
    corrected_response: str | None
    chosen: str | None
    rejected: str | None
    created_at: datetime


@dataclass(slots=True)
class ExportRecord:
    export_id: str
    run_id: str | None
    format: str
    path: str
    record_count: int
    filters: dict[str, Any]
    created_at: datetime
