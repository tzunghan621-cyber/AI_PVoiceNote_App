---
title: System Overview
date: 2026-04-05
type: spec
status: draft
author: 大統領
tags:
  - architecture
  - tech-stack
  - pipeline
---

# System Overview

> 語音會議摘要筆記 — 系統架構與技術選型規格書
> 相關規格：[[data_schema]] ｜ [[ui_spec]] ｜ [[team_roster]]

---

## 1. 產品定位

**會議即時智能儀表板。** 開會時投影在大螢幕或放在筆電側邊，即時顯示逐字稿、會議重點、Action Items。它不是會後才用的工具，它是**會議進行中的一員**。

核心能力：
- **即時串流處理**：錄音同時轉錄 → 校正 → 每 3~5 分鐘週期性更新重點與 Action Items
- **三區塊即時儀表板**：逐字稿即時滾動 / 會議重點累積更新 / Action Items 累積更新
- **會後編輯模式**：停止錄音後，同一畫面切換為可編輯的工作區
- **App 自有知識庫**：獨立的智能產品，有自己的知識體系，透過 Claude Code 從外部 Obsidian 知識庫同步充實
- **全程本地運算**：Gemma 4 + faster-whisper + ChromaDB，會議內容不外傳
- **自我進化**：從每次會議的使用回饋中學習，越用越準

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
┌─────────────────────────────────────────┐
│              UI Layer (Flet)            │
│  即時儀表板（會中）│ 編輯工作區（會後）   │
│  詞條管理 │ 回饋統計 │ 設定               │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│        Streaming Pipeline               │
│                                         │
│  AudioRecorder ──→ StreamProcessor      │
│       │              │                  │
│       │        ┌─────┴─────┐            │
│       │        │ Transcriber│            │
│       │        │ (Whisper)  │            │
│       │        └─────┬─────┘            │
│       │              │ 即時              │
│       │        ┌─────▼──────┐           │
│       │        │RAG Corrector│           │
│       │        └─────┬──────┘           │
│       │              │ 即時              │
│  每 3~5 分鐘    ┌─────▼──────┐           │
│  週期觸發 ────→ │ Summarizer │           │
│                │ (Gemma 4)  │           │
│                └────────────┘           │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│           Data Layer                    │
│  App 知識庫（ChromaDB + 詞條）           │
│  Sessions │ 回饋紀錄 │ 設定              │
└─────────────────────────────────────────┘
```

### 3.2 模組職責

| 模組 | 職責 | 輸入 | 輸出 |
|------|------|------|------|
| **AudioRecorder** | 麥克風錄音，串流輸出音訊區塊 | 麥克風音訊流 | 音訊區塊（串流）+ WAV 分段檔（暫存） |
| **AudioImporter** | 匯入外部音檔，切段後送入 Pipeline | WAV/MP3/M4A 檔案路徑 | 音訊區塊序列 + WAV 分段檔（暫存） |
| **StreamProcessor** | 串流管線控制器，協調轉錄→校正→週期摘要 | 音訊區塊串流 | 即時 UI 更新事件 |
| **Transcriber** | 語音轉文字，即時產出 segments | 音訊區塊 | 逐字稿 segments（即時），格式見 [[data_schema#2. 轉錄 Segment]] |
| **KnowledgeBase** | App 自有知識庫，管理詞條 + 向量索引 | 詞條 CRUD / 外部同步 | ChromaDB 索引，格式見 [[data_schema#1. 知識詞條（Term）]] |
| **RAGCorrector** | 即時校正逐字稿中的專有名詞 | 逐字稿 segment + ChromaDB | 校正後 segment（即時），格式見 [[data_schema#3. 校正結果]] |
| **Summarizer** | 週期性呼叫 Gemma 4 產生/更新摘要 | 累積的校正後逐字稿 | 會議重點 + Action Items + 決議（增量更新），格式見 [[data_schema#4. 摘要結果]] |
| **SessionManager** | 管理會議生命週期（會中 → 會後 → 匯出） | Pipeline 各階段產出 | Session 物件，格式見 [[data_schema#5. Session（單次會議）]] |
| **Exporter** | 匯出 Markdown，匯出後刪除音檔 | Session 物件 | .md 檔案，格式見 [[data_schema#7. 匯出格式（Markdown）]] |
| **FeedbackStore** | 儲存/讀取校正回饋紀錄 | 使用者回饋操作 | JSON 回饋紀錄，格式見 [[data_schema#6. 回饋紀錄（Feedback）]] |
| **ConfigManager** | 讀取/寫入應用設定 | YAML 設定檔 | 設定物件，格式見 [[data_schema#8. 設定檔]] |

---

## 4. 串流處理 Pipeline

### 4.1 即時串流架構

與舊版批次處理的根本差異：**錄音、轉錄、校正同時進行，摘要週期性更新**。

```
時間軸 ──────────────────────────────────────────→

