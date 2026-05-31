from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from local_subagent.review.service import ReviewRecord


@dataclass(slots=True)
class TraceRecord:
    run_id: str
    task: str
    messages: Sequence[Mapping[str, Any]]
    tool_requests: Sequence[Mapping[str, Any]]
    tool_results: Sequence[Mapping[str, Any]]


def export_raw_trace(trace: TraceRecord, review: ReviewRecord) -> str:
    payload = {
        "run_id": trace.run_id,
        "task": trace.task,
        "messages": list(trace.messages),
        "tool_requests": list(trace.tool_requests),
        "tool_results": list(trace.tool_results),
        "review": _raw_review_payload(review),
    }
    return json.dumps(payload, ensure_ascii=False)


def export_sft(trace: TraceRecord, review: ReviewRecord) -> str:
    messages = [dict(message) for message in trace.messages]
    corrected_response = _first_text(review.corrected_response)
    if corrected_response is not None:
        messages.append({"role": "assistant", "content": corrected_response})

    payload = {
        "messages": messages,
        "metadata": {
            "run_id": trace.run_id,
            "source": "local-subagent-review",
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def export_preference(trace: TraceRecord, review: ReviewRecord) -> str:
    payload = {
        "prompt": _prompt_from_trace(trace),
        "chosen": review.chosen,
        "rejected": review.rejected,
        "metadata": {"run_id": trace.run_id},
    }
    return json.dumps(payload, ensure_ascii=False)


def export_reward(trace: TraceRecord, review: ReviewRecord) -> str:
    payload = {
        "prompt": _prompt_from_trace(trace),
        "response": _response_from_review(review),
        "score": review.score,
        "review": {
            "errors": list(review.errors),
            "improvements": list(review.improvements),
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _raw_review_payload(review: ReviewRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {"run_id": review.run_id}
    if review.score is not None:
        payload["score"] = review.score
    if review.chosen is not None:
        payload["chosen"] = review.chosen
    if review.rejected is not None:
        payload["rejected"] = review.rejected
    if review.corrected_response is not None:
        payload["corrected_response"] = review.corrected_response
    if review.errors:
        payload["errors"] = list(review.errors)
    if review.improvements:
        payload["improvements"] = list(review.improvements)
    if review.missing_parts:
        payload["missing_parts"] = list(review.missing_parts)
    return payload


def _prompt_from_trace(trace: TraceRecord) -> str:
    for message in trace.messages:
        if message.get("role") == "user":
            content = _first_text(message.get("content"))
            if content is not None:
                return content
    last_message = trace.messages[-1] if trace.messages else {}
    content = _first_text(last_message.get("content"))
    return content or ""


def _response_from_review(review: ReviewRecord) -> str:
    content = _first_text(review.corrected_response)
    return content or ""


def _first_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None
