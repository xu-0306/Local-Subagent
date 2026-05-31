# Local Subagent MCP v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local MCP server that exposes a local model as a mediated subagent, persists auditable traces in SQLite, and exports reviewed runs as JSONL datasets.

**Architecture:** The server is a Python package centered on a thin FastMCP entrypoint. Runtime, persistence, review, and export concerns are isolated into focused modules so MCP tool handlers orchestrate instead of owning business logic. v1 uses main-agent-mediated tool execution only: the local model can request tools, but the MCP server never executes shell, patch, browser, or file-mutation tools itself.

**Tech Stack:** Python 3.12, FastMCP, SQLite, httpx, pytest

---

## File Structure

- `pyproject.toml`: package metadata, dependencies, pytest configuration
- `.gitignore`: ignore Python caches, local databases, exports, virtualenvs, env files
- `src/local_subagent/config.py`: app configuration defaults and environment loading
- `src/local_subagent/server.py`: FastMCP server factory and MCP tool registration
- `src/local_subagent/service.py`: orchestration layer for run lifecycle and tool-review flow
- `src/local_subagent/domain/models.py`: structured dataclasses for runs, messages, tool requests, tool results, reviews, and exports
- `src/local_subagent/runtime/protocol.py`: structured local-model response schema and parsing helpers
- `src/local_subagent/runtime/prompts.py`: system prompts for mediated subagent behavior
- `src/local_subagent/runtime/adapter.py`: OpenAI-compatible local model client
- `src/local_subagent/storage/schema.py`: SQLite schema creation and migrations for v1
- `src/local_subagent/storage/repository.py`: persistence reads and writes for run data
- `src/local_subagent/review/service.py`: review capture and dataset-readiness logic
- `src/local_subagent/exporters/jsonl.py`: raw trace, SFT, preference, and reward JSONL exporters
- `tests/unit/test_config.py`: configuration tests
- `tests/unit/test_server.py`: FastMCP server factory tests
- `tests/unit/test_repository.py`: SQLite repository tests
- `tests/unit/test_protocol.py`: structured response parsing tests
- `tests/unit/test_adapter.py`: local model adapter tests with mocked HTTP
- `tests/unit/test_review_service.py`: review logic tests
- `tests/unit/test_exporters.py`: JSONL export tests
- `tests/unit/test_mcp_tools.py`: MCP tool validation and orchestration tests
- `tests/integration/test_end_to_end.py`: fake local model end-to-end workflow test
- `README.md`: setup and usage
- `README.zh-TW.md`: localized setup and usage

## Workstreams

- **Workstream A:** repo bootstrap and guardrails
- **Workstream B:** domain models and SQLite repository
- **Workstream C:** runtime protocol and local model adapter
- **Workstream D:** review capture and JSONL exporters
- **Workstream E:** MCP orchestration and tool wiring
- **Workstream F:** integration coverage and documentation

Dependencies:

- Workstream A must land first.
- Workstreams B, C, and D can run in parallel after A.
- Workstream E depends on B, C, and D.
- Workstream F depends on E.

## Checkpoints

- **Checkpoint 1:** bootstrap complete, tests for config/server pass, `.gitignore` present
- **Checkpoint 2:** repository, runtime, and exporter unit tests pass together
- **Checkpoint 3:** MCP tools wired and tool-level tests pass
- **Checkpoint 4:** integration flow and docs complete

### Task 0: Bootstrap The Package And Guardrails

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/local_subagent/__init__.py`
- Create: `src/local_subagent/config.py`
- Create: `src/local_subagent/server.py`
- Test: `tests/unit/test_config.py`
- Test: `tests/unit/test_server.py`

- [ ] **Step 1: Write failing config and server tests**

```python
from local_subagent.config import AppConfig
from local_subagent.server import create_server


def test_app_config_defaults():
    config = AppConfig.from_env({})
    assert str(config.database_path) == "local_subagent.db"
    assert str(config.export_dir) == "exports"
    assert config.model_base_url == "http://127.0.0.1:11434/v1"


def test_create_server_returns_fastmcp_instance():
    server = create_server()
    assert server.name == "local-subagent"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_config.py tests/unit/test_server.py -q`
Expected: FAIL because package modules do not exist yet.

- [ ] **Step 3: Write minimal package skeleton**

```python
@dataclass(slots=True)
class AppConfig:
    ...

