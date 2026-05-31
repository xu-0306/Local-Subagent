# Local Subagent MCP

語言：[English](README.md)

Local Subagent MCP 是一個本地優先的橋接層，讓 coding agent 可以把本地語言模型當成可審查的 subagent 來使用。

它的核心邊界很明確：本地模型可以提出答案、推理與 tool request，但真正的工具執行、審核、除錯與資料標註仍由主代理負責。

## v1 目前包含

- 用來啟動與延續 subagent run 的 MCP tools
- 由主代理審核的 tool review 流程
- 以 SQLite 儲存 runs、messages、tool requests、tool results、reviews 與 exports
- 匯出 `raw trace / SFT / preference / reward` 的 JSONL 格式
- 以 FastMCP 實作、適合本地 stdio client 的 server 入口

## 架構

![Local Subagent MCP 架構圖](local-subagent-architecture.png)

可編輯圖檔：[local-subagent-architecture.drawio](local-subagent-architecture.drawio)

本地模型服務可以是 Ollama、vLLM、llama.cpp、LM Studio，或任何 OpenAI-compatible chat completion endpoint。

## 安裝

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## 設定

Server 會讀取以下環境變數：

- `LOCAL_SUBAGENT_APP_NAME`
- `LOCAL_SUBAGENT_DATABASE_PATH`
- `LOCAL_SUBAGENT_EXPORT_DIR`
- `LOCAL_SUBAGENT_MODEL_BASE_URL`
- `LOCAL_SUBAGENT_MODEL_API_KEY`
- `LOCAL_SUBAGENT_MODEL_NAME`
- `LOCAL_SUBAGENT_TEMPERATURE`
- `LOCAL_SUBAGENT_MAX_TOKENS`

預設值：

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

以 Ollama `/v1` 介面為例：

```powershell
$env:LOCAL_SUBAGENT_MODEL_BASE_URL = "http://127.0.0.1:11434/v1"
$env:LOCAL_SUBAGENT_MODEL_API_KEY = "ollama"
$env:LOCAL_SUBAGENT_MODEL_NAME = "qwen3"
```

## 啟動 MCP Server

```bash
python -m local_subagent
```

若已用 editable install 安裝，也可以直接執行：

```bash
local-subagent
```

目前以 FastMCP 為基礎，預設走本地 stdio 型態的 MCP 使用情境。

## 主要 MCP Tools

- `subagent_start_task`
- `subagent_step`
- `subagent_submit_tool_result`
- `subagent_record_review`
- `subagent_export_dataset`
- `subagent_get_run`
- `subagent_list_runs`

## 一次完整流程

1. 用 `subagent_start_task` 傳入任務與可選 context。
2. 如果 subagent 回傳 `tool_requests`，由主代理先審核。
3. 透過 `subagent_submit_tool_result` 把決策與 observation 回送給 subagent。
4. 任務完成後，用 `subagent_record_review` 存下 review 與標註。
5. 最後用 `subagent_export_dataset` 匯出資料集。

## 資料集輸出

- `raw_trace_jsonl`：完整 audit trace 與 review payload
- `sft_jsonl`：把 corrected answer 當成 assistant 輸出
- `preference_jsonl`：`chosen` 與 `rejected` 配對
- `reward_jsonl`：帶分數與 review note 的 response

## 執行測試

```bash
pytest -q
```

## 計畫文件

實作拆分與 checkpoint 請看 [docs/superpowers/plans/2026-06-01-local-subagent-mcp-v1.md](docs/superpowers/plans/2026-06-01-local-subagent-mcp-v1.md)。

原始產品方向請看 [LOCAL_SUBAGENT_MCP_PLAN.md](LOCAL_SUBAGENT_MCP_PLAN.md)。
