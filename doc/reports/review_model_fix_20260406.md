---
title: Review Report — 四層級模型選型修正
date: 2026-04-06
type: report
status: active
author: 審察者
phase: S (Code — 模型選型修正)
target: 11 個檔案（6 source + 5 test），gemma4:4b → gemma3:4b + 設定頁四選項
verdict: ✅ Pass
tags:
  - review
  - model-selection
---

# Review Report — 四層級模型選型修正

> 審察者獨立審查。對照 [[system_overview]]（四層級模型選型表）、[[data_schema]]（設定檔）、[[ui_spec]]（設定頁）。

---

## 判定：✅ Pass

**理由：** 所有 11 個檔案的模型預設值已對齊 `gemma3:4b`，設定頁四選項與 specs 完全一致，全部 106 non-slow tests 通過，無新 bug 引入。

---

## 1. 預設值對齊檢查

### Specs 基準

| 來源 | 預設值 |
|------|--------|
| [[system_overview#2. 技術選型]] 模型選型表 | `gemma3:4b`（輕量預設） |
| [[data_schema#8. 設定檔]] | `model: "gemma3:4b"` |
| [[ui_spec#5. 設定頁]] | `[gemma3:4b ▼]` |

### 程式碼對齊結果

| 檔案 | 位置 | 值 | 狀態 |
|------|------|---|------|
| `config/default.yaml` | 第 8 行 `ollama.model` | `"gemma3:4b"` | ✅ |
| `app/core/summarizer.py` | 第 20 行 fallback | `"gemma3:4b"` | ✅ |
| `app/ui/main_view.py` | 第 31 行 StatusBar fallback | `"gemma3:4b"` | ✅ |
| `app/ui/settings_view.py` | 第 29 行 dropdown | 見 §2 | ✅ |

### 測試對齊結果

| 測試檔案 | 出現次數 | 值 | 狀態 |
|----------|---------|---|------|
| `tests/test_models.py` | 3 處 | `gemma3:4b` | ✅ |
| `tests/test_summarizer.py` | 4 處 | `gemma3:4b` | ✅ |
| `tests/test_session_manager.py` | 1 處 | `gemma3:4b` | ✅ |
| `tests/test_stream_processor.py` | 1 處 | `gemma3:4b` | ✅ |
| `tests/test_exporter.py` | 1 處 | `gemma3:4b` | ✅ |

### 遺漏掃描

全專案 `*.py` + `*.yaml` 搜尋 `gemma4:4b`（舊預設值）：**零結果**。無遺漏。

> 注意：`gemma4` 字串仍出現在多處（如 `term_id="gemma4"`、知識庫詞條範例），這些是知識庫中「Gemma 4」這個**詞條**的 ID，與 Ollama 模型名稱無關，不應修改。

---

## 2. 設定頁四選項

**位置：** `settings_view.py:29`

```python
self._dropdown("模型", ["gemma3:1b", "gemma3:4b", "gemma4:e2b", "gemma4:e4b"], "ollama.model")
```

**與 specs 對照：**

| [[system_overview]] 模型選型表 | [[ui_spec#5]] 設定頁 | 程式碼 | 狀態 |
|------|------|------|------|
| gemma3:1b（極輕量） | ✅ | ✅ 第 1 選項 | ✅ |
| gemma3:4b（輕量預設） | ✅ | ✅ 第 2 選項 | ✅ |
| gemma4:e2b（標準） | ✅ | ✅ 第 3 選項 | ✅ |
| gemma4:e4b（高階） | ✅ | ✅ 第 4 選項 | ✅ |

模型改為 dropdown（原為 text_field），與 specs 規格一致。`_dropdown` 的 fallback 邏輯（第 82 行 `current if current in options else options[0]`）確保即使 config 中存在無效值也不會 crash。

---

## 3. 測試執行

```
106 passed, 1 warning in 6.49s
```

全部 106 non-slow tests 通過。1 warning 為 pydub 的 `audioop` deprecation，非本次修正相關。

---

## 4. 新 Bug 檢查

| 檢查項 | 結果 |
|--------|------|
| `dashboard_view.py` 有無模型硬編碼 | ✅ 無 — 不直接引用模型名稱 |
| `terms_view.py` 有無模型硬編碼 | ✅ 無 |
| Summarizer prompt 中有無寫死模型名 | ✅ 無 — prompt 不引用模型名稱 |
| StatusBar 顯示是否從 config 讀取 | ✅ `config.get("ollama.model", "gemma3:4b")` |
| dropdown 預設選中值是否正確 | ✅ 從 config 讀取 `gemma3:4b`，在選項列表中 → 選中 |

---

## 審察者簽章

- **審察者**：CLI-2
- **日期**：2026-04-06
- **審查輪次**：第 1 次
- **判定**：✅ Pass — 模型選型修正完整正確
