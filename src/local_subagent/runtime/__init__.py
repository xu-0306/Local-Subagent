"""Runtime helpers for local model interaction."""

from local_subagent.runtime.adapter import LocalModelAdapter
from local_subagent.runtime.prompts import SUBAGENT_SYSTEM_PROMPT
from local_subagent.runtime.protocol import (
    SubagentResponse,
    ToolRequest,
    parse_subagent_response,
)

__all__ = [
    "LocalModelAdapter",
    "SUBAGENT_SYSTEM_PROMPT",
    "SubagentResponse",
    "ToolRequest",
    "parse_subagent_response",
]