錄音    ████████████████████████████████████████ STOP
         │    │    │    │    │    │    │
轉錄     ██   ██   ██   ██   ██   ██   ██
         即時逐字稿持續產出，UI 即時滾動顯示
              │    │    │    │    │    │
校正          ██   ██   ██   ██   ██   ██
              即時校正，校正標記即時出現
                   │              │
摘要                ██             ██          ██
                  週期摘要 1     週期摘要 2   最終摘要
                  (重點+Actions  (累積更新)  (停止後)
                   首次出現)
```

### 4.2 週期性摘要更新

| 參數 | 值 | 說明 |
|------|---|------|
| 摘要週期 | 3~5 分鐘（可設定） | 累積足夠新內容後觸發 |
| 觸發條件 | 新增 ≥ N 個 segments 且距上次摘要 ≥ 週期時間 | 避免內容太少時浪費推理資源 |
| 更新方式 | 增量式 | 將新段落 + 前次摘要送入 Gemma 4，產生更新後的重點/Actions/決議 |
| 最終摘要 | 停止錄音後 | 全部內容的最終整合摘要 |

**增量摘要 Prompt 策略：**

```
前次摘要結果：{previous_summary}
新增逐字稿段落：{new_segments}

請更新會議重點、Action Items、決議事項。
保留仍然有效的項目，新增或修改有變化的項目。
```

### 4.3 長會議處理

長時間會議（數小時）的資源管理：

| 資源 | 策略 |
|------|------|
| 音訊記憶體 | 串流處理，不在記憶體累積整段；每 10 分鐘切段存檔 |
| Whisper | 逐段即時處理，段與段之間無依賴 |
| RAG 校正 | 逐 segment 即時處理，無累積壓力 |
| Gemma 4 摘要 | 增量式更新，每次只送新段落 + 前次摘要；若累積超過 100K tokens 則採階層式摘要 |
| UI 逐字稿 | 虛擬捲動，只渲染可見區域 |

### 4.4 階層式摘要（Hierarchical Summarization）

當累積逐字稿超過 Gemma 4 context window 時自動啟用：

```
段落群 1 (0~30min)  → 段落摘要 1
段落群 2 (30~60min) → 段落摘要 2
段落群 3 (60~90min) → 段落摘要 3
...
全部段落摘要 → 最終合併摘要
```

### 4.5 音檔匯入流程

匯入音檔不是即時的，但仍走串流 Pipeline：

```
音檔匯入 → 切段 → 逐段送入 StreamProcessor
                    → 轉錄 + 校正即時產出（UI 顯示進度）
                    → 每段完成後觸發摘要更新
                    → 全部完成後最終摘要
```

匯入時 UI 直接進入儀表板畫面，逐字稿/重點/Actions 隨處理進度逐步填充。

---

## 5. 知識庫架構

### 5.1 App 自有知識庫

App 是一個**獨立的智能產品**，擁有自己的知識體系：

```
App 知識庫
├── 詞條庫（data/terms/）     ← 結構化知識詞條（YAML）
├── 向量索引（data/chroma/）   ← ChromaDB 嵌入向量
└── 會議記憶                   ← 從歷史會議中累積的語境知識
```

### 5.2 外部知識同步

App 的知識庫透過 Claude Code 從使用者的 Obsidian 知識庫同步充實：

```
使用者的 Obsidian 知識庫（KNOWLEDGE_BASE/）
          │
          │  甲方透過 Claude Code 指揮
          │  「把這些重點建進 App 的知識庫」
          ▼
    Claude Code 提取、整理、格式化
          │
          ▼
    App 自有知識庫（data/terms/ + data/chroma/）
