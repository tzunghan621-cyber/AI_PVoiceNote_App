---
title: 開發日誌 2026-04-05 — S Phase（Phase 2 組合模組 + Phase 3 管線整合）
date: 2026-04-05
type: devlog
status: active
author: 碼農
tags:
  - devlog
  - s-phase
  - tdd
  - phase-2
  - phase-3
---

# 開發日誌 — 2026-04-05 S Phase（Phase 2 + 3）

> 碼農執行 S Phase：Phase 2 組合模組 + Phase 3 管線整合。
> 依據 [[plan_implementation_20260405]]（已通過 Review Gate）。
> 前次日誌：[[devlog_20260405_s_phase]]

---

## 完成事項

### Phase 2：組合模組（依賴 Phase 0 + 1）

| 模組 | 檔案 | 測試 | 說明 |
|------|------|------|------|
| RAGCorrector | `app/core/rag_corrector.py` | `tests/test_rag_corrector.py`（11 tests） | alias 模糊比對 + 相似度閾值 + 統計更新。同一 term 多 alias 不重複校正 |
| Summarizer | `app/core/summarizer.py` | `tests/test_summarizer.py`（9 tests） | Ollama HTTP 呼叫 + JSON 解析 + 增量 index 過濾（m-1）+ fallback（T-1） |
| SessionManager | `app/core/session_manager.py` | `tests/test_session_manager.py`（14 tests） | 全生命週期 + save/load 一致性（T-2）+ delete_audio（M-1） |
| Exporter | `app/core/exporter.py` | `tests/test_exporter.py`（13 tests） | Markdown 匯出（data_schema#7）+ user_edits 優先 + 不刪音檔（M-1） |

### Phase 3：管線整合

| 模組 | 檔案 | 測試 | 說明 |
|------|------|------|------|
| StreamProcessor | `app/core/stream_processor.py` | `tests/test_stream_processor.py`（6 tests） | 串流管線控制器 + 週期摘要觸發 + 最終摘要 + _summarizing 旗標（R-1） |

---

## 測試結果

```
全部非 ML 測試（Phase 0-3）：105 passed in 19.27s ✅
（含 Phase 0+1 的 52 tests + Phase 2+3 新增 53 tests）
```

### 測試覆蓋的 Review 修正項

| Review 項 | 測試涵蓋 |
|-----------|---------|
| m-1（Summarizer index 過濾） | `test_incremental_uses_index_filter` — 驗證 prompt 只含 index > covered_until |
| T-1（JSON fallback） | `test_json_parse_failure_fallback` + `test_json_parse_failure_no_previous` |
| T-2（save→load 一致性） | `test_save_and_load` — 驗證 segments、corrections、summary、user_edits 全部還原 |
| M-1（不刪音檔） | `test_does_not_delete_audio`（Exporter）+ `test_delete_audio`（SessionManager） |
| R-1（CPU 競爭旗標） | `test_summarizing_flag` |

---

## 架構決策

### 1. RAGCorrector 同一 term 只用第一個匹配 alias

**問題**：「寶石四」被替換為「Gemma 4」後，corrected_text 中的「Gemma」又匹配到 alias「GEMMA」，造成雙重校正（「Gemma 4 4」）。

**解法**：引入 `corrected_term_ids` set，每個 term 只用第一個命中的 alias 做校正，命中後 `break` 跳出 alias 迴圈。同時，alias 匹配檢查改為對 `segment.text`（原始文字）而非 `corrected_text`，避免替換後的文字被二次匹配。

### 2. Summarizer JSON fallback 策略

依計畫 T-1 實作：
- 有前次摘要：保留前次 highlights/decisions/keywords，version 遞增
- 無前次摘要：回傳空摘要（highlights=""）

不 retry — 避免在會中模態下阻塞 pipeline。

### 3. SessionManager 手動反序列化

未使用 `models.from_json()` 的通用反序列化，改為手動 `_dict_to_session` / `_dict_to_summary`。原因：
- Session 結構深度巢狀（Session → CorrectedSegment → Correction, SummaryResult → ActionItem）
- 手動控制每一層的還原邏輯更可靠，避免 type hint 字串解析的邊界情況
- T-2 測試驗證了完整的 save → load 一致性

### 4. StreamProcessor 週期摘要觸發條件

嚴格遵循 [[system_overview#4.2]]：
- `elapsed >= summary_interval` **且** `segments_since_summary >= min_new_segments` **且** `not _summarizing`
- 三條件同時滿足才觸發
- `_summarizing` 旗標防止 Whisper 與 Gemma 同時推理（R-1）

### 5. Summarizer 新增 httpx 依賴

計畫偽代碼未指定 HTTP 庫。選用 `httpx` 因其原生支援 async，且已被 `ollama` 套件間接安裝。未新增到 `pyproject.toml`（已隨 ollama 安裝）。

---

## 目前目錄結構

```
AI_PVoiceNote_App/
├── app/
│   ├── core/
│   │   ├── models.py              ✅ Phase 0
│   │   ├── knowledge_base.py      ✅ Phase 1
│   │   ├── transcriber.py         ✅ Phase 1
│   │   ├── audio_recorder.py      ✅ Phase 1
│   │   ├── audio_importer.py      ✅ Phase 1
│   │   ├── rag_corrector.py       ✅ Phase 2（本次）
│   │   ├── summarizer.py          ✅ Phase 2（本次）
│   │   ├── session_manager.py     ✅ Phase 2（本次）
│   │   ├── exporter.py            ✅ Phase 2（本次）
│   │   └── stream_processor.py    ✅ Phase 3（本次）
│   ├── data/
│   │   ├── config_manager.py      ✅ Phase 0
│   │   └── feedback_store.py      ✅ Phase 1
│   ├── ui/                        🔲 Phase 4（待做）
│   └── utils/                     🔲 （需要時補充）
├── tests/
│   ├── test_models.py             ✅ 21 tests
│   ├── test_config_manager.py     ✅ 9 tests
│   ├── test_knowledge_base.py     ✅ 14 tests (slow)
│   ├── test_transcriber.py        ✅ 7 tests (slow)
│   ├── test_audio_recorder.py     ✅ 6 tests
│   ├── test_audio_importer.py     ✅ 7 tests
│   ├── test_feedback_store.py     ✅ 9 tests
│   ├── test_rag_corrector.py      ✅ 11 tests（本次）
│   ├── test_summarizer.py         ✅ 9 tests（本次）
│   ├── test_session_manager.py    ✅ 14 tests（本次）
│   ├── test_exporter.py           ✅ 13 tests（本次）
│   └── test_stream_processor.py   ✅ 6 tests（本次）
└── ...
```

**測試總計：126 tests**（105 non-slow + 21 slow）

---

## 下一步

等待大統領指示：
1. 審察者 Review Phase 2+3
2. 或進入 Phase 4 UI 核心頁面（main_view, dashboard_view, settings_view）
