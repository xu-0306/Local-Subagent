import pytest

from local_subagent.runtime.protocol import (
    SubagentResponse,
    parse_subagent_response,
)


def test_parse_subagent_response_with_tool_requests():
    payload = {
        "message": "Need directory listing.",
        "tool_requests": [
            {
                "name": "shell",
                "arguments": {"cmd": "ls"},
                "reason": "Inspect the workspace",
                "risk_label": "low",
            }
        ],
        "done": False,
        "confidence": 0.62,
        "assumptions": ["The current directory is the project root."],
    }

    response = parse_subagent_response(payload)

    assert isinstance(response, SubagentResponse)
    assert response.message == "Need directory listing."
    assert response.done is False
    assert response.confidence == 0.62
    assert response.assumptions == ["The current directory is the project root."]
    assert len(response.tool_requests) == 1
    assert response.tool_requests[0].name == "shell"
    assert response.tool_requests[0].arguments == {"cmd": "ls"}
    assert response.tool_requests[0].reason == "Inspect the workspace"
    assert response.tool_requests[0].risk_label == "low"


def test_parse_subagent_response_defaults_optional_fields():
    response = parse_subagent_response({"message": "Finished.", "done": True})

    assert response.tool_requests == []
    assert response.assumptions == []
    assert response.confidence is None


def test_parse_subagent_response_rejects_invalid_tool_request():
    payload = {
        "message": "Need a tool.",
        "tool_requests": [{"arguments": {"cmd": "ls"}}],
        "done": False,
    }

    with pytest.raises(ValueError, match="tool_requests\\[0\\]"):
        parse_subagent_response(payload)
