---
title: System Overview
date: 2026-04-04
type: spec
status: draft
author: Director (Claude)
tags:
  - architecture
  - tech-stack
  - pipeline
---

# System Overview

> 語音會議摘要筆記 — 系統架構與技術選型規格書
> 相關規格：[[data_schema]] ｜ [[ui_spec]]

---

## 1. 產品定位

**個人會議指揮中心。** 不只是轉錄摘要工具，而是一個可編輯、可持續迭代的會議工作區。

核心能力：
- 會議錄音即時轉錄，RAG 連動個人 Obsidian 知識庫校正專有名詞
- 工作區三區塊：**逐字稿** / **會議重點** / **Action Items**，AI 產出後使用者可即時編輯修正
- 全程本地運算（Gemma 4 + faster-whisper），會議內容不外傳
- 持續進化：養庫 → 使用回饋 → 優化知識詞條，越用越準

> 開發規範遵循 [[AI協作開發規範]]（P-S-C-V 流程 + Agent 團隊架構）

---

## 2. 技術選型

| 層 | 技術 | 版本/規格 | 備註 |
|---|---|---|---|
| 語音轉文字 | faster-whisper | small model | CPU 離線，支援中英文 |
| 摘要推理 | Gemma 4 4B | Q4 量化，透過 Ollama | CPU 推理，約 3GB RAM |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 | sentence-transformers | 多語言，適合中文知識庫 |
| 向量資料庫 | ChromaDB | 嵌入式 | 零設定，Python 原生 |
| Desktop 框架 | Flet | 基於 Flutter | Python 全端，可打包 .exe |
| 設定管理 | YAML | — | 知識庫路徑、模型參數等 |
| 模型管理 | Ollama | — | 本地模型下載與運行 |
| 語言 | Python | 3.11+ | — |

### 硬體基準

- Surface Pro 9（i7-1255U / 16GB RAM / 無獨顯）
- 純 CPU 推理，無 CUDA

---

## 3. 系統架構

### 3.1 模組分層

```
┌─────────────────────────────────────┐
│            UI Layer (Flet)          │
│  錄音 │ 匯入 │ 審閱 │ 詞條管理 │ 設定  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│          Core Pipeline              │
│                                     │
│  ┌───────────┐  ┌────────────────┐  │
│  │ Transcriber│  │ RAG Corrector  │  │
│  │ (Whisper)  │→│ (ChromaDB +    │  │
│  │            │  │  Embedding)    │  │
│  └───────────┘  └───────┬────────┘  │
│                         │           │
│                ┌────────▼────────┐  │
│                │   Summarizer    │  │
│                │   (Gemma 4)     │  │
│                └─────────────────┘  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│          Data Layer                 │
│  音檔(暫存) │ 詞條庫 │ 回饋紀錄 │ 設定  │
└─────────────────────────────────────┘
```

### 3.2 模組職責