def create_server(config: AppConfig | None = None) -> FastMCP:
    return FastMCP(name="local-subagent")
```

- [ ] **Step 4: Add package metadata and ignore rules**

```toml
[project]
name = "local-subagent"
dependencies = ["fastmcp", "httpx"]
```

- [ ] **Step 5: Run targeted tests to verify they pass**

Run: `pytest tests/unit/test_config.py tests/unit/test_server.py -q`
Expected: PASS

- [ ] **Step 6: Commit checkpoint**

```bash
git add .gitignore pyproject.toml src/local_subagent tests/unit docs/superpowers/plans/2026-06-01-local-subagent-mcp-v1.md
git commit -m "feat: bootstrap local subagent package"
```

### Task 1: Implement Domain Models And SQLite Repository

**Files:**
- Create: `src/local_subagent/domain/models.py`
- Create: `src/local_subagent/storage/schema.py`
- Create: `src/local_subagent/storage/repository.py`
- Test: `tests/unit/test_repository.py`

- [ ] **Step 1: Write failing repository tests**

```python
def test_repository_creates_and_reads_run(tmp_path):
    repo = SQLiteRunRepository(tmp_path / "runs.db")
    run = repo.create_run(task="inspect repo", model_name="qwen")
    loaded = repo.get_run(run.run_id)
    assert loaded.task == "inspect repo"
    assert loaded.model_name == "qwen"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_repository.py -q`
Expected: FAIL because repository types do not exist yet.

- [ ] **Step 3: Implement minimal domain model and schema**

```python
@dataclass(slots=True)
class RunRecord:
    run_id: str
    task: str
    model_name: str
```

- [ ] **Step 4: Implement repository CRUD used by v1 flows**

```python
repo.create_run(...)
repo.add_message(...)
repo.add_tool_request(...)
repo.add_tool_result(...)
repo.save_review(...)
repo.list_runs(...)
```

- [ ] **Step 5: Run repository tests**

Run: `pytest tests/unit/test_repository.py -q`
Expected: PASS

- [ ] **Step 6: Commit checkpoint**

```bash
git add src/local_subagent/domain src/local_subagent/storage tests/unit/test_repository.py
git commit -m "feat: add sqlite run repository"
```

### Task 2: Implement Runtime Protocol And Local Model Adapter

**Files:**
- Create: `src/local_subagent/runtime/protocol.py`
- Create: `src/local_subagent/runtime/prompts.py`
- Create: `src/local_subagent/runtime/adapter.py`
- Test: `tests/unit/test_protocol.py`
- Test: `tests/unit/test_adapter.py`

- [ ] **Step 1: Write failing protocol and adapter tests**

```python
def test_parse_subagent_response_with_tool_requests():
    payload = {"message": "Need ls", "tool_requests": [{"name": "shell", "arguments": {"cmd": "ls"}}], "done": False}
    response = parse_subagent_response(payload)
    assert response.tool_requests[0].name == "shell"


def test_adapter_posts_openai_compatible_request(httpx_mock):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_protocol.py tests/unit/test_adapter.py -q`
Expected: FAIL because protocol and adapter modules do not exist yet.

- [ ] **Step 3: Implement structured response schema and parser**

```python
@dataclass(slots=True)
class SubagentResponse:
    message: str
    tool_requests: list[ToolRequest]
    done: bool
```

- [ ] **Step 4: Implement OpenAI-compatible adapter**

```python
class LocalModelAdapter:
    def complete(self, messages: list[dict[str, str]]) -> SubagentResponse:
        ...
