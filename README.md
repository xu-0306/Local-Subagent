# Local Subagent MCP

Language: [繁體中文](README.zh-TW.md)

Local Subagent MCP is a local-first bridge between coding agents and local language models.

It lets a main agent, such as Codex or Claude Code, ask a local model to work as a subagent, then review what that subagent produced before anything risky happens. The local model can propose answers, reasoning, and tool requests. The main agent stays in charge of tool execution, review, debugging, and dataset labeling.

## What v1 Includes

- MCP tools for starting and continuing a subagent run
- Main-agent-mediated tool review loop
- SQLite persistence for runs, messages, tool requests, tool results, reviews, and exports
- JSONL export formats for raw trace, SFT, preference, and reward datasets
- A local FastMCP server entrypoint using stdio-friendly defaults

## Architecture

![Local Subagent MCP architecture](local-subagent-architecture.png)

Editable diagram source: [local-subagent-architecture.drawio](local-subagent-architecture.drawio)

The local model service can be Ollama, vLLM, llama.cpp, LM Studio, or any OpenAI-compatible chat completion endpoint.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Configuration

The server reads these environment variables:

- `LOCAL_SUBAGENT_APP_NAME`
- `LOCAL_SUBAGENT_DATABASE_PATH`
- `LOCAL_SUBAGENT_EXPORT_DIR`
- `LOCAL_SUBAGENT_MODEL_BASE_URL`
- `LOCAL_SUBAGENT_MODEL_API_KEY`
- `LOCAL_SUBAGENT_MODEL_NAME`
- `LOCAL_SUBAGENT_TEMPERATURE`
- `LOCAL_SUBAGENT_MAX_TOKENS`

Default values:

```text
LOCAL_SUBAGENT_APP_NAME=local-subagent
LOCAL_SUBAGENT_DATABASE_PATH=local_subagent.db
LOCAL_SUBAGENT_EXPORT_DIR=exports
LOCAL_SUBAGENT_MODEL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_SUBAGENT_MODEL_API_KEY=ollama
LOCAL_SUBAGENT_MODEL_NAME=qwen3
LOCAL_SUBAGENT_TEMPERATURE=0.2
LOCAL_SUBAGENT_MAX_TOKENS=2000
```

Example for Ollama-compatible `/v1` usage:

```powershell
$env:LOCAL_SUBAGENT_MODEL_BASE_URL = "http://127.0.0.1:11434/v1"
$env:LOCAL_SUBAGENT_MODEL_API_KEY = "ollama"
$env:LOCAL_SUBAGENT_MODEL_NAME = "qwen3"
```

## Running The MCP Server

```bash
python -m local_subagent
```

Or, after editable install:

```bash
local-subagent
```

The server uses FastMCP and is intended for stdio-based local MCP clients.

## Core MCP Tools

- `subagent_start_task`
- `subagent_step`
- `subagent_submit_tool_result`
- `subagent_record_review`
- `subagent_export_dataset`
- `subagent_get_run`
- `subagent_list_runs`

## Example Workflow

1. Call `subagent_start_task` with the task and optional context.
2. If the subagent returns `tool_requests`, the main agent reviews them.
3. Send the decision and observation back with `subagent_submit_tool_result`.
4. Once the run is complete, store review labels with `subagent_record_review`.
5. Export reviewed traces with `subagent_export_dataset`.

## Dataset Outputs

- `raw_trace_jsonl`: full audit trace with review payload
- `sft_jsonl`: corrected answer appended as assistant output
- `preference_jsonl`: chosen vs. rejected answer pairs
- `reward_jsonl`: scored response plus review notes

## Running Tests

```bash
pytest -q
```

## Project Plan

For the implementation breakdown and checkpoints, see [docs/superpowers/plans/2026-06-01-local-subagent-mcp-v1.md](docs/superpowers/plans/2026-06-01-local-subagent-mcp-v1.md).

For the original product direction, see [LOCAL_SUBAGENT_MCP_PLAN.md](LOCAL_SUBAGENT_MCP_PLAN.md).
