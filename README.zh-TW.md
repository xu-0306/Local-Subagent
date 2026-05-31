# Local Subagent MCP

語言：[English](README.md)

Local Subagent MCP 是一個本地優先的橋接層，用來把 coding agent 和本地語言模型接起來。

它讓 Codex、Claude Code 這類主 agent 可以把任務交給本地模型當 subagent 處理，但在任何有風險的動作發生前，仍由主 agent 先審核。換句話說，本地模型可以提出答案、推理和工具請求；主 agent 則負責工具執行、審核、除錯和資料標註。

簡單說：讓本地模型成為有用的助手，但讓主 agent 保持最後把關。

## 為什麼需要這個專案

本地模型已經越來越能參與真實 coding workflow，但直接把 shell、檔案修改、patch、測試或瀏覽器操作權限交給它，通常還不是最穩的做法。

這個專案把邊界切清楚：

- 主 agent 透過 MCP 呼叫本地 subagent。
- 本地 subagent 可以要求使用工具，但不直接執行工具。
- 主 agent 負責批准、拒絕或改寫工具請求。
- 每次回答、工具請求、審核、修正和偏好標籤都可以被保存。
- 這些 trace 之後可以轉成改進本地模型的資料。

這樣一來，它既能拿來做日常 agent 實驗，也能慢慢累積高價值的本地模型優化資料。

## 可以拿來做什麼

- 在 Codex、Claude Code 或其他支援 MCP 的 agent 裡測試本地模型
- 讓本地模型作為可審核的 coding subagent
- 從真實任務中收集錯誤、修正和改進建議
- 從已審核的 run 產生 SFT、preference、reward 或 raw trace 資料集
- 讓工具使用維持由主 agent 代審代執行，而不是直接把控制權交給本地模型

訓練、微調和模型服務部署會和 MCP 層分開處理。這個專案專注在 agent 介面和資料收集迴圈。

## 架構

![Local Subagent MCP 架構](local-subagent-architecture.png)

可編輯的圖檔來源：[local-subagent-architecture.drawio](local-subagent-architecture.drawio)

本地模型服務可以是 Ollama、vLLM、llama.cpp、LM Studio，或任何 OpenAI-compatible chat completion endpoint。

## 核心 MCP Tools

- `subagent_start_task`：開始一個本地 subagent run
- `subagent_step`：用新的 context 或 observation 延續 run
- `subagent_submit_tool_result`：把主 agent 的工具決策和觀察結果回傳給 subagent
- `subagent_record_review`：保存分數、錯誤、改進點、修正答案和偏好標籤
- `subagent_export_dataset`：將已審核的 trace 匯出成 JSONL
- `subagent_get_run` 與 `subagent_list_runs`：查看歷史 run

## 資料集輸出

收集到的 run 可以匯出成：

- Raw trace JSONL：用於除錯與審計
- SFT JSONL：使用修正後或審核後的答案
- Preference JSONL：使用 `chosen` 和 `rejected` 回覆
- Reward JSONL：使用分數和審核意見

更完整的實作計畫請看 [LOCAL_SUBAGENT_MCP_PLAN.md](LOCAL_SUBAGENT_MCP_PLAN.md)。
