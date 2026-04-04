---
title: "競品研究 — 語音會議摘要工具"
date: 2026-04-04
type: research
status: complete
author: Researcher (Claude)
tags:
  - competitive-analysis
  - voice-transcription
  - meeting-summary
  - market-research
---

# 競品研究 — 語音會議摘要工具

> 調查日期：2026-04-04
> 目的：為 [[system_overview|AI_PVoiceNote_App]] 的差異化定位與 [[ui_spec|工作區設計]] 提供決策依據

---

## 1. 研究摘要

### 市場現況

2026 年語音會議摘要工具市場已高度成熟，主要分為三大類：

| 類型 | 代表產品 | 特點 |
|------|----------|------|
| **雲端 SaaS** | Otter.ai、Fireflies.ai、tl;dv、Notta | 功能豐富、依賴雲端、訂閱制 |
| **混合式** | Granola、Krisp、Jamie | 本地錄音 + 雲端 AI 處理 |
| **本地優先** | Meetily、Talat | 全程本地運算、隱私優先 |

### 我們的差異化優勢

與現有競品比較，[[system_overview|AI_PVoiceNote_App]] 的獨特組合為：

1. **RAG 知識庫校正**：市面上無競品具備 RAG + 個人知識庫的專有名詞校正機制（僅有簡單的 Custom Vocabulary 字典）
2. **三區塊並排工作區**：多數競品採分頁或上下捲動，缺乏逐字稿/重點/Action Items 並排對照
3. **回饋驅動的持續優化循環**：校正品質的量化追蹤與詞條效能分析為獨有功能

---

## 2. 主流商業產品

### 2.1 Otter.ai

**定位：** 市場龍頭，AI 會議助理與即時轉錄平台

**核心功能：**
- 即時語音轉錄（支援 Zoom/Meet/Teams 自動加入）
- OtterPilot 自動化流程：加入會議 → 錄音 → 轉錄 → 摘要 → Action Items
- 整合 Slack、Zoom、Salesforce、Google Drive 等

**工作區/介面設計：**
- 單頁式佈局：逐字稿為主體，摘要與 Action Items 在側邊面板或頂部區域
- 非三欄並排，而是「逐字稿佔主體 + 摘要/Action Items 折疊顯示」

**編輯能力：**
- 逐字稿可直接點擊編輯文字
- Action Items 可點擊進入編輯模式，修改/刪除/新增
- 摘要可加註評論，但直接編輯有限

**自訂詞彙功能：**
- 支援 Custom Vocabulary（純字典比對，非 RAG）
- Free: 5 詞、Pro: 各 100 詞（姓名 + 其他）、Business: 各 800 詞
- 僅支援名稱與詞彙兩種類型，無語境上下文

**本地 vs 雲端：** 全雲端處理

**定價：**
- Free：300 分鐘/月（30 分鐘/次）
- Pro：$16.99/月（月付）/ $8.33/月（年付）、1,200 分鐘/月
- Business：$19.99/用戶/月
- Enterprise：客製定價

**優點：** 市場成熟度高、整合豐富、即時轉錄穩定
**缺點：** 全雲端處理（隱私風險）、Custom Vocabulary 簡陋（無語境校正）、工作區非並排佈局

---

### 2.2 Fireflies.ai

**定位：** AI 會議筆記 + 對話智慧分析平台

**核心功能：**
- 自動加入視訊會議錄音、轉錄、摘要
- AskFred AI 助手：可對轉錄內容提問
- 「Talk to Fireflies」整合 Perplexity AI（會議中即時搜尋）
- 自動偵測 Action Items 並推送至 Jira/Asana/Trello

**工作區/介面設計：**
- 分頁式佈局：逐字稿、AI Super Summary、Action Items 各為獨立分頁
- 會議即時產生重點筆記（bullet-point notes）

**Action Items 結構：**
- 包含負責人指派（如「John to email the API documentation by Friday」）
- 可自動同步至專案管理工具
- 可編輯與調整

