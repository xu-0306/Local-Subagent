from __future__ import annotations

import os

from fastmcp import FastMCP

from local_subagent.config import AppConfig


def create_server(config: AppConfig | None = None) -> FastMCP:
    resolved = config or AppConfig.from_env(os.environ)
    instructions = (
        "Local mediated subagent server. The local model may propose responses "
        "and tool requests, but tool execution is always reviewed by the main agent."
    )
    return FastMCP(name=resolved.app_name, instructions=instructions)
