"""Runtime helpers for local model interaction."""

from local_subagent.runtime.adapter import LocalModelAdapter
from local_subagent.runtime.onboarding import build_runtime_settings, list_runtime_presets
from local_subagent.runtime.presets import RUNTIME_PRESETS, get_runtime_preset
from local_subagent.runtime.prompts import SUBAGENT_SYSTEM_PROMPT
from local_subagent.runtime.protocol import (
    SubagentResponse,
    ToolRequest,
    parse_subagent_response,
)

__all__ = [
    "LocalModelAdapter",
    "RUNTIME_PRESETS",
    "SUBAGENT_SYSTEM_PROMPT",
    "SubagentResponse",
    "ToolRequest",
    "build_runtime_settings",
    "get_runtime_preset",
    "list_runtime_presets",
    "parse_subagent_response",
]
