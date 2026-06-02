import os
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from local_subagent.config import AppConfig
from local_subagent.errors import LocalSubagentError
from local_subagent.service import SubagentService

def create_server(
    config: AppConfig | None = None,
    *,
    service: SubagentService | Any | None = None,
) -> FastMCP:
    resolved_config = config or AppConfig.from_env(os.environ)
    resolved_service = service or SubagentService.from_config(resolved_config)
    instructions = (
        "Local mediated subagent server. The local model may propose responses "
        "and tool requests, but tool execution is always reviewed by the main agent. "
        "Before first use, the main agent should inspect runtime status, ask the user "
        "which runtime they use if needed, configure the runtime, and validate the "
        "connection before starting subagent tasks."
    )
    mcp = FastMCP(name=resolved_config.app_name, instructions=instructions)

    def _tool_call(fn):
        try:
            return fn()
        except LocalSubagentError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        name="subagent_get_runtime_status",
        annotations={
            "title": "Get Runtime Status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def subagent_get_runtime_status() -> dict[str, Any]:
        """Inspect the current runtime setup and report the next onboarding step."""
        return _tool_call(lambda: resolved_service.get_runtime_status())

    @mcp.tool(
        name="subagent_list_runtime_presets",
        annotations={
            "title": "List Runtime Presets",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def subagent_list_runtime_presets() -> dict[str, Any]:
        """List supported local runtime presets and their expected inputs."""
        return _tool_call(lambda: resolved_service.list_runtime_presets())

    @mcp.tool(
        name="subagent_configure_runtime",
        annotations={
            "title": "Configure Runtime",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def subagent_configure_runtime(
        provider: Annotated[
            str,
            Field(
                min_length=1,
                description="Runtime provider preset such as ollama, vllm, lmstudio, llamacpp, or openai_compatible.",
            ),
        ],
        model_name: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional target model name. If omitted, the existing configured model name is reused.",
            ),
        ] = None,
        api_url: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional OpenAI-compatible /v1 base URL. Required for the custom openai_compatible preset.",
            ),
        ] = None,
        api_key: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional API key override. If omitted, the preset default or the existing value is used.",
            ),
        ] = None,
        temperature: Annotated[
            float | None,
            Field(
                default=None,
                description="Optional default sampling temperature saved to the runtime config.",
            ),
        ] = None,
        max_tokens: Annotated[
            int | None,
            Field(
                default=None,
                ge=1,
                description="Optional default max_tokens saved to the runtime config.",
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Save runtime settings to the local runtime config file or report the missing fields."""
        return _tool_call(
            lambda: resolved_service.configure_runtime(
                provider=provider,
                model_name=model_name,
                api_url=api_url,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

    @mcp.tool(
        name="subagent_validate_runtime",
        annotations={
            "title": "Validate Runtime",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    def subagent_validate_runtime(
        provider: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional runtime provider override for this validation attempt.",
            ),
        ] = None,
        model_name: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional model name override for this validation attempt.",
            ),
        ] = None,
        api_url: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional OpenAI-compatible /v1 base URL override for this validation attempt.",
            ),
        ] = None,
        api_key: Annotated[
            str | None,
            Field(
                default=None,
                description="Optional API key override for this validation attempt.",
            ),
        ] = None,
        temperature: Annotated[
            float | None,
            Field(
                default=None,
                description="Optional temperature override for this validation attempt.",
            ),
        ] = None,
        max_tokens: Annotated[
            int | None,
            Field(
                default=None,
                ge=1,
                description="Optional max_tokens override for this validation attempt.",
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Check whether the configured local runtime is reachable and whether the selected model is visible."""
        return _tool_call(
            lambda: resolved_service.validate_runtime(
                provider=provider,
                model_name=model_name,
                api_url=api_url,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

    @mcp.tool(
        name="subagent_start_task",
        annotations={
            "title": "Start Subagent Task",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    def subagent_start_task(
        task: Annotated[
            str,
            Field(min_length=1, description="User or main-agent task instruction."),
        ],
        context: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description="Optional context, file hints, constraints, or prior findings.",
            ),
        ] = None,
        model_profile: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description="Optional model selection or runtime parameter overrides.",
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Start a new subagent run and return its first response."""
        return _tool_call(
            lambda: resolved_service.start_task(
                task=task,
                context=context,
                model_profile=model_profile,
            )
        )

    @mcp.tool(
        name="subagent_step",
        annotations={
            "title": "Continue Subagent Run",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    def subagent_step(
        run_id: Annotated[
            str,
            Field(min_length=1, description="Existing run identifier."),
        ],
        message: Annotated[
            str,
            Field(
                min_length=1,
                description="Main-agent follow-up message or observation.",
            ),
        ],
        context_delta: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description="Optional incremental context for the next subagent step.",
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Continue an existing run with a main-agent message or observation."""
        return _tool_call(
            lambda: resolved_service.step(
                run_id=run_id,
                message=message,
                context_delta=context_delta,
            )
        )

    @mcp.tool(
        name="subagent_submit_tool_result",
        annotations={
            "title": "Submit Tool Review Result",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    def subagent_submit_tool_result(
        run_id: Annotated[
            str,
            Field(min_length=1, description="Existing run identifier."),
        ],
        tool_request_id: Annotated[
            str,
            Field(min_length=1, description="Tool request identifier to resolve."),
        ],
        decision: Annotated[
            Literal["approved", "rejected", "modified"],
            Field(description="Main-agent decision for the requested tool call."),
        ],
        observation: Annotated[
            str,
            Field(
                min_length=1,
                description="Observed result or reason returned to the subagent.",
            ),
        ],
    ) -> dict[str, Any]:
        """Record a tool review decision and continue the subagent run."""
        return _tool_call(
            lambda: resolved_service.submit_tool_result(
                run_id=run_id,
                tool_request_id=tool_request_id,
                decision=decision,
                observation=observation,
            )
        )

    @mcp.tool(
        name="subagent_record_review",
        annotations={
            "title": "Record Run Review",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def subagent_record_review(
        run_id: Annotated[
            str,
            Field(min_length=1, description="Run identifier to review."),
        ],
        score: Annotated[
            int | None,
            Field(
                default=None,
                ge=0,
                le=10,
                description="Optional scalar score for reward-style labeling.",
            ),
        ] = None,
        errors: Annotated[
            list[str] | None,
            Field(default=None, description="Observed mistakes or failures."),
        ] = None,
        improvements: Annotated[
            list[str] | None,
            Field(
                default=None,
                description="Concrete improvements that would make the response better.",
            ),
        ] = None,
        missing_parts: Annotated[
            list[str] | None,
            Field(
                default=None,
                description="Important missing pieces or omitted requirements.",
            ),
        ] = None,
        corrected_response: Annotated[
            str | None,
            Field(default=None, description="Optional corrected answer for SFT export."),
        ] = None,
        chosen: Annotated[
            str | None,
            Field(default=None, description="Preferred answer text for preference export."),
        ] = None,
        rejected: Annotated[
            str | None,
            Field(default=None, description="Rejected answer text for preference export."),
        ] = None,
        replace_existing: Annotated[
            bool,
            Field(
                default=False,
                description="When true, replace an existing review for the same run.",
            ),
        ] = False,
    ) -> dict[str, Any]:
        """Store review feedback and report which dataset exports are now ready."""
        return _tool_call(
            lambda: resolved_service.record_review(
                run_id=run_id,
                score=score,
                errors=errors or [],
                improvements=improvements or [],
                missing_parts=missing_parts or [],
                corrected_response=corrected_response,
                chosen=chosen,
                rejected=rejected,
                replace_existing=replace_existing,
            )
        )

    @mcp.tool(
        name="subagent_export_dataset",
        annotations={
            "title": "Export Dataset",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    def subagent_export_dataset(
        format: Annotated[
            Literal[
                "raw_trace_jsonl",
                "sft_jsonl",
                "preference_jsonl",
                "reward_jsonl",
            ],
            Field(description="Dataset export format."),
        ],
        run_id: Annotated[
            str | None,
            Field(description="Optional run identifier to export a single run."),
        ] = None,
        filters: Annotated[
            dict[str, Any] | None,
            Field(description="Optional export filters stored with export metadata."),
        ] = None,
    ) -> dict[str, Any]:
        """Export stored traces into JSONL dataset formats."""
        return _tool_call(
            lambda: resolved_service.export_dataset(
                format=format,
                run_id=run_id,
                filters=filters,
            )
        )

    @mcp.tool(
        name="subagent_get_run",
        annotations={
            "title": "Get Run Details",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def subagent_get_run(
        run_id: Annotated[
            str,
            Field(min_length=1, description="Run identifier to inspect."),
        ],
    ) -> dict[str, Any]:
        """Fetch one persisted run with its messages, tool reviews, and review data."""
        return _tool_call(lambda: resolved_service.get_run(run_id=run_id))

    @mcp.tool(
        name="subagent_list_runs",
        annotations={
            "title": "List Runs",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    def subagent_list_runs(
        limit: Annotated[
            int | None,
            Field(default=None, ge=1, description="Maximum runs to return."),
        ] = None,
        offset: Annotated[
            int,
            Field(default=0, ge=0, description="Number of matching runs to skip."),
        ] = 0,
        model_name: Annotated[
            str | None,
            Field(default=None, description="Optional model name filter."),
        ] = None,
        status: Annotated[
            str | None,
            Field(default=None, description="Optional run status filter."),
        ] = None,
        min_score: Annotated[
            int | None,
            Field(default=None, ge=0, le=10, description="Optional minimum review score."),
        ] = None,
        max_score: Annotated[
            int | None,
            Field(default=None, ge=0, le=10, description="Optional maximum review score."),
        ] = None,
        created_after: Annotated[
            str | None,
            Field(default=None, description="Optional ISO-8601 lower bound for run creation time."),
        ] = None,
        created_before: Annotated[
            str | None,
            Field(default=None, description="Optional ISO-8601 upper bound for run creation time."),
        ] = None,
    ) -> dict[str, Any]:
        """List stored runs for audit and debugging."""
        return _tool_call(
            lambda: resolved_service.list_runs(
                limit=limit,
                offset=offset,
                model_name=model_name,
                status=status,
                min_score=min_score,
                max_score=max_score,
                created_after=created_after,
                created_before=created_before,
            )
        )

    return mcp
