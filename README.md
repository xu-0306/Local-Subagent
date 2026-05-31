# Local Subagent MCP

Language: [繁體中文](README.zh-TW.md)

Local Subagent MCP is a local-first bridge between coding agents and local language models.

It lets a main agent, such as Codex or Claude Code, ask a local model to work as a subagent, then review what that subagent produced before anything risky happens. The local model can propose answers, reasoning, and tool requests. The main agent stays in charge of tool execution, review, debugging, and dataset labeling.

The short version: use your local model as a useful assistant, while keeping the main agent as the responsible reviewer.

## Why This Exists

Local models are getting good enough to help with real coding workflows, but giving them direct access to shell commands, file edits, patches, tests, or browser automation is not always a good idea.

This project keeps the boundary clear:

- The main agent calls the local subagent through MCP.
- The local subagent can ask for tools, but does not run them directly.
- The main agent approves, rejects, or rewrites those tool requests.
- Every answer, tool request, review, correction, and preference label can be saved.
- The saved traces can become data for future model improvement.

This makes the workflow useful both for day-to-day agent experiments and for building better local models over time.

## What It Is For

- Trying local models inside Codex, Claude Code, or another MCP-capable agent
- Letting a local model act as a reviewable coding subagent
- Capturing mistakes, fixes, and improvement notes from real tasks
- Building SFT, preference, reward, or raw trace datasets from reviewed runs
- Keeping tool use mediated by the main agent instead of handing full control to the local model

Training, fine-tuning, and model serving are intentionally separate from this MCP layer. This project focuses on the agent interface and the data capture loop.

## Architecture

![Local Subagent MCP architecture](local-subagent-architecture.png)

Editable diagram source: [local-subagent-architecture.drawio](local-subagent-architecture.drawio)

The local model service can be Ollama, vLLM, llama.cpp, LM Studio, or any OpenAI-compatible chat completion endpoint.

## Core MCP Tools

- `subagent_start_task`: start a local subagent run
- `subagent_step`: continue the run with new context or observations
- `subagent_submit_tool_result`: send the main agent's tool decision and observation back to the subagent
- `subagent_record_review`: save scores, errors, improvements, corrected answers, and preference labels
- `subagent_export_dataset`: export reviewed traces as JSONL
- `subagent_get_run` and `subagent_list_runs`: inspect previous runs

## Dataset Outputs

The captured runs can be exported as:

- Raw trace JSONL for debugging and audit
- SFT JSONL using corrected or reviewed answers
- Preference JSONL using `chosen` and `rejected` responses
- Reward JSONL using scores and review notes

For the fuller implementation plan, see [LOCAL_SUBAGENT_MCP_PLAN.md](LOCAL_SUBAGENT_MCP_PLAN.md).