**編輯能力：**
- 逐字稿可編輯
- AI 摘要與 Action Items 可調整與修正

**自訂詞彙功能：**
- Settings > Custom Vocabulary 可新增專有名詞
- 限 Pro/Business 方案使用
- 同為字典式比對，無語境 RAG

**本地 vs 雲端：** 全雲端處理

**定價：**
- Free：800 分鐘
- Pro：$18/月（月付）/ $10/月（年付）
- Business：$29/月（月付）/ $19/月（年付）
- Enterprise：$39/月

**優點：** AI 功能豐富（AskFred、Perplexity 整合）、Action Items 結構化且可推送至 PM 工具
**缺點：** AI 功能消耗 credit（重度用戶花費 2-3 倍基本價）、雲端處理、分頁式佈局不利對照

---

### 2.3 tl;dv

**定位：** 會議錄影 + AI 筆記平台，主打「太長不看」價值

**核心功能：**
- 會議錄影 + 轉錄（30+ 語言）
- AI 摘要：含討論重點、Action Items、決議、下一步驟
- 可自訂摘要模板
- 自動標記重要時刻

**工作區/介面設計：**
- 影片播放器 + 逐字稿 + AI 摘要，影片為主體
- 時間戳標記可快速跳轉
- Team 方案提供共享 Workspace（共享會議 + 標籤管理）

**Action Items 結構：**
- 包含 Action Items、截止日期、重要資訊
- AI Report 功能可跨多場會議彙整 Action Items

**編輯能力：**
- 逐字稿可編輯修正
- 自動高亮重點、支援標籤與時間戳標記

**自訂詞彙功能：**
- **尚未推出**（2026 年仍為即將推出狀態）
- 被多篇評測指為最大弱點，技術/醫療/法律領域用戶需大量手動修正

**本地 vs 雲端：** 全雲端處理

**定價：**
- Free：無限錄影/轉錄，僅 10 次 AI 摘要（終身）
- Pro：無限 AI 筆記（具體價格依方案）
- Business：$59/用戶/月（年付）

**優點：** 影片 + 逐字稿整合、跨會議 AI Report、摘要模板自訂
**缺點：** 無 Custom Vocabulary（最大弱點）、Free 方案 AI 功能極度受限、雲端處理

---

### 2.4 Krisp

**定位：** 噪音消除 + AI 會議助理（混合式）

**核心功能：**
- 業界領先的 AI 噪音消除（消除背景噪音、回音、人聲）
- 即時口音轉換（Real-time Accent Conversion）
- 轉錄 + 摘要 + Action Items（16+ 語言，96% 準確率）
- **無需 Bot 加入會議**：直接在音訊層級擷取

**工作區/介面設計：**
- 轉錄筆記 + 摘要 + Action Items 在會議結束後呈現
- 較為簡潔的介面，專注於筆記產出

**Action Items 結構：**
- 自動識別與摘要中一同呈現
- 可透過 Zapier 連結 Notion/Jira

**編輯能力：**
- 轉錄可編輯
- 摘要與筆記可調整

**自訂詞彙功能：**
- 無公開的 Custom Vocabulary 功能

**本地 vs 雲端：** 混合式（噪音消除本地處理，轉錄與 AI 功能雲端處理）

**定價：**
- Free：60 分鐘/天噪音消除、無限轉錄/錄音、2 則 AI 筆記/天
- Core：$16/月（月付）/ $8/月（年付）
- Advanced：$30/月（月付）/ $15/月（年付）

**優點：** 噪音消除獨步業界、無 Bot 入侵會議、口音轉換
**缺點：** AI 摘要功能相對基本、無 Custom Vocabulary、核心 AI 仍雲端處理

---

### 2.5 Notta

**定位：** 多語言 AI 會議轉錄平台

**核心功能：**
- 58 語言即時轉錄與翻譯
- 98.86% 準確率（官方宣稱）
- AI 摘要含決議、Action Items、客戶洞察
- 匯出至 Google Drive、Notion、Slack、Salesforce

