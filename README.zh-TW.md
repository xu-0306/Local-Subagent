# Local Subagent MCP

語言：[English](README.md)

Local Subagent MCP 是一個讓 coding agent 與本地語言模型協作的本機優先橋接層。

它讓主代理（例如 Codex 或 Claude Code）可以把任務交給本地模型當 subagent 執行，但任何有風險的工具操作仍然由主代理審查與決定。本地模型可以提出答案、推理與 tool request；主代理則保留工具執行、除錯、review 與資料標註的控制權。

## v1 內容

- 用於啟動與續跑 subagent run 的 MCP tools
- 主代理介入的 tool review 流程
- 使用 SQLite 持久化 runs、messages、tool requests、tool results、reviews 與 exports
- 支援 `raw trace / SFT / preference / reward` 四種 JSONL 匯出格式
- 以 FastMCP 提供本機 `stdio` 型 MCP server

## 架構

![Local Subagent MCP architecture](local-subagent-architecture.png)

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
- `LOCAL_SUBAGENT_CONFIG_PATH`
- `LOCAL_SUBAGENT_RUNTIME_PROVIDER`
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
LOCAL_SUBAGENT_RUNTIME_PROVIDER=ollama
LOCAL_SUBAGENT_MODEL_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_SUBAGENT_MODEL_API_KEY=ollama
LOCAL_SUBAGENT_MODEL_NAME=qwen3
LOCAL_SUBAGENT_TEMPERATURE=0.2
LOCAL_SUBAGENT_MAX_TOKENS=2000
```

如果有設定 `LOCAL_SUBAGENT_CONFIG_PATH` 指向 JSON 檔，server 會先讀取該檔案中的 runtime 設定，再讓環境變數覆蓋它。這讓 `npx` 啟動時也能保留持久化設定，而不需要使用者手動管理 virtualenv。

如果沒有設定 `LOCAL_SUBAGENT_CONFIG_PATH`，server 會依宿主 agent 環境選擇預設設定檔路徑：

- Codex 且有 `CODEX_HOME`：`$CODEX_HOME/local-subagent-runtime.json`
- Codex 但沒有 `CODEX_HOME`、只有 Codex marker env：`~/.codex/local-subagent-runtime.json`
- Claude Code：`~/.claude/local-subagent-runtime.json`
- 通用 fallback：`~/.local-subagent/runtime.json`

Ollama `/v1` 設定範例：

```powershell
$env:LOCAL_SUBAGENT_MODEL_BASE_URL = "http://127.0.0.1:11434/v1"
$env:LOCAL_SUBAGENT_MODEL_API_KEY = "ollama"
$env:LOCAL_SUBAGENT_MODEL_NAME = "qwen3"
```

## 啟動 MCP Server

```bash
python -m local_subagent
```

如果已經做 editable install，也可以直接執行：

```bash
local-subagent
```

這個 server 使用 FastMCP，主要提供給本機 `stdio` 型 MCP client。

## Runtime Onboarding

MCP 目前提供 runtime onboarding tools，讓 agent 可以在首次使用時引導設定：

- `subagent_get_runtime_status`
- `subagent_list_runtime_presets`
- `subagent_configure_runtime`
- `subagent_validate_runtime`

建議的首次設定流程：

1. 呼叫 `subagent_get_runtime_status`
2. 如果還在使用 defaults，先詢問使用者目前使用哪種 runtime
3. 呼叫 `subagent_list_runtime_presets` 查看支援的 preset
4. 用 `subagent_configure_runtime` 寫入對應 preset，以及必要時的自訂 URL 或 model name
5. 用 `subagent_validate_runtime` 驗證連線後，再開始 subagent task

目前支援的 preset：

- `ollama`
- `vllm`
- `lmstudio`
- `llamacpp`
- `openai_compatible`

如果工具無法自動完成設定，回傳結果中會包含本機設定檔路徑，讓 agent 可以提示使用者去該路徑手動修改。

## 透過 `npx` 啟動

將 npm wrapper package 發佈後，MCP client 可以直接這樣設定：

```json
{
  "mcpServers": {
    "local-subagent": {
      "command": "npx",
      "args": ["-y", "@xu-0306/local-subagent-mcp@latest"]
    }
  }
}
```

第一次啟動時，npm launcher 會：

1. 偵測本機 Python
2. 建立快取 virtualenv
3. 安裝隨 npm package 一起發佈的 Python 專案
4. 啟動 `python -m local_subagent`

因此使用者通常不需要自己手動建立 virtualenv，但主機上仍需要 Python 3.12+ 與 Node.js。

## 發佈說明

目前這個專案同時有兩個發佈面：

- Python package：由 `pyproject.toml` 定義，供 launcher 安裝 `local_subagent`
- npm package：由 `package.json` 定義，提供 `npx` 啟動入口

建議的發佈流程如下：

1. 先同步版本號
   - 更新 `package.json` 的 `version`
   - 更新 `pyproject.toml` 的 `project.version`
2. 執行本地驗證
   - `pytest -q`
   - `node --check bin/local-subagent-mcp.js`
   - `python -m py_compile src/local_subagent/config.py src/local_subagent/service.py src/local_subagent/server.py src/local_subagent/runtime/adapter.py src/local_subagent/runtime/onboarding.py src/local_subagent/runtime/presets.py`
3. 登入 npm
   - `npm login`
4. 發佈 npm package
   - `npm publish --access public`
5. 驗證 `npx` 啟動
   - 在 MCP client 設定中使用 `@xu-0306/local-subagent-mcp@latest`
   - 呼叫 `subagent_get_runtime_status` 與 `subagent_validate_runtime`

注意事項：

- npm package 目前是 wrapper，不是獨立 binary
- `npx` 啟動仍依賴本機 Python 3.12+
- 若未來要做到完全免 Python 安裝，必須改成 Node/TypeScript 版本，或另外打包 standalone binary

## 核心 MCP Tools

- `subagent_get_runtime_status`
- `subagent_list_runtime_presets`
- `subagent_configure_runtime`
- `subagent_validate_runtime`
- `subagent_start_task`
- `subagent_step`
- `subagent_submit_tool_result`
- `subagent_record_review`
- `subagent_export_dataset`
- `subagent_get_run`
- `subagent_list_runs`

## 範例流程

1. 呼叫 `subagent_start_task`，提供 task 與必要 context
2. 如果 subagent 回傳 `tool_requests`，由主代理進行審查
3. 用 `subagent_submit_tool_result` 把決策與 observation 傳回 subagent
4. 當 run 完成後，使用 `subagent_record_review` 記錄 review 標註
5. 用 `subagent_export_dataset` 匯出資料集

## 匯出格式

- `raw_trace_jsonl`：完整 audit trace 與 review payload
- `sft_jsonl`：將 corrected answer 作為 assistant 輸出
- `preference_jsonl`：`chosen` 與 `rejected` 的偏好配對
- `reward_jsonl`：帶分數與 review note 的 response

## 執行測試

```bash
pytest -q
```

## 專案計畫

實作拆解與 checkpoint 可參考 [docs/superpowers/plans/2026-06-01-local-subagent-mcp-v1.md](docs/superpowers/plans/2026-06-01-local-subagent-mcp-v1.md)。

原始產品方向可參考 [LOCAL_SUBAGENT_MCP_PLAN.md](LOCAL_SUBAGENT_MCP_PLAN.md)。
