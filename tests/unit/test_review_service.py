from local_subagent.review.service import ReviewRecord, record_review


def test_record_review_marks_raw_trace_and_sft_ready_when_corrected_response_present():
    result = record_review(
        ReviewRecord(
            run_id="run-1",
            corrected_response="fixed answer",
        )
    )

    assert result.ready_formats == {"raw_trace_jsonl", "sft_jsonl"}


def test_record_review_marks_preference_and_reward_ready_when_labels_and_score_present():
    result = record_review(
        ReviewRecord(
            run_id="run-2",
            score=7,
            chosen="better answer",
            rejected="worse answer",
        )
    )

    assert result.ready_formats == {
        "raw_trace_jsonl",
        "preference_jsonl",
        "reward_jsonl",
    }
