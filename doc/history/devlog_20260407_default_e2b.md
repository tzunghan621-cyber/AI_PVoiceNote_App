---
title: 開發日誌 2026-04-07 — 預設模型改為 gemma4:e2b
date: 2026-04-07
type: devlog
status: active
author: 碼農
tags:
  - devlog
  - hotfix
  - model-config
---

# 開發日誌 — 2026-04-07 預設模型改為 gemma4:e2b

> 甲方 Surface Pro 9 實測 E4B 跑不動，預設降為 E2B，E4B 改為高階升級選項。
> 前次日誌：[[devlog_20260406_v_phase]]

---

## 起因

- 甲方在 Surface Pro 9（i7-1255U / 16GB / CPU only）實測 `gemma4:e4b` 無法正常載入（RAM 不足）
- 大統領裁決：預設改為 `gemma4:e2b`，`gemma4:e4b` 保留為高階升級選項
- Specs（[[system_overview]]、[[data_schema]]）已先行更新，本次由碼農同步 code 與 tests

---

## 變更清單

| 類型 | 檔案 | 變更 |
|---|---|---|
| 設定 | `config/default.yaml` | 已是 `gemma4:e2b`（先前 commit 已改） |
| 程式 | `app/core/summarizer.py` | fallback `gemma4:e4b` → `gemma4:e2b` |
| 程式 | `app/ui/main_view.py` | fallback `gemma4:e4b` → `gemma4:e2b` |
| 程式 | `app/ui/settings_view.py` | Dropdown 順序 `["gemma4:e4b", "gemma4:e2b"]` → `["gemma4:e2b", "gemma4:e4b"]`（E2B 為預設放第一） |
| 測試 | `tests/test_exporter.py` | `gemma4:e4b` → `gemma4:e2b` |
| 測試 | `tests/test_models.py` | `gemma4:e4b` → `gemma4:e2b`（多處） |
| 測試 | `tests/test_session_manager.py` | `gemma4:e4b` → `gemma4:e2b` |
| 測試 | `tests/test_stream_processor.py` | `gemma4:e4b` → `gemma4:e2b` |
| 測試 | `tests/test_summarizer.py` | `gemma4:e4b` → `gemma4:e2b`（多處） |

---

## 驗證

- `pytest -q`：**127 passed, 1 warning**（全綠）
- Specs 與 code 預設值一致：`gemma4:e2b`
- Settings 下拉選單順序符合「預設在前」慣例

---

## 模型階層（更新後）

| 層級 | 模型 | 用途 |
|---|---|---|
| 預設 | `gemma4:e2b` | Surface Pro 9 / 一般筆電可跑 |
| 高階升級 | `gemma4:e4b` | ≥32GB RAM 或有 GPU |

---

## 相關文件

- [[devlog_20260406_model_fix]] — 三輪模型選型迭代
- [[devlog_20260406_v_phase]] — V Phase 驗證與 E4B OOM 發現
- [[system_overview]] — specs 已同步為 E2B 預設
- [[data_schema]] — specs 已同步為 E2B 預設