| 模組 | 職責 | 輸入 | 輸出 |
|------|------|------|------|
| **AudioRecorder** | 麥克風錄音，產生 WAV | 麥克風音訊流 | WAV 檔（暫存） |
| **AudioImporter** | 匯入外部音檔，統一轉為 WAV | WAV/MP3/M4A 檔案路徑 | WAV 檔（暫存） |
| **Transcriber** | 語音轉文字，帶時間戳 | WAV 檔 | 逐字稿（含 segment 時間戳），格式見 [[data_schema#2. 轉錄 Segment]] |
| **KnowledgeBase** | 管理知識詞條，建立/更新向量索引 | 詞條 CRUD 操作 | ChromaDB 索引，詞條格式見 [[data_schema#1. 知識詞條（Term）]] |
| **RAGCorrector** | 用知識庫比對校正逐字稿中的專有名詞 | 逐字稿 + ChromaDB 索引 | 校正後逐字稿（含校正標記），格式見 [[data_schema#3. 校正結果]] |
| **Summarizer** | 呼叫 Gemma 4 產生結構化摘要 | 校正後逐字稿 | 摘要 / 待辦 / 決議，格式見 [[data_schema#4. 摘要結果]] |
| **SessionManager** | 管理單次會議的完整生命週期 | Pipeline 各階段產出 | Session 物件，格式見 [[data_schema#5. Session（單次會議）]] |
| **Exporter** | 匯出 Markdown，匯出後刪除音檔 | Session 物件 | .md 檔案，格式見 [[data_schema#7. 匯出格式（Markdown）]] |
| **FeedbackStore** | 儲存/讀取校正回饋紀錄 | 使用者回饋操作 | JSON 回饋紀錄，格式見 [[data_schema#6. 回饋紀錄（Feedback）]] |
| **ConfigManager** | 讀取/寫入應用設定 | YAML 設定檔 | 設定物件，格式見 [[data_schema#8. 設定檔]] |

---

## 4. 處理 Pipeline（單次會議流程）

### 4.1 分段處理策略（Chunked Pipeline）

長時間錄音（數小時）會造成記憶體與處理時間壓力。所有 Pipeline 階段採分段處理：

| 資源 | 限制 | 分段策略 |
|------|------|----------|
| WAV 暫存 | 16kHz/16bit/mono ≈ 1.9MB/min | 錄音時每 10 分鐘自動切段儲存，不累積整段在記憶體 |
| Whisper 轉錄 | CPU 推理，1 小時音檔約需 15-30 分鐘 | 逐段送入（10 分鐘/段），即時產出 segments，邊轉邊顯示進度 |
| RAG 校正 | 輕量操作，無瓶頸 | 每段轉錄完成後立即校正，不需等全部轉完 |
| Gemma 4 摘要 | 128K context ≈ 可處理 2-3 小時逐字稿 | 若逐字稿超過 context 上限 → 階層式摘要（見 4.2） |

### 4.2 階層式摘要（Hierarchical Summarization）

當逐字稿長度超過模型 context window 時：

```
段落 1 逐字稿 → Gemma 4 → 段落摘要 1
段落 2 逐字稿 → Gemma 4 → 段落摘要 2
段落 3 逐字稿 → Gemma 4 → 段落摘要 3
...
          ↓
所有段落摘要 → Gemma 4 → 最終合併摘要
                        （含全局待辦 / 決議 / 關鍵詞）
```

- **分段閾值**：逐字稿總 token 數 > 100K 時啟用（預留 28K 給 prompt + 輸出）
- **分段大小**：每段約 30 分鐘的逐字稿內容
- **段落摘要保留**：合併後段落摘要仍保留在 Session 中，匯出時可選擇是否包含

### 4.3 完整流程

```
1. 輸入
   ├── 麥克風錄音 → AudioRecorder → WAV 分段檔（每 10 分鐘切段）
   └── 音檔匯入 → AudioImporter → WAV 分段檔（長檔自動切段）
          ↓
2. 轉錄（逐段，可與步驟 3 交錯執行）
   WAV 段 N → Transcriber (faster-whisper small)
            → 逐字稿 segments [{ start, end, text }]
          ↓
3. RAG 校正（每段轉錄完成後立即執行）
   逐字稿段 N → RAGCorrector
               ├── 查詢 ChromaDB 取得相關詞條
               ├── 比對替換專有名詞
               └── 標記校正位置與原始值
            → 校正後逐字稿 [{ start, end, text, corrections }]
          ↓
4. 摘要（全部段落校正完成後）
   ├── 短會議（< 100K tokens）：整份逐字稿 → Summarizer → 結構化摘要
   └── 長會議（≥ 100K tokens）：階層式摘要（見 4.2）
       → 結構化摘要 { summary, action_items, decisions }
          ↓
5. 審閱（UI）
   使用者在 app 內檢視：
   ├── 逐字稿（可對照校正標記）
   ├── 摘要 / 待辦 / 決議
   └── 回饋標記（校正正確/錯誤/遺漏）
          ↓
6. 匯出（使用者手動觸發）
   Session → Exporter → Markdown 檔案（資訊完整）
   匯出成功 → 刪除原始 WAV 分段暫存檔
          ↓
7. 回饋儲存
   回饋標記 → FeedbackStore → data/feedback/{session_id}.json
```

---

## 5. 三階段使用模式

| 階段 | 觸發者 | 動作 | 涉及模組 | UI 頁面 |
|------|--------|------|----------|---------|
| **養庫** | 甲方（透過 Claude） | 從 Obsidian 知識庫提取重點，整理成詞條匯入 | KnowledgeBase | [[ui_spec#3. 詞條管理頁]] |
| **使用 + 回饋** | 甲方 | 執行 Pipeline，審閱結果，標記校正品質 | 全 Pipeline + FeedbackStore | [[ui_spec#2. 會議頁（主頁）]] |
| **優化** | 甲方（透過 Claude） | 分析回饋，增補/移除/調整詞條 | FeedbackStore → KnowledgeBase | [[ui_spec#4. 回饋統計頁]] |

---

## 6. 前置需求

1. **Ollama** — 需預先安裝，用於管理和運行 Gemma 4 模型
2. **Python 3.11+** — 執行環境
3. **麥克風** — 即時錄音功能需要

---

## 7. 目錄結構（程式碼）

```
AI_PVoiceNote_App/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Flet app 進入點
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_view.py        # 主視窗佈局與導航
│   │   ├── record_view.py      # 錄音 / 匯入介面
│   │   ├── session_view.py     # 單次會議審閱介面
│   │   ├── terms_view.py       # 詞條管理介面
│   │   ├── feedback_view.py    # 回饋統計介面
│   │   └── settings_view.py    # 設定頁面
│   ├── core/
│   │   ├── __init__.py
│   │   ├── audio_recorder.py   # 麥克風錄音
│   │   ├── audio_importer.py   # 音檔匯入與格式轉換
│   │   ├── transcriber.py      # Whisper 語音轉文字
│   │   ├── knowledge_base.py   # 知識詞條 CRUD + 向量索引
│   │   ├── rag_corrector.py    # RAG 校正邏輯
│   │   ├── summarizer.py       # Gemma 4 摘要產生
│   │   ├── session_manager.py  # 會議 session 生命週期
│   │   └── exporter.py         # Markdown 匯出
│   ├── data/
│   │   ├── __init__.py
│   │   ├── feedback_store.py   # 回饋紀錄讀寫
│   │   └── config_manager.py   # 設定管理
│   └── utils/
│       ├── __init__.py
│       └── audio_utils.py      # 音訊格式轉換工具
├── data/
│   ├── feedback/               # 回饋紀錄（JSON）
│   └── terms/                  # 知識詞條（YAML）
├── config/
│   └── default.yaml            # 預設設定
├── doc/                        # 文件體系（依開發規範）
│   ├── specs/
│   ├── plans/
│   ├── history/
│   ├── manuals/
│   ├── reports/
│   ├── research/
│   └── archive/
├── tests/                      # 測試
├── requirements.txt
├── pyproject.toml
└── CLAUDE.md                   # 專案級 Agent 指引
```
