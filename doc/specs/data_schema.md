---
title: Data Schema
date: 2026-04-04
type: spec
status: draft
author: Director (Claude)
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
| `source` | string | ❌ | 來源知識庫檔名（Obsidian 檔名） |
| `created` | string | ✅ | 建立日期 YYYY-MM-DD |
| `updated` | string | ✅ | 最後更新日期 YYYY-MM-DD |
| `stats` | object | ✅ | 效能統計（由系統自動更新） |

---

## 2. 轉錄 Segment

**用途：** Pipeline 內部傳遞，不獨立儲存（由 [[system_overview#3.2 模組職責|Transcriber]] 產生）

```python
@dataclass
class TranscriptSegment:
    start: float          # 開始時間（秒）
    end: float            # 結束時間（秒）
    text: str             # 原始轉錄文字
    confidence: float     # Whisper 信心分數（0-1）
```

---

## 3. 校正結果

**用途：** Pipeline 內部傳遞，隨 Session 儲存（由 [[system_overview#3.2 模組職責|RAGCorrector]] 產生）

```python
@dataclass
class Correction:
    segment_index: int    # 對應的 segment 索引
    original: str         # 原始文字片段
    corrected: str        # 校正後文字
    term_id: str          # 命中的詞條 ID
    similarity: float     # 向量相似度分數（0-1）

@dataclass
class CorrectedSegment:
    start: float
    end: float
    original_text: str        # 原始轉錄
    corrected_text: str       # 校正後文字
    corrections: list[Correction]  # 該 segment 的所有校正
```

---

## 4. 摘要結果

**用途：** Gemma 4 輸出，隨 Session 儲存（由 [[system_overview#3.2 模組職責|Summarizer]] 產生）

```python
@dataclass
class ActionItem:
    id: str                   # UUID
    content: str              # 待辦內容
    owner: str | None         # 負責人（Gemma 從逐字稿推斷，使用者可修改）
    deadline: str | None      # 期限（Gemma 推斷或使用者指定，YYYY-MM-DD）
    source_segment: int       # 來源 segment 索引（可回溯原始對話）
    status: str               # "open" | "done" | "dropped"
    priority: str             # "high" | "medium" | "low"（Gemma 推斷，使用者可改）
    note: str | None          # 使用者補充備註
    created: str              # ISO 8601
    updated: str              # ISO 8601

@dataclass
class SummaryResult:
    highlights: str           # 會議重點摘要（Markdown，使用者可編輯）
    action_items: list[ActionItem]  # 結構化待辦事項
    decisions: list[str]      # 決議事項清單
    keywords: list[str]       # 關鍵詞（供後續 RAG 回饋用）
    model: str                # 使用的模型名稱
    generation_time: float    # 產生耗時（秒）
```

> `highlights` 改自原 `summary`，強調這是「會議重點」而非完整摘要。使用者可在 [[ui_spec#2.4 工作區]] 直接編輯。

---

## 5. Session（單次會議）

**用途：** 管理完整會議生命週期
**儲存位置：** `data/sessions/{session_id}.json`（暫存，匯出後可刪除）

```python
@dataclass
class Session:
    id: str                       # UUID
    created: str                  # ISO 8601 timestamp
    status: str                   # recording | transcribing | correcting | summarizing | ready | exported
    audio_paths: list[str]        # WAV 分段暫存路徑（匯出後清空）
    audio_source: str             # "microphone" | "import"
    audio_duration: float         # 音檔總長度（秒）
    chunk_count: int              # 音檔分段數
    segments: list[TranscriptSegment]       # 原始轉錄（所有段合併，時間戳連續）
    corrected_segments: list[CorrectedSegment]  # 校正後
    chunk_summaries: list[SummaryResult]    # 段落摘要（階層式摘要時使用，短會議為空）
    summary: SummaryResult | None           # 最終合併摘要
    feedback: list[FeedbackEntry] | None    # 使用者回饋
    export_path: str | None       # 匯出路徑（匯出後填入）
```

> 分段處理策略見 [[system_overview#4.1 分段處理策略（Chunked Pipeline）]]
> 階層式摘要見 [[system_overview#4.2 階層式摘要（Hierarchical Summarization）]]

---

## 6. 回饋紀錄（Feedback）

**儲存位置：** `data/feedback/{session_id}.json`
**生命週期：** 永久保留（用於優化分析，見 [[ui_spec#4. 回饋統計頁]]）

```python
@dataclass
class FeedbackEntry:
    segment_index: int        # 對應 segment
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

**匯出檔案結構：**

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

{summary}

## 待辦事項

- [ ] {action_item_1}
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

> 校正標記只在有校正的段落顯示，使用刪除線標註原始值。匯出由 [[system_overview#3.2 模組職責|Exporter]] 執行，使用者在 [[ui_spec#2.4 審閱模式]] 手動觸發。

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

# 知識庫
knowledge_base:
  terms_dir: "data/terms"
  chroma_dir: "data/chroma"

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
```