**工作區/介面設計：**
- 轉錄 + 摘要上下排列
- 可搜尋與篩選歷史轉錄

**Action Items 結構：**
- 與摘要一同產生
- 結構相對簡單

**編輯能力：**
- 轉錄可編輯
- 摘要可調整

**自訂詞彙功能：**
- 無明確的 Custom Vocabulary 功能

**本地 vs 雲端：** 全雲端處理（SOC2 Type II + ISO 27001）

**定價：**
- Free：120-200 分鐘/月
- Pro：~$8.17/月（年付）、1,800 分鐘/月
- Business：無限分鐘

**優點：** 58 語言支援最廣、準確率高、定價親民
**缺點：** 功能相對基本、雲端處理、Action Items 結構簡單

---

### 2.6 Granola

**定位：** AI 筆記本（2026 年估值 $1.5B 獨角獸）

**核心功能：**
- 會議中可輸入關鍵字筆記，AI 自動擴展為結構化摘要
- 使用者筆記（黑字）vs AI 補充（灰字）明確區分，灰字可點擊連結到轉錄原文
- 自然語言查詢歷史會議（GPT-4o + Claude 驅動）
- 支援 Zoom/Meet/Teams/Slack Huddles/WebEx

**工作區/介面設計（Spaces）：**
- 新推出 **Spaces** 功能：團隊工作區 + 資料夾結構
- 精細的存取權限控制
- 可針對特定 Space/資料夾查詢筆記

**Action Items 結構：**
- AI 從會議內容自動擷取
- 整合 CRM 與專案管理工具

**編輯能力：**
- 核心設計理念：使用者與 AI 共同編輯
- 使用者打的筆記保留，AI 在旁補充，形成協作式編輯體驗

**自訂詞彙功能：**
- 無專門的 Custom Vocabulary 功能

**本地 vs 雲端：** 混合式（本地錄音，雲端 AI 處理）

**定價：**
- Basic：免費（有限會議歷史）
- Business：$14/用戶/月
- Enterprise：$35/用戶/月（含 SSO、可退出模型訓練）

**優點：** 獨特的人機協作編輯體驗、Spaces 團隊架構、$1.5B 獨角獸代表市場認可
**缺點：** AI 處理仍需雲端、無 Custom Vocabulary、個人使用者定價偏低但功能受限

---

## 3. 開源專案

### 3.1 Meetily（最具參考價值）

**GitHub：** Zackriya-Solutions/meetily（MIT License）

**定位：** 隱私優先的開源 AI 會議助理，Otter.ai / Granola 的開源替代品

**技術棧：**
- 轉錄：Whisper.cpp（tiny ~ large-v3，支援 GPU 加速）+ NVIDIA Parakeet（4x 快速）
- 摘要：Ollama（Gemma3n / LLaMA / Mistral）或 Cloud API（Claude / Groq）
- Speaker Diarization 說話人辨識
- 後端 Rust 建構

**核心功能：**
- 即時音訊擷取與轉錄
- AI 摘要（自動識別重點、Action Items、決議）
- 音訊/影片匯入（10 種格式）
- 6 種內建摘要模板（Pro 版可自訂）
- 搜尋/取代（跨轉錄與摘要）
- 匯出 PDF/DOCX/Markdown

**工作區/介面設計：**
- Desktop App（Windows + macOS）
- 轉錄 + 摘要呈現（具體佈局為上下排列式）
- 無三欄並排設計

**自訂詞彙：** 無 RAG 校正機制

**優點：** 完全開源免費、100% 本地處理、技術棧與我們高度相似（Whisper + Ollama）
**缺點：** 無 RAG 知識庫校正、無回饋優化循環、介面較基本、無三區塊工作區

> **與我們的關鍵差異：** Meetily 是最接近的競品，但缺少 RAG 校正、回饋驅動優化、三區塊並排工作區三大核心功能。

---

### 3.2 其他開源專案

