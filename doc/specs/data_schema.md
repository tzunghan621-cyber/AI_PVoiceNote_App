---
title: Data Schema
date: 2026-04-05
type: spec
status: draft
author: 大統領
tags:
  - data-schema
  - terms
  - feedback
  - export
---

# Data Schema

> 語音會議摘要筆記 — 資料結構規格書
> 系統架構見 [[system_overview]] ｜ UI 規格見 [[ui_spec]]

---

## 1. 知識詞條（Term）

**所屬：** App 自有知識庫（見 [[system_overview#5. 知識庫架構]]）
**儲存位置：** `data/terms/`
**格式：** 每個詞條一個 YAML 檔案，檔名為 `{term_id}.yaml`

```yaml
# data/terms/gemma4.yaml
---
id: "gemma4"
term: "Gemma 4"
aliases:
  - "寶石四"
  - "gemma4"
  - "GEMMA"
category: "技術/AI模型"
context: "Google 開源本地端 LLM，基於 Gemini 3 開發"
source: "學習筆記_Gemma.md"
origin: "obsidian_sync"
created: "2026-04-04"
updated: "2026-04-04"
stats:
  hit_count: 0          # 被 RAG 查詢命中的次數
  correction_count: 0   # 實際被用於校正的次數
  success_count: 0      # 使用者確認校正正確的次數
  fail_count: 0         # 使用者標記校正錯誤的次數
```

### 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `id` | string | ✅ | 唯一識別碼，英文小寫 + 底線 |
| `term` | string | ✅ | 正確名稱（校正目標） |
| `aliases` | list[string] | ✅ | 可能的誤聽形式、同義詞、縮寫 |
| `category` | string | ❌ | 分類（自由文字，用 `/` 分層） |
| `context` | string | ❌ | 補充說明，幫助 RAG 理解語境 |
| `source` | string | ❌ | 來源檔名（Obsidian 檔名或會議 ID） |
| `origin` | string | ✅ | 來源類型：`obsidian_sync` / `manual` / `auto_suggest` |
| `created` | string | ✅ | 建立日期 YYYY-MM-DD |
| `updated` | string | ✅ | 最後更新日期 YYYY-MM-DD |
| `stats` | object | ✅ | 效能統計（由系統自動更新） |

> `origin` 追蹤詞條來源：`obsidian_sync`（Claude Code 從知識庫同步）、`manual`（使用者手動新增）、`auto_suggest`（App 從高頻遺漏自動建議）

---

## 2. 轉錄 Segment

**用途：** 串流 Pipeline 即時產出，逐條送至 UI 顯示（由 [[system_overview#3.2 模組職責|Transcriber]] 產生）

```python
@dataclass
class TranscriptSegment:
    index: int            # 全局序號（從 0 遞增）
    start: float          # 開始時間（秒）
    end: float            # 結束時間（秒）
    text: str             # 原始轉錄文字
    confidence: float     # Whisper 信心分數（0-1）
    chunk_id: int         # 所屬音訊分段編號
```

---

## 3. 校正結果

**用途：** 即時校正後送至 UI 顯示（由 [[system_overview#3.2 模組職責|RAGCorrector]] 產生）

```python
@dataclass
class Correction:
    segment_index: int    # 對應的 segment 全局序號
    original: str         # 原始文字片段
    corrected: str        # 校正後文字
    term_id: str          # 命中的詞條 ID
    similarity: float     # 向量相似度分數（0-1）

@dataclass
class CorrectedSegment:
    index: int                # 全局序號（與 TranscriptSegment.index 對應）
    start: float
    end: float
    original_text: str        # 原始轉錄
    corrected_text: str       # 校正後文字
    corrections: list[Correction]  # 該 segment 的所有校正
```

---

## 4. 摘要結果

**用途：** Gemma 4 週期性產出，每次更新覆蓋前次結果（由 [[system_overview#3.2 模組職責|Summarizer]] 產生）

```python
@dataclass
class ActionItem:
    id: str                   # UUID
    content: str              # 待辦內容
    owner: str | None         # 負責人（Gemma 推斷，使用者可改）
    deadline: str | None      # 期限（YYYY-MM-DD）
    source_segment: int       # 來源 segment 全局序號（可回溯原始對話）
    status: str               # "open" | "done" | "dropped"
    priority: str             # "high" | "medium" | "low"
    note: str | None          # 使用者補充備註
    created: str              # ISO 8601
    updated: str              # ISO 8601

@dataclass
class SummaryResult:
    version: int              # 摘要版本號（每次週期更新 +1）
    highlights: str           # 會議重點摘要（Markdown，使用者可編輯）
    action_items: list[ActionItem]  # 結構化待辦事項
    decisions: list[str]      # 決議事項清單
    keywords: list[str]       # 關鍵詞
    covered_until: int        # 本次摘要涵蓋到第幾個 segment
    model: str                # 使用的模型名稱
    generation_time: float    # 產生耗時（秒）
    is_final: bool            # 是否為最終摘要（停止錄音後產生）
```

> `version` 遞增追蹤摘要演進。`covered_until` 標記本次摘要涵蓋的 segment 範圍，供增量更新使用。
> 會中每 3~5 分鐘產生一版，停止錄音後產生 `is_final=True` 的最終版。
> 詳見 [[system_overview#4.2 週期性摘要更新]]

---

## 5. Session（單次會議）

**用途：** 管理完整會議生命週期（會中即時 → 會後編輯 → 匯出）
**儲存位置：** `data/sessions/{session_id}.json`

```python
@dataclass
class Session:
    id: str                       # UUID
    title: str                    # 會議名稱（可由使用者命名，預設為日期時間）
    created: str                  # ISO 8601 timestamp
    ended: str | None             # 錄音結束時間（會中時為 None）
    mode: str                     # "live" | "review"（會中即時 / 會後編輯）
    status: str                   # recording | processing | ready | exported
    audio_paths: list[str]        # WAV 分段暫存路徑（匯出後清空）
    audio_source: str             # "microphone" | "import"
    audio_duration: float         # 音檔總長度（秒，會中持續更新）
    segments: list[CorrectedSegment]     # 校正後逐字稿（即時累積）
    summary_history: list[SummaryResult] # 摘要版本歷史（週期更新累積）
    summary: SummaryResult | None        # 當前最新摘要（= summary_history[-1]）
    user_edits: UserEdits | None         # 使用者在會後編輯的內容
    feedback: list[FeedbackEntry] | None # 使用者回饋
    export_path: str | None       # 匯出路徑（匯出後填入）
```

### Session 狀態流轉

```
[開始錄音/匯入音檔]
      │
      ▼
  recording ──── mode: "live"
  （串流處理中，逐字稿即時累積，摘要週期更新）
      │
  [停止錄音/匯入完成]
      │
      ▼
  processing ── 產生最終摘要
      │
      ▼
  ready ──────── mode: "review"
  （可編輯、可回饋、可匯出）
      │
  [匯出]
      │
      ▼
  exported ──── 音檔已刪除，Session 保留供回溯
```

---

## 5.1 使用者編輯（會後）

```python
@dataclass
class UserEdits:
    highlights_edited: str | None    # 使用者修改後的會議重點（None = 未修改）
    decisions_edited: list[str] | None  # 使用者修改後的決議
    edited_at: str                   # ISO 8601
```

> 使用者在會後編輯模式中修改的內容獨立存放，不覆蓋 AI 原始產出。匯出時以使用者編輯版本為準，同時保留 AI 原始版本供對照。

---

## 6. 回饋紀錄（Feedback）

**儲存位置：** `data/feedback/{session_id}.json`
**生命週期：** 永久保留（用於優化分析，見 [[ui_spec#4. 回饋統計頁]]）

```python
@dataclass
class FeedbackEntry:
    segment_index: int        # 對應 segment 全局序號
    correction_index: int     # 對應該 segment 中的第幾個 correction（-1 表示遺漏回報）
    type: str                 # "correct" | "wrong" | "missed"
    term_id: str | None       # 相關詞條 ID（missed 類型時可能無）
    expected: str | None      # 使用者期望的正確值（wrong/missed 時填寫）
    note: str | None          # 備註
    timestamp: str            # ISO 8601

@dataclass
class SessionFeedback:
    session_id: str
    created: str              # ISO 8601
    entries: list[FeedbackEntry]
    summary_rating: int       # 摘要品質 1-5 分
    summary_note: str | None  # 摘要回饋備註
```

---

## 7. 匯出格式（Markdown）

匯出由 [[system_overview#3.2 模組職責|Exporter]] 執行，使用者在 [[ui_spec#2.4 會後編輯模式]] 手動觸發。

**匯出邏輯：** 有使用者編輯時以編輯版本為準，無編輯時使用 AI 最終摘要。

```markdown
---
title: 會議摘要 — {日期} {時間}
date: {YYYY-MM-DD}
duration: {HH:MM:SS}
source: AI_PVoiceNote_App
tags:
  - 會議摘要
---

# 會議摘要 — {日期} {時間}

## 摘要

{highlights — 使用者編輯版或 AI 最終版}

## 待辦事項

- [ ] {action_item_1}（負責人：{owner}，期限：{deadline}，優先級：{priority}）
- [ ] {action_item_2}

## 決議事項

- {decision_1}
- {decision_2}

## 關鍵詞

{keywords, comma-separated}

---

## 逐字稿

### [{HH:MM:SS}]
{corrected_text}
~~{original_text}~~ → **{corrected_text}**（校正：{term_id}）

### [{HH:MM:SS}]
{text}

...
```

> Action Items 匯出時包含負責人/期限/優先級完整資訊。
> 校正標記只在有校正的段落顯示，使用刪除線標註原始值。

---

## 8. 設定檔

**路徑：** `config/default.yaml`

```yaml
# 模型設定
whisper:
  model: "small"
  language: "zh"
  device: "cpu"

ollama:
  model: "gemma4:4b"
  base_url: "http://localhost:11434"

embedding:
  model: "paraphrase-multilingual-MiniLM-L12-v2"

# App 知識庫
knowledge_base:
  terms_dir: "data/terms"
  chroma_dir: "data/chroma"

# 串流處理
streaming:
  summary_interval_sec: 180       # 摘要更新週期（秒），預設 3 分鐘
  summary_min_new_segments: 10    # 至少累積 N 個新 segments 才觸發摘要
  audio_chunk_duration_sec: 600   # 音訊分段長度（秒），預設 10 分鐘

# 音訊
audio:
  sample_rate: 16000
  channels: 1
  temp_dir: "data/temp"

# 匯出
export:
  default_dir: ""  # 空字串時每次匯出都問使用者
  include_raw_transcript: true
  include_corrections: true

# 回饋
feedback:
  dir: "data/feedback"

# Sessions
sessions:
  dir: "data/sessions"
```
