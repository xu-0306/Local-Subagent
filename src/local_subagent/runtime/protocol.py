from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]
    reason: str | None = None
    risk_label: str | None = None


@dataclass(slots=True)
class SubagentResponse:
    message: str
    tool_requests: list[ToolRequest] = field(default_factory=list)
    done: bool = False
    confidence: float | None = None
    assumptions: list[str] = field(default_factory=list)


def parse_subagent_response(payload: Mapping[str, Any]) -> SubagentResponse:
    message = payload.get("message")
    done = payload.get("done")
    tool_requests = payload.get("tool_requests", [])
    confidence = payload.get("confidence")
    assumptions = payload.get("assumptions", [])

    if not isinstance(message, str):
        raise ValueError("message must be a string")
    if not isinstance(done, bool):
        raise ValueError("done must be a boolean")
    if not isinstance(tool_requests, list):
        raise ValueError("tool_requests must be a list")
    if confidence is not None and not isinstance(confidence, int | float):
        raise ValueError("confidence must be numeric")
    if not isinstance(assumptions, list) or any(
        not isinstance(item, str) for item in assumptions
    ):
        raise ValueError("assumptions must be a list of strings")

    parsed_requests: list[ToolRequest] = []
    for index, item in enumerate(tool_requests):
        if not isinstance(item, Mapping):
            raise ValueError(f"tool_requests[{index}] must be an object")

        name = item.get("name")
        arguments = item.get("arguments")
        reason = item.get("reason")
        risk_label = item.get("risk_label")

        if not isinstance(name, str) or not name:
            raise ValueError(f"tool_requests[{index}].name must be a non-empty string")
        if not isinstance(arguments, Mapping):
            raise ValueError(f"tool_requests[{index}].arguments must be an object")
        if reason is not None and not isinstance(reason, str):
            raise ValueError(f"tool_requests[{index}].reason must be a string")
        if risk_label is not None and not isinstance(risk_label, str):
            raise ValueError(f"tool_requests[{index}].risk_label must be a string")

        parsed_requests.append(
            ToolRequest(
                name=name,
                arguments=dict(arguments),
                reason=reason,
                risk_label=risk_label,
            )
        )

    return SubagentResponse(
        message=message,
        tool_requests=parsed_requests,
        done=done,
        confidence=float(confidence) if confidence is not None else None,
        assumptions=list(assumptions),
    )