| 專案 | 特點 | 限制 |
|------|------|------|
| **Transcript-Seeker** (Meeting-BaaS) | 瀏覽器端轉錄檢視器，可 AI 對話 | Web-based，無本地 LLM |
| **AI-Powered-Meeting-Summarizer** | Gradio + Whisper + Ollama | 簡單 demo，非產品級 |
| **meeting-transcriber** (jfcostello) | Python, 支援本地或雲端 LLM | CLI 工具，無 UI |

---

## 4. 本地端/隱私優先方案

### 4.1 Talat（2026 年 3 月新品）

**平台：** macOS（M 系列晶片專用）

**核心功能：**
- Mac Neural Engine 即時轉錄
- 本地 LLM 產生摘要（內建 Qwen3-4B-4bit，或可接 Ollama/OpenAI/Anthropic API）
- 即時 Speaker Diarization（可手動調整說話人）
- 自動儲存至 Obsidian / iCloud / Dropbox
- 支援 HTTP Webhook 推送（Markdown/JSON）

**工作區/介面設計：**
- Mac-native 介面
- 即時轉錄 + 會議結束後產生摘要（重點 + 決議 + Action Items）

**自訂詞彙：** 無

**定價：** Pre-release $49（正式版 $99），一次性買斷

**優點：** 完全本地處理、Mac 整合優秀、Obsidian 匯出、一次性買斷
**缺點：** 僅 macOS、無 Custom Vocabulary/RAG、無回饋循環、無三區塊工作區

> **與我們的關鍵差異：** Talat 同為本地優先 + Obsidian 整合，但缺少 RAG 校正與三區塊編輯工作區。且僅限 macOS。

### 4.2 Jamie

**定位：** GDPR 合規的本地錄音 + 雲端轉錄方案

- 本地錄音，雲端轉錄後刪除音訊
- EU 託管（法蘭克福）、AES 加密
- 嚴格意義上並非完全本地處理

---

## 5. 重點功能對比矩陣

### 5.1 基礎功能

| 功能 | Otter | Fireflies | tl;dv | Krisp | Notta | Granola | Meetily | Talat | **我們** |
|------|-------|-----------|-------|-------|-------|---------|---------|-------|----------|
| 即時轉錄 | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| AI 摘要 | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Action Items | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| 100% 本地處理 | :x: | :x: | :x: | :x: | :x: | :x: | :white_check_mark: | :white_check_mark: | **:white_check_mark:** |
| 自訂詞彙 | :white_check_mark: (字典) | :white_check_mark: (字典) | :x: (規劃中) | :x: | :x: | :x: | :x: | :x: | **:white_check_mark: (RAG)** |
| RAG 知識庫校正 | :x: | :x: | :x: | :x: | :x: | :x: | :x: | :x: | **:white_check_mark:** |
| 回饋驅動優化 | :x: | :x: | :x: | :x: | :x: | :x: | :x: | :x: | **:white_check_mark:** |

### 5.2 工作區佈局比較

| 產品 | 佈局方式 | 逐字稿/摘要/Action Items 關係 |
|------|----------|------------------------------|
| **Otter.ai** | 單頁：逐字稿為主，摘要/AI 側邊面板 | 摘要折疊於頂部或側邊 |
| **Fireflies.ai** | 分頁式：逐字稿、Summary、Action Items 各一頁 | 需切換分頁，無法同時對照 |
| **tl;dv** | 影片 + 逐字稿 + 摘要上下排列 | 影片為主體，文字輔助 |
| **Krisp** | 簡潔筆記式 | 摘要 + Action Items 合併呈現 |
| **Notta** | 上下排列：轉錄在上，摘要在下 | 需捲動切換 |
| **Granola** | 筆記本式：使用者筆記 + AI 補充混排 | 協作式混合，非結構分離 |
| **Meetily** | 上下排列：轉錄 + 摘要 | 基本佈局 |
| **Talat** | 即時轉錄 + 後製摘要 | 時序呈現 |
| **我們** | **三欄並排：逐字稿 / 會議重點 / Action Items** | **三區塊可同時對照、各自可編輯** |

