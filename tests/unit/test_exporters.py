import json

from local_subagent.exporters.jsonl import (
    TraceRecord,
    ReviewRecord,
    export_preference,
    export_raw_trace,
    export_reward,
    export_sft,
)


def test_export_raw_trace_includes_review_payload():
    line = export_raw_trace(
        TraceRecord(
            run_id="run-1",
            task="solve a bug",
            messages=[{"role": "user", "content": "help"}],
            tool_requests=[],
            tool_results=[],
        ),
        ReviewRecord(run_id="run-1", score=8),
    )

    payload = json.loads(line)

    assert payload == {
        "run_id": "run-1",
        "task": "solve a bug",
        "messages": [{"role": "user", "content": "help"}],
        "tool_requests": [],
        "tool_results": [],
        "review": {"run_id": "run-1", "score": 8},
    }


def test_export_sft_appends_corrected_answer():
    line = export_sft(
        TraceRecord(
            run_id="run-1",
            task="solve a bug",
            messages=[
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "original question"},
            ],
            tool_requests=[],
            tool_results=[],
        ),
        ReviewRecord(run_id="run-1", corrected_response="corrected response"),
    )

    payload = json.loads(line)

    assert payload == {
        "messages": [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "original question"},
            {"role": "assistant", "content": "corrected response"},
        ],
        "metadata": {"run_id": "run-1", "source": "local-subagent-review"},
    }


def test_export_preference_uses_user_prompt_and_review_labels():
    line = export_preference(
        TraceRecord(
            run_id="run-1",
            task="solve a bug",
            messages=[{"role": "user", "content": "original question"}],
            tool_requests=[],
            tool_results=[],
        ),
        ReviewRecord(
            run_id="run-1",
            chosen="better answer",
            rejected="worse answer",
        ),
    )

    payload = json.loads(line)

    assert payload == {
        "prompt": "original question",
        "chosen": "better answer",
        "rejected": "worse answer",
        "metadata": {"run_id": "run-1"},
    }


def test_export_reward_uses_score_and_review_notes():
    line = export_reward(
        TraceRecord(
            run_id="run-1",
            task="solve a bug",
            messages=[{"role": "user", "content": "original question"}],
            tool_requests=[],
            tool_results=[],
        ),
        ReviewRecord(
            run_id="run-1",
            score=7,
            errors=["missed edge case"],
            improvements=["add validation"],
            corrected_response="corrected response",
        ),
    )

    payload = json.loads(line)

    assert payload == {
        "prompt": "original question",
        "response": "corrected response",
        "score": 7,
        "review": {
            "errors": ["missed edge case"],
            "improvements": ["add validation"],
        },
    }
