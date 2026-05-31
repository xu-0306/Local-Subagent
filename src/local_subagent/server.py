import os
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from local_subagent.config import AppConfig
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
        "and tool requests, but tool execution is always reviewed by the main agent."
    )
    mcp = FastMCP(name=resolved_config.app_name, instructions=instructions)

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

        return resolved_service.start_task(
            task=task,
            context=context,
            model_profile=model_profile,
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

        return resolved_service.step(
            run_id=run_id,
            message=message,
            context_delta=context_delta,
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

        return resolved_service.submit_tool_result(
            run_id=run_id,
            tool_request_id=tool_request_id,
            decision=decision,
            observation=observation,
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
    ) -> dict[str, Any]:
        """Store review feedback and report which dataset exports are now ready."""

        return resolved_service.record_review(
            run_id=run_id,
            score=score,
            errors=errors or [],
            improvements=improvements or [],
            missing_parts=missing_parts or [],
            corrected_response=corrected_response,
            chosen=chosen,
            rejected=rejected,
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

        return resolved_service.export_dataset(
            format=format,
            run_id=run_id,
            filters=filters,
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

        return resolved_service.get_run(run_id=run_id)

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
    def subagent_list_runs() -> list[dict[str, Any]]:
        """List stored runs for audit and debugging."""

        return resolved_service.list_runs()

    return mcp