> **洞察：** 市面上無產品採用三欄並排佈局。這是我們的介面差異化，但需驗證在 1024px 最小寬度下的可用性。

### 5.3 Action Items 結構比較

| 產品 | 負責人 | 期限 | 優先級 | 狀態追蹤 | 回溯原文 | 可編輯 |
|------|--------|------|--------|----------|----------|--------|
| **Otter.ai** | :white_check_mark: (AI 推斷) | :x: | :x: | :x: | :x: | :white_check_mark: |
| **Fireflies.ai** | :white_check_mark: (AI 推斷) | :white_check_mark: (AI 推斷) | :x: | :white_check_mark: (Jira 同步) | :x: | :white_check_mark: |
| **tl;dv** | :white_check_mark: | :white_check_mark: | :x: | :x: | :white_check_mark: (時間戳) | :white_check_mark: |
| **Granola** | :white_check_mark: | :x: | :x: | :x: | :white_check_mark: (灰字連結) | :white_check_mark: |
| **我們** | **:white_check_mark:** | **:white_check_mark:** | **:white_check_mark:** | **:white_check_mark:** | **:white_check_mark: (segment 索引)** | **:white_check_mark:** |

> **洞察：** 我們的 [[data_schema#4. 摘要結果|ActionItem]] 結構是最完整的（含 owner / deadline / priority / status / source_segment / note）。Fireflies 最接近但缺少優先級與備註。

### 5.4 自訂詞彙/專有名詞校正比較

| 產品 | 機制 | 上限 | 語境感知 | 效能追蹤 |
|------|------|------|----------|----------|
| **Otter.ai** | 字典比對（姓名 + 詞彙兩類） | Free: 5 / Pro: 200 / Biz: 1600 | :x: | :x: |
| **Fireflies.ai** | 字典比對 | Pro/Business 專用 | :x: | :x: |
| **tl;dv** | 尚未推出 | — | — | — |
| **其他競品** | 均無 | — | — | — |
| **我們** | **RAG 向量相似度 + 語境上下文** | **無硬性上限** | **:white_check_mark: (context 欄位)** | **:white_check_mark: (hit/success/fail 統計)** |

> **洞察：** 這是我們最大的技術差異化。競品的 Custom Vocabulary 僅為簡單字典，我們的 RAG 校正具備：
> - 向量相似度匹配（不限於精確比對）
> - 語境上下文輔助判斷（`context` 欄位）
> - 多別名支援（`aliases` 欄位涵蓋各種誤聽形式）
> - 校正效能追蹤與回饋驅動優化（[[data_schema#6. 回饋紀錄（Feedback）]]）

---

## 6. 定價模式總覽

| 產品 | 模式 | 免費方案 | 付費起價 | 備註 |
|------|------|----------|----------|------|
| Otter.ai | 訂閱制 | 300 分鐘/月 | $8.33/月 | 功能分級明顯 |
| Fireflies.ai | 訂閱制 + Credit | 800 分鐘 | $10/月 | AI 功能額外消耗 credit |
| tl;dv | 訂閱制 | 無限錄影，10 次 AI 摘要 | ~$18/月 | Free 方案 AI 極度受限 |
| Krisp | 訂閱制 | 60 分鐘/天噪音消除 | $8/月 | 噪音消除為核心賣點 |
| Notta | 訂閱制 | 120-200 分鐘/月 | $8.17/月 | 多語言為賣點 |
| Granola | 訂閱制 | 有限歷史 | $14/月 | 2026 估值 $1.5B |
| Meetily | 開源免費 | 完整功能 | $0 | Community Edition 永久免費 |
| Talat | 一次性買斷 | 10 小時試用 | $49 (pre-release) | 僅 macOS |
| **我們** | **免費（本地）** | **完整功能** | **$0** | **自建基礎設施成本** |

---

## 7. 設計啟發與建議

### 7.1 工作區設計建議

1. **三欄並排確認可行**：市面無競品採此佈局，是差異化優勢。但需注意：
   - Granola 的「使用者筆記 + AI 補充」混排模式值得參考作為會議重點區的編輯體驗
   - Fireflies 的分頁式是反面教材 — 無法同時對照嚴重影響審閱效率
   - 建議三欄寬度可拖曳調整，且在窄視窗時自動折疊為分頁

2. **逐字稿區參考 Otter**：
   - 時間戳可點擊（未來若支援音訊回放）
   - 校正處高亮標記（我們已有此設計，見 [[ui_spec#2.4 工作區]]）

3. **會議重點區參考 Granola**：
   - AI 產出 vs 使用者編輯可用不同顏色/樣式區分
   - 決議事項獨立呈現（不混在摘要文字中）

### 7.2 Action Items 設計建議

1. **我們的 [[data_schema#4. 摘要結果|ActionItem]] 結構已是業界最完整的**
2. 參考 Fireflies 的 PM 工具同步概念 — 未來可匯出為 Obsidian Tasks 格式
3. 優先級視覺化：建議用顏色 Tag（紅/橙/灰）而非純文字

### 7.3 編輯互動建議

1. **逐字稿區**：僅提供校正回饋（正確/錯誤/遺漏），不開放全文編輯（保持資料完整性）
2. **會議重點區**：全文可編輯（如 [[ui_spec#2.4 工作區]] 所設計），參考 Granola 的 contenteditable 體驗
3. **Action Items 區**：表單式編輯（各欄位獨立修改），參考 Otter 的 inline editing

### 7.4 RAG 知識庫 — 獨特競爭優勢

競品 Custom Vocabulary 的共同弱點：
- 僅支援精確字串比對
- 無語境判斷能力
- 無效能追蹤
- 無使用者回饋循環

**建議強化方向：**
- 在 [[ui_spec#2.4 工作區]] 的逐字稿區，校正處可「一鍵」新增遺漏詞條（降低回饋門檻）
- 回饋統計頁（[[ui_spec#4. 回饋統計頁]]）的「高頻遺漏回報」功能是獨有價值，持續強化

---

## 8. 風險與注意事項

1. **本地運算效能**：Meetily 用 Rust + Whisper.cpp 達到 4x 加速，我們用 Python + faster-whisper，需確保在 [[system_overview|Surface Pro 9 (CPU only)]] 上的效能可接受
2. **Granola 的崛起**：$1.5B 估值代表「筆記 + AI」模式獲得市場認可，但其人機協作編輯概念與我們不同（我們是 AI 全自動 + 人工審閱，Granola 是人工筆記 + AI 補充）
3. **Talat 的 Obsidian 整合**：Talat 已支援自動匯出至 Obsidian，我們也連結 Obsidian 知識庫，但方向不同（我們是從 Obsidian 讀取建庫，Talat 是輸出到 Obsidian）
4. **tl;dv 的 Custom Vocabulary 缺失**：被廣泛批評，驗證了此功能的市場需求

---

## 9. 結論

AI_PVoiceNote_App 在以下三點形成獨特定位，目前市面上無直接競品覆蓋此組合：

| 差異化維度 | 最接近競品 | 我們的優勢 |
|-----------|-----------|-----------|
| **RAG 知識庫校正** | Otter.ai（簡單字典） | 向量相似度 + 語境 + 別名 + 效能追蹤 |
| **三區塊並排工作區** | 無（均為分頁或上下排列） | 逐字稿/重點/Action Items 同時對照 |
| **回饋驅動優化循環** | 無 | 校正品質量化 + 詞條效能分析 + 自動建議 |

建議 Director 優先確認 [[ui_spec#2.4 工作區]] 的三欄佈局細部互動設計，這是使用者體驗的核心差異化。

---

> 本報告由 Researcher Agent 產出，供 Director 決策參考。
> 相關 Specs：[[system_overview]] | [[data_schema]] | [[ui_spec]]
