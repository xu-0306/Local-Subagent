import os
from typing import Any, Literal

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from local_subagent.config import AppConfig
from local_subagent.service import SubagentService


class _BaseInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class StartTaskInput(_BaseInput):
    task: str = Field(..., min_length=1, description="User or main-agent task instruction.")
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional context, file hints, constraints, or prior findings.",
    )
    model_profile: dict[str, Any] | None = Field(
        default=None,
        description="Optional model selection or runtime parameter overrides.",
    )


class StepInput(_BaseInput):
    run_id: str = Field(..., min_length=1, description="Existing run identifier.")
    message: str = Field(..., min_length=1, description="Main-agent follow-up message or observation.")
    context_delta: dict[str, Any] | None = Field(
        default=None,
        description="Optional incremental context for the next subagent step.",
    )


class ToolResultInput(_BaseInput):
    run_id: str = Field(..., min_length=1, description="Existing run identifier.")
    tool_request_id: str = Field(..., min_length=1, description="Tool request identifier to resolve.")
    decision: Literal["approved", "rejected", "modified"] = Field(
        ...,
        description="Main-agent decision for the requested tool call.",
    )
    observation: str = Field(
        ...,
        min_length=1,
        description="Observed result or reason returned to the subagent.",
    )


class ReviewInput(_BaseInput):
    run_id: str = Field(..., min_length=1, description="Run identifier to review.")
    score: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Optional scalar score for reward-style labeling.",
    )
    errors: list[str] = Field(default_factory=list, description="Observed mistakes or failures.")
    improvements: list[str] = Field(
        default_factory=list,
        description="Concrete improvements that would make the response better.",
    )
    missing_parts: list[str] = Field(
        default_factory=list,
        description="Important missing pieces or omitted requirements.",
    )
    corrected_response: str | None = Field(
        default=None,
        description="Optional corrected answer for SFT export.",
    )
    chosen: str | None = Field(
        default=None,
        description="Preferred answer text for preference export.",
    )
    rejected: str | None = Field(
        default=None,
        description="Rejected answer text for preference export.",
    )


class ExportInput(_BaseInput):
    format: Literal[
        "raw_trace_jsonl",
        "sft_jsonl",
        "preference_jsonl",
        "reward_jsonl",
    ] = Field(..., description="Dataset export format.")
    run_id: str | None = Field(
        default=None,
        description="Optional run identifier to export a single run.",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Optional export filters stored with export metadata.",
    )


class GetRunInput(_BaseInput):
    run_id: str = Field(..., min_length=1, description="Run identifier to inspect.")


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
    def subagent_start_task(params: StartTaskInput) -> dict[str, Any]:
        """Start a new subagent run and return its first response."""

        return resolved_service.start_task(
            task=params.task,
            context=params.context,
            model_profile=params.model_profile,
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
    def subagent_step(params: StepInput) -> dict[str, Any]:
        """Continue an existing run with a main-agent message or observation."""

        return resolved_service.step(
            run_id=params.run_id,
            message=params.message,
            context_delta=params.context_delta,
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
    def subagent_submit_tool_result(params: ToolResultInput) -> dict[str, Any]:
        """Record a tool review decision and continue the subagent run."""

        return resolved_service.submit_tool_result(
            run_id=params.run_id,
            tool_request_id=params.tool_request_id,
            decision=params.decision,
            observation=params.observation,
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
    def subagent_record_review(params: ReviewInput) -> dict[str, Any]:
        """Store review feedback and report which dataset exports are now ready."""

        return resolved_service.record_review(
            run_id=params.run_id,
            score=params.score,
            errors=params.errors,
            improvements=params.improvements,
            missing_parts=params.missing_parts,
            corrected_response=params.corrected_response,
            chosen=params.chosen,
            rejected=params.rejected,
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
    def subagent_export_dataset(params: ExportInput) -> dict[str, Any]:
        """Export stored traces into JSONL dataset formats."""

        return resolved_service.export_dataset(
            format=params.format,
            run_id=params.run_id,
            filters=params.filters,
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
    def subagent_get_run(params: GetRunInput) -> dict[str, Any]:
        """Fetch one persisted run with its messages, tool reviews, and review data."""

        return resolved_service.get_run(run_id=params.run_id)

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