```

- [ ] **Step 5: Run protocol and adapter tests**

Run: `pytest tests/unit/test_protocol.py tests/unit/test_adapter.py -q`
Expected: PASS

- [ ] **Step 6: Commit checkpoint**

```bash
git add src/local_subagent/runtime tests/unit/test_protocol.py tests/unit/test_adapter.py
git commit -m "feat: add local model adapter"
```

### Task 3: Implement Review Capture And JSONL Exporters

**Files:**
- Create: `src/local_subagent/review/service.py`
- Create: `src/local_subagent/exporters/jsonl.py`
- Test: `tests/unit/test_review_service.py`
- Test: `tests/unit/test_exporters.py`

- [ ] **Step 1: Write failing review and exporter tests**

```python
def test_review_marks_dataset_ready_when_corrected_response_present():
    result = review_service.record_review(...)
    assert result.ready_formats == {"raw_trace_jsonl", "sft_jsonl"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_review_service.py tests/unit/test_exporters.py -q`
Expected: FAIL because review and exporter modules do not exist yet.

- [ ] **Step 3: Implement review readiness rules**

```python
def record_review(...):
    ...
```

- [ ] **Step 4: Implement JSONL exporters**

```python
def export_raw_trace(...)
def export_sft(...)
def export_preference(...)
def export_reward(...)
```

- [ ] **Step 5: Run review and exporter tests**

Run: `pytest tests/unit/test_review_service.py tests/unit/test_exporters.py -q`
Expected: PASS

- [ ] **Step 6: Commit checkpoint**

```bash
git add src/local_subagent/review src/local_subagent/exporters tests/unit/test_review_service.py tests/unit/test_exporters.py
git commit -m "feat: add review and dataset export services"
```

### Task 4: Implement MCP Tool Orchestration

**Files:**
- Modify: `src/local_subagent/server.py`
- Create: `src/local_subagent/service.py`
- Test: `tests/unit/test_mcp_tools.py`

- [ ] **Step 1: Write failing MCP tool tests**

```python
def test_start_task_persists_run_and_returns_initial_response():
    result = subagent_start_task(...)
    assert result["run_id"]
    assert result["done"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_tools.py -q`
Expected: FAIL because MCP tools are not registered yet.

- [ ] **Step 3: Implement orchestration service**

```python
class SubagentService:
    def start_task(...)
    def step(...)
    def submit_tool_result(...)
    def record_review(...)
    def export_dataset(...)
```

- [ ] **Step 4: Register MCP tools through FastMCP**

```python
@mcp.tool
def subagent_start_task(...):
    ...
```

- [ ] **Step 5: Run MCP tool tests**

Run: `pytest tests/unit/test_mcp_tools.py -q`
Expected: PASS

- [ ] **Step 6: Run focused regression suite**

Run: `pytest tests/unit/test_config.py tests/unit/test_server.py tests/unit/test_repository.py tests/unit/test_protocol.py tests/unit/test_adapter.py tests/unit/test_review_service.py tests/unit/test_exporters.py tests/unit/test_mcp_tools.py -q`
Expected: PASS

- [ ] **Step 7: Commit checkpoint**

```bash
git add src/local_subagent/server.py src/local_subagent/service.py tests/unit/test_mcp_tools.py
git commit -m "feat: wire mcp subagent tools"
```

### Task 5: Add End-To-End Coverage And Documentation

**Files:**
- Create: `tests/integration/test_end_to_end.py`
- Modify: `README.md`
- Modify: `README.zh-TW.md`

- [ ] **Step 1: Write failing end-to-end test**

```python
def test_fake_local_model_round_trip(tmp_path):
    run_id = ...
    assert exported_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_end_to_end.py -q`
Expected: FAIL because full orchestration is not complete yet.

- [ ] **Step 3: Implement any missing integration glue**

```python
fake_model = FakeLocalModel([...])
```

- [ ] **Step 4: Update docs**

Document:
- local model service assumptions
- configuration variables
- one complete MCP interaction
- review capture
- dataset export

- [ ] **Step 5: Run full test suite**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 6: Commit checkpoint**

```bash
git add tests/integration/test_end_to_end.py README.md README.zh-TW.md
git commit -m "feat: add end-to-end coverage and docs"
```

## Subagent Assignment Plan

- **Worker A:** Task 1 ownership over `src/local_subagent/domain/*`, `src/local_subagent/storage/*`, `tests/unit/test_repository.py`
- **Worker B:** Task 2 ownership over `src/local_subagent/runtime/*`, `tests/unit/test_protocol.py`, `tests/unit/test_adapter.py`
- **Worker C:** Task 3 ownership over `src/local_subagent/review/*`, `src/local_subagent/exporters/*`, `tests/unit/test_review_service.py`, `tests/unit/test_exporters.py`
- **Controller session:** Task 0 locally first, then Task 4 integration, Task 5 verification/docs

## Push Strategy

- Push after Checkpoint 1
- Push after integrating Tasks 1, 2, and 3
- Push after Task 4
- Push after Task 5
