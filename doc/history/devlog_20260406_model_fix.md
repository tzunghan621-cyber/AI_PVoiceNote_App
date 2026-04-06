---
title: 開發日誌 2026-04-06 — 模型名稱修正 + 四層級選型
date: 2026-04-06
type: devlog
status: active
author: 碼農
tags:
  - devlog
  - hotfix
  - model-config
  - v-phase
---

# 開發日誌 — 2026-04-06 模型名稱修正

> V Phase 測試發現模型名稱問題，大統領裁決後由碼農修正。
> 前次日誌：[[devlog_20260405_s_ui_fix]]

---

## 修正一：`gemma4:4b` → `gemma4:e4b`

**起因：** 實驗者 V Phase 驗證時發現 `gemma4:4b` 在 Ollama 上不存在（`pull` 回傳 `file does not exist`）。正確的 Ollama tag 是 `gemma4:e4b`。

**修正範圍（8 檔案）：**

| 類別 | 檔案 | 修正 |
|------|------|------|
| 設定 | `config/default.yaml` | `gemma4:4b` → `gemma4:e4b` |
| 程式 | `app/core/summarizer.py` | fallback 值 |
| 程式 | `app/ui/main_view.py` | fallback 值 |
| 測試 | `tests/test_exporter.py` | model 字串 |
| 測試 | `tests/test_models.py` | model 字串（3 處） |
| 測試 | `tests/test_session_manager.py` | model 字串 |
| 測試 | `tests/test_stream_processor.py` | model 字串 |
| 測試 | `tests/test_summarizer.py` | model 字串（4 處） |

---

## 修正二：四層級模型選型（預設 `gemma3:4b`）

**起因：** 大統領裁決採用四層級模型選型策略，預設使用 `gemma3:4b`（Surface Pro 9 上已驗證可用），高階選項保留 `gemma4:e4b`。

**Specs 更新（大統領完成）：**
- [[system_overview]] 模型選型表新增四層級
- [[data_schema#8. 設定檔]] 預設值更新
- [[ui_spec#5. 設定頁]] 下拉選單定義

**碼農修正範圍（8 檔案）：**

| 類別 | 檔案 | 修正 |
|------|------|------|
| 設定 | `config/default.yaml` | `gemma4:e4b` → `gemma3:4b` |
| 程式 | `app/core/summarizer.py` | fallback → `gemma3:4b` |
| 程式 | `app/ui/main_view.py` | fallback → `gemma3:4b` |
| 程式 | `app/ui/settings_view.py` | TextField → Dropdown（四選項） |
| 測試 | 5 個測試檔 | 全部 `gemma4:e4b` → `gemma3:4b` |

**四層級選項（設定頁 Dropdown）：**

| 選項 | 大小 | 適用場景 |
|------|------|---------|
| `gemma3:1b` | ~1GB | 輕量快速，低 RAM 環境 |
| `gemma3:4b` | ~3GB | **預設**，平衡品質與速度 |
| `gemma4:e2b` | ~2GB | Gemma 4 架構，中等 |
| `gemma4:e4b` | ~4GB | 最高品質，需較多 RAM |

---

## 測試結果

兩次修正後均確認：

```
106 passed, 21 deselected ✅
```
