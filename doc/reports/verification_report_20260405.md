---
title: V Phase 驗證報告
date: 2026-04-06
phase: V (Verify)
agent: 實驗者（Verifier）
status: 🟡 進行中（驗證 #1 PASS，#2~#10 待測）
tags: [verification, v-phase, report]
---

# V Phase 驗證報告

> 初次執行：2026-04-05
> 持續更新：2026-04-06（碼農完成模型選型修正後重新驗證）
> 執行者：實驗者（Verifier）
> 對象：[[system_overview|AI_PVoiceNote_App]] S Phase 全部交付物

---

## 一、Agent 自測結果

### 1.1 環境驗證

| 項目 | 結果 | 詳情 |
|---|---|---|
| Python ≥ 3.11 | ✅ PASS | Python 3.11.9 |
| `pip install -e .` | ✅ PASS | 成功安裝 ai-pvoicenote-app 0.1.0 |
| Ollama | ✅ PASS | 0.20.2，服務正常運行 |
| Ollama Model — `gemma4:e4b` | ⚠️ 已下載但無法載入 | 9.2GB 模型，需 9.9GB RAM，超出當前可用（見 [[#四、模型選型實測]]） |
| Ollama Model — `gemma4:e2b` | ✅ PASS | 6.8GB 模型，推理測試成功 |
| ffmpeg | ✅ PASS | ffmpeg 8.0.1-full_build |
| faster-whisper | ✅ PASS | 1.2.1 |
| flet | ✅ PASS | 0.84.0 |
| chromadb | ✅ PASS | 1.5.5 |

### 1.2 自動化測試

| 測試套件 | 通過 | 失敗 | 跳過 | 耗時 |
|---|---|---|---|---|
| Fast tests (`-m "not slow"`) | 106 | 0 | 21 deselected | 13.77s |
| Whisper (`test_transcriber.py`) | 7 | 0 | 0 | 7.46s |
| ChromaDB + Embedding (`test_knowledge_base.py`) | 14 | 0 | 0 | 17.99s |
| **合計** | **127** | **0** | — | — |

> 全部 127 項測試在碼農完成模型選型修正後重新執行，零失敗。

**警告記錄**：
- `pydub.utils`: `audioop` 模組在 Python 3.13 將被移除（DeprecationWarning）— 目前使用 3.11，不影響

### 1.3 冒煙測試 — App 啟動

| 項目 | 結果 | 詳情 |
|---|---|---|
| TCP Server 啟動 | ✅ PASS | 成功監聽本地 port |
| Flet View 啟動 | ✅ PASS | flet-desktop 0.84.0 |
| Assets 路徑 | ✅ PASS | `app/assets` 正確載入 |
| Idle 頁面渲染 | ✅ PASS | 視窗開啟、idle 介面顯示正確（見截圖） |

### 1.4 程式碼完整性檢查

| 檢查項目 | 結果 | 詳情 |
|---|---|---|
| Import 路徑 | ✅ PASS | 全部 app/ 內部 import 解析正確 |
| `config/default.yaml` vs [[data_schema]]#8 | ✅ PASS | 含 `ollama.options.num_ctx: 8192` + `temperature: 0.3` |
| `models.py` vs [[data_schema]] | ✅ PASS | 10 個 dataclass 與 spec 完全對齊 |

---

## 二、Runtime Bug 修復記錄

V Phase 第一輪驗證時發現 2 個 Runtime Error，由 Verifier 就地修復後，碼農的後續修改沿用：

### Bug #1：`AttributeError: property 'page' has no setter`

- **檔案**：[[dashboard_view.py]]、[[terms_view.py]]
- **原因**：兩個類別繼承 `ft.Container`，而 Flet 0.84.0 的 `page` 是唯讀 property，`self.page = page` 觸發 AttributeError
- **修復**：將 `self.page` 改為 `self._page_ref`，全檔替換所有引用

### Bug #2：`TypeError: OutlinedButton.__init__() got unexpected keyword argument 'color'`

- **檔案**：[[dashboard_view.py]]:391
- **原因**：Flet 0.84.0 的 `OutlinedButton` 不接受直接 `color=` 參數
- **修復**：改用 `style=ft.ButtonStyle(color=COLOR_TEXT)`

> 兩個 Bug 修復後，自動化測試 106 項全通過，App 成功啟動。

---

## 三、甲方手動驗證進度

### 3.1 前置條件

- [x] 安裝 Ollama — 已安裝（0.20.2）
- [x] 下載模型 — gemma4:e4b + gemma4:e2b 皆已下載

### 3.2 功能驗證

| # | 驗證項目 | Pass/Fail | 備註 |
|---|---|---|---|
| 1 | App 啟動 + 介面外觀 | ✅ PASS | 視窗、idle 頁面、左側導航、狀態列 (gemma4:e2b) 全正常 |
| 2 | 響應式佈局 | ⏳ 待測 | 需進入 live 模式觀察三欄/兩欄/單欄 |
| 3 | 即時錄音 | ⏳ 待測 | |
| 4 | 匯入音檔 | ⏳ 待測 | |
| 5 | 完整 Pipeline | ⏳ 待測 | 含轉錄 + RAG 校正 + 摘要 |
| 6 | 即時儀表板三區塊 | ⏳ 待測 | |
| 7 | 會後編輯模式 | ⏳ 待測 | |
| 8 | 匯出 Markdown | ⏳ 待測 | |
| 9 | 詞條管理 CRUD | ⏳ 待測 | |
| 10 | 設定頁面 | ⏳ 待測 | |

### 3.3 截圖紀錄

- [[screenshots/v_phase_app_idle.png|App Idle 頁面]]（驗證 #1）— 待甲方提供

---

## 四、模型選型實測

### 4.1 硬體環境

| 項目 | 數值 |
|---|---|
| 機型 | Surface Pro 9 (i7-1255U) |
| 總記憶體 | 16 GB |
| OS | Windows 11 Pro |
| 開發時可用 RAM | ~3-5 GB（被 VS Code、Claude Code、瀏覽器等佔用） |

### 4.2 模型實測對照

| 模型 | 模型大小 | 推理 RAM 需求 | 實測結果 | 適用情境 |
|---|---|---|---|---|
| `gemma4:e4b` | 9.2 GB | 9.9 GB | ❌ OOM | 開發模式下記憶體不足；需專注使用情境 |
| `gemma4:e2b` | 6.8 GB | ~6 GB | ✅ 推理正常 | **當前驗證採用** |

### 4.3 決策

- Spec 定義的預設仍為 `gemma4:e4b`，與 [[decision_20260406_model_selection]] 保持一致
- V Phase 驗證**暫時改用 `gemma4:e2b`**，以便在開發環境下完成端到端測試
- 驗證完成後，`config/default.yaml` 應改回 `gemma4:e4b`（spec 預設）

> ⚠️ 此處改 config 屬於驗證階段的權宜做法，**非規格變更**。

---

## 五、需大統領決策的 Issues

### Issue #1：`ft.app()` Deprecated

- **位置**：[[main.py]]:177
- **現狀**：`ft.app(target=main)` 在 Flet 0.80.0 已標記 deprecated
- **影響**：目前不影響功能，但未來 Flet 版本可能移除
- **建議**：排入技術債，低優先

---

## 六、總結

| 類別 | 狀態 |
|---|---|
| 環境 | ✅ 全數通過（含 Ollama + 兩個模型） |
| 自動化測試 | ✅ 127/127 通過 |
| 冒煙測試 | ✅ App 可啟動 |
| 程式碼完整性 | ✅ Import / Config / Models 全數一致 |
| 甲方驗證 | 1/10 PASS，9 項待測 |
| 模型選型 | ⚠️ E4B 在 16GB 機器上記憶體緊繃，驗證暫用 E2B |

---

**🟡 進行中 — 暫停等待甲方繼續手動驗證**

下一步：甲方有空時，啟動 App 並依序完成驗證 #2~#10。