```

| 來源 | 方式 | 說明 |
|------|------|------|
| **Obsidian 知識庫** | 由 Claude Code 手動同步 | 甲方指揮 Claude Code 提取重點，整理成詞條匯入 |
| **會議回饋** | App 自動學習 | 高頻遺漏 → 建議新增詞條；低效詞條 → 建議調整/移除 |
| **手動維護** | App 內建詞條管理 UI | 使用者直接在 App 中新增/編輯/刪除詞條 |

### 5.3 知識庫與 Pipeline 的關係

```
知識庫 ──→ RAGCorrector（即時校正）
  ↑                │
  │                ▼
  └──── FeedbackStore（回饋驅動優化）
```

---

## 6. 兩種使用模態

| 模態 | 場景 | UI 狀態 | 使用者行為 |
|------|------|---------|-----------|
| **會中（即時儀表板）** | 開會中，大螢幕或半邊螢幕 | 三區塊即時更新，逐字稿唯讀，重點/Actions 可編輯 | 偶爾瞄一眼確認結論；助理可即時修正 AI 產出 |
| **會後（編輯工作區）** | 會議結束後 | 三區塊可編輯，可回饋 | 修正、補充、標記回饋、匯出 |

詳見 [[ui_spec#2. 會議頁（主頁）]]

---

## 7. 三階段進化模式

| 階段 | 觸發者 | 動作 | 涉及模組 | UI 頁面 |
|------|--------|------|----------|---------|
| **養庫** | 甲方（透過 Claude Code） | 從 Obsidian 知識庫提取重點，同步至 App 知識庫 | KnowledgeBase | [[ui_spec#3. 詞條管理頁]] |
| **使用 + 回饋** | 甲方 | 開會即時使用，會後審閱回饋 | 全 Pipeline + FeedbackStore | [[ui_spec#2. 會議頁（主頁）]] |
| **優化** | 甲方（透過 Claude Code） | 分析回饋，增補/移除/調整 App 知識庫詞條 | FeedbackStore → KnowledgeBase | [[ui_spec#4. 回饋統計頁]] |

---

## 8. 前置需求

1. **Ollama** — 需預先安裝，用於管理和運行 Gemma 4 模型
2. **Python 3.11+** — 執行環境
3. **麥克風** — 即時錄音功能需要

---

## 9. 目錄結構（程式碼）

```
AI_PVoiceNote_App/
├── app/
│   ├── __init__.py
│   ├── main.py                   # Flet app 進入點
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── main_view.py          # 主視窗佈局與導航
│   │   ├── dashboard_view.py     # 即時儀表板（會中）+ 編輯工作區（會後）
│   │   ├── terms_view.py         # 詞條管理介面
│   │   ├── feedback_view.py      # 回饋統計介面
│   │   └── settings_view.py      # 設定頁面
│   ├── core/
│   │   ├── __init__.py
│   │   ├── models.py             # 所有 dataclass 集中定義
│   │   ├── audio_recorder.py     # 麥克風錄音（串流輸出）
│   │   ├── audio_importer.py     # 音檔匯入與切段
│   │   ├── stream_processor.py   # 串流管線控制器
│   │   ├── transcriber.py        # Whisper 即時轉錄
│   │   ├── knowledge_base.py     # App 知識庫（詞條 + 向量索引）
│   │   ├── rag_corrector.py      # 即時 RAG 校正
│   │   ├── summarizer.py         # 週期性 Gemma 4 摘要
│   │   ├── session_manager.py    # 會議生命週期管理
│   │   └── exporter.py           # Markdown 匯出
│   ├── data/
│   │   ├── __init__.py
│   │   ├── feedback_store.py     # 回饋紀錄讀寫
│   │   └── config_manager.py     # 設定管理
│   └── utils/
│       ├── __init__.py
│       └── audio_utils.py        # 音訊格式工具
├── data/
│   ├── terms/                    # App 知識庫詞條（YAML）
│   ├── chroma/                   # ChromaDB 向量索引
│   ├── sessions/                 # Session 資料（JSON）
│   ├── feedback/                 # 回饋紀錄（JSON）
│   └── temp/                     # 音訊暫存
├── config/
│   └── default.yaml              # 預設設定
├── doc/                          # 文件體系（依 [[AI協作開發規範]]）
│   ├── specs/
│   ├── plans/
│   ├── history/
│   ├── manuals/
│   ├── reports/
│   ├── research/
│   └── archive/
├── tests/
├── requirements.txt
├── pyproject.toml
└── CLAUDE.md
```
