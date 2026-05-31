from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ReviewRecord:
    run_id: str
    score: int | None = None
    errors: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    missing_parts: list[str] = field(default_factory=list)
    corrected_response: str | None = None
    chosen: str | None = None
    rejected: str | None = None


@dataclass(slots=True)
class ReviewAssessment:
    review: ReviewRecord
    ready_formats: set[str]


def record_review(review: ReviewRecord) -> ReviewAssessment:
    ready_formats: set[str] = {"raw_trace_jsonl"}

    if _has_text(review.corrected_response):
        ready_formats.add("sft_jsonl")

    if _has_text(review.chosen) and _has_text(review.rejected):
        ready_formats.add("preference_jsonl")

    if review.score is not None:
        ready_formats.add("reward_jsonl")

    return ReviewAssessment(review=review, ready_formats=ready_formats)


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())
