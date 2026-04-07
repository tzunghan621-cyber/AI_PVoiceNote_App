---
title: 開發日誌 2026-04-06 — V Phase 驗證
date: 2026-04-06
type: devlog
phase: V (Verify)
agent: 實驗者（Verifier）
status: 進行中
tags: [v-phase, devlog, verification]
---

# V Phase 驗證日誌（2026-04-06）

> 對應報告：[[verification_report_20260405]]

## 時間軸

### 第一輪驗證（早上）

1. **環境驗證** — Python 3.11.9、ffmpeg、faster-whisper、flet、chromadb 全部 PASS；Ollama 初次未安裝
2. **自動化測試** — fast tests 106/106、Whisper 7/7、ChromaDB 14/14 全通過
3. **甲方安裝 Ollama** — 安裝 0.20.2，初次拉取 `gemma3:4b`（暫代）
4. **冒煙測試發現 Runtime Bug**
   - Bug #1：`DashboardView.page` setter 衝突 → 修復
   - Bug #2：`OutlinedButton(color=...)` 不相容 Flet 0.84.0 → 修復
5. **驗證 #1 PASS** — App idle 頁面正常顯示

### 模型選型卡關（中午）

- 發現 spec 寫的 `gemma4:4b` 在 Ollama 不存在 → 阻塞
- 大統領決策：改用 `gemma4:e4b`（spec 與 code 一併修正，碼農負責）
- 拉 `gemma4:e4b`（9.2GB）成功，但載入時 OOM：需 9.9GB RAM，可用僅 ~3GB
- 大統領決策：補拉 `gemma4:e2b`（7.2GB 模型）作為降級

### 第二輪驗證（下午）

1. 碼農修正完成（[[decision_20260406_model_selection]]）：
   - `config/default.yaml`: 預設 `gemma4:e4b` + `num_ctx: 8192` + `temperature: 0.3`
   - `summarizer.py`、`main_view.py`、`settings_view.py`、5 個測試檔同步更新
2. 拉 `gemma4:e2b` 成功，推理測試 PASS（"Hello" 回應正常）
3. 自動化測試 106/106 重跑 PASS
4. **權宜措施**：將 `config/default.yaml` 的 `model` 暫改為 `gemma4:e2b`，以便在開發環境下完成 Pipeline 端到端驗證
5. App 啟動成功，狀態列正確顯示 `gemma4:e2b`
6. 驗證 #2~#10 暫停，等待甲方有空繼續

## 關鍵發現

### 1. Flet 0.84.0 API 變動

兩個 Bug 都源自 Flet 升級：
- 繼承 `ft.Container` 的子類別不能再用 `self.page` 屬性（與內建唯讀 property 衝突）
- `OutlinedButton` 不接受裸 `color=` 參數，需用 `ButtonStyle`

### 2. 16GB 機器跑 E4B 的現實限制

| 用途 | RAM 需求 |
|---|---|
| Windows + 系統服務 | ~4-5 GB |
| VS Code + Claude Code + 瀏覽器 | ~4-6 GB |
| Ollama + Whisper + Flet App | ~2 GB |
| **gemma4:e4b 模型載入** | **9.9 GB** |
| **總和** | **~20-23 GB**（超過 16 GB 上限） |

開發模式下要跑 E4B 幾乎不可能。E2B（~6 GB 推理）較務實。

### 3. 驗證流程經驗

- Flet App 在背景模式啟動會立刻退出（視窗生命週期問題），改由甲方手動啟動效果較好
- App 啟動 logs 中的 ERROR 是早期 bug 線索；exit code 0 不代表沒問題

## 權宜變更紀錄

| 檔案 | 變更 | 原因 | 何時還原 |
|---|---|---|---|
| `config/default.yaml` | `ollama.model: gemma4:e4b` → `gemma4:e2b` | 開發環境 RAM 不足以載入 E4B | V Phase 驗證完成後 |

## 下一步

- 等待甲方繼續執行驗證 #2~#10（響應式佈局、錄音、匯入、Pipeline、編輯、匯出、詞條 CRUD、設定）
- 完成所有手動驗證後，將 `config/default.yaml` 改回 `gemma4:e4b`
- 產出 V Phase 結案報告

## 相關文件

- [[verification_report_20260405]] — V Phase 驗證報告
- [[decision_20260406_model_selection]] — 模型選型決策
- [[devlog_20260406_model_fix]] — 碼農修改紀錄
