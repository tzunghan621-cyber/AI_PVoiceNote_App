---
title: "Android 高階手機可行性研究"
date: 2026-04-05
type: research
status: complete
author: Researcher (Claude)
tags:
  - android
  - mobile
  - feasibility
  - on-device-ai
  - architecture
---

# Android 高階手機可行性研究

> 調查日期：2026-04-05
> 目的：評估 [[system_overview|AI_PVoiceNote_App]] 現有技術棧移植至 Android 高階手機的可行性
> 相關規格：[[system_overview]] | [[data_schema]]

---

## 1. 研究摘要

### 一句話結論

**現有技術棧無法直接移植至 Android，但每個元件都有成熟的 Android 替代方案 — 而且 Gemma 4 E2B/E4B 內建原生音訊 ASR，有望用單一模型同時取代 Whisper + Summarizer。**

### 總覽

| 元件 | 現有方案 | Android 可行？ | 推薦替代方案 | 難度 |
|------|----------|:--------------:|-------------|:----:|
| 語音轉文字 | faster-whisper (CTranslate2) | ❌ | **Gemma 4 E4B 原生 ASR**（首選）/ whisper.cpp | 中 |
| 摘要推理 | Gemma 4 4B via Ollama | ❌ | Gemma 4 E4B via Google AI Edge SDK | 中 |
| Embedding | sentence-transformers (MiniLM) | ❌ | ONNX Runtime Mobile | 低 |
| 向量資料庫 | ChromaDB | ❌ | sqlite-vec / 原生 SQLite | 低 |
| UI 框架 | Flet (Flutter) | ✅ | Flet 原生支援 Android | 低 |

> **重大發現：** Gemma 4 E2B/E4B 是多模態模型，原生支援音訊輸入（ASR + 語音翻譯）。在 Android 端有機會用**一個模型搞定轉錄 + 摘要**，大幅簡化架構。

---

## 2. 各元件 Android 相容性分析

### 2.1 語音轉文字：faster-whisper → Gemma 4 E4B 原生 ASR / whisper.cpp

**現狀：CTranslate2 無 Android 支援。** CTranslate2 針對 x86 (Intel MKL/oneDNN) 和 CUDA 優化，無官方 ARM/Android build，也無社群維護的移植版本。

#### 重大發現：Gemma 4 E2B/E4B 內建原生音訊 ASR

根據 [Gemma 4 官方 Model Card](https://ai.google.dev/gemma/docs/core/model_card_4)，**Gemma 4 E2B 和 E4B 原生支援音訊輸入**：
- 語音轉文字（ASR）
- 語音翻譯（Speech-to-text translation）
- 最大支援 30 秒音訊片段

這意味著在 Android 端，**Gemma 4 E4B 一個模型可以同時負責 ASR + 摘要**，不需要額外的 Whisper 模型。這是架構上的重大簡化。

> ⚠️ **限制：30 秒上限。** 需要將音訊切成 ≤30 秒片段逐段送入，與現有 `transcribe_chunk_sec: 10` 的設計相容。但即時串流轉錄的延遲需要實測。

#### 替代方案比較

| 方案 | 離線 | 中英雙語 | 模型大小 | 手機效能 | 備註 |
|------|:----:|:-------:|---------|---------|------|
| **Gemma 4 E4B 原生 ASR** | ✅ | ✅ (140+ 語言) | 與摘要模型共用 | 待實測 | **一模型雙用**，架構最簡。但 ASR 品質需驗證 |
| **whisper.cpp** | ✅ | ✅ | small Q5 ~180MB | SD 8 Gen 2: ~3-4x 即時 | 社群最活躍，有 Android JNI 範例，品質有保證 |
| **Sherpa-ONNX** | ✅ | ✅ | 依模型 | 針對手機優化，支援串流 ASR | 有預建 Android AAR，串流能力強 |
| Google ML Kit | 部分 | ✅ | ~50MB/語言 | 極佳 | 封閉 API，客製化低 |
| Android SpeechRecognizer | 部分 | ✅ | OS 內建 | 原生 | 無時間戳 API，品質因廠商而異 |

#### 推薦

- **首選（激進方案）：Gemma 4 E4B 原生 ASR** — 一個模型搞定轉錄+摘要，大幅減少 RAM 和模型管理複雜度。但 ASR 品質和即時性需要 POC 驗證。
- **穩健方案：whisper.cpp**（small Q5 量化）— 社群活躍、有成熟 Android 範例、ASR 品質有保證
- **串流場景備選：Sherpa-ONNX** — 原生支援串流 ASR
- **降級方案：Whisper base（Q5 ~60MB）** — 中低階裝置使用

### 2.2 摘要推理：Ollama + Gemma 4 4B → Google AI Edge + Gemma 4 E4B

**現狀：Ollama 無 Android 支援。** Ollama 專為 Desktop 設計（macOS/Linux/Windows），社群有透過 Termux 運行的方案但不穩定、無 GPU 加速，不適合產品級使用。

#### Gemma 4 完整模型家族（來源：[官方 Model Card](https://ai.google.dev/gemma/docs/core/model_card_4)）

| 模型 | 架構 | 有效參數 | 總參數 | Context | 多模態 | 音訊 ASR | 適用場景 |
|------|------|---------|--------|---------|:------:|:-------:|---------|
| **Gemma 4 E2B** | Dense | 2.3B | 5.1B | 128K | ✅ | ✅ | 手機 / Edge（輕量） |
| **Gemma 4 E4B** | Dense | 4.5B | 8B | 128K | ✅ | ✅ | 手機 / Edge（品質優先） |
| **Gemma 4 26B A4B** | MoE | 3.8B 活躍 | 25.2B | 256K | ✅ | ❌ | 中高階裝置（MoE 效率） |
| **Gemma 4 31B** | Dense | 30.7B | 30.7B | 256K | ✅ | ❌ | Desktop / Server |

> **重要：E2B 和 E4B 是 Gemma 4 家族的成員**，不是獨立的 "Gemma 3n" 模型。它們共享 Gemma 4 的訓練和能力基線，包括 140+ 語言支援和多模態能力。

#### 推理引擎比較

| 方案 | 備註 |
|------|------|
| **Google AI Edge (MediaPipe LLM Inference)** | Google 官方 on-device SDK，Gemma 4 一等公民支援，GPU/NPU 加速。**最佳選項。** |
| **LiteRT-LM** | Google 新一代輕量推理引擎，官方支援 Gemma 4 |
| **llama.cpp** | 成熟穩定，支援 GGUF 量化，透過 NDK 編譯 Android 版。通用型方案。 |
| **MLC LLM** | Apache TVM 基底，Vulkan GPU 後端，效能好但生態較小。 |

#### Gemma 4 E4B 在手機上的可行性（推薦）

| 項目 | E4B | E2B |
|------|-----|-----|
| 有效參數 | 4.5B | 2.3B |
| 總參數（含 embedding） | 8B | 5.1B |
| 量化後模型大小（估） | ~4-5 GB | ~2.5-3 GB |
| 總 RAM 需求（估） | ~5-7 GB | ~3-5 GB |
| Context window | 128K tokens | 128K tokens |
| 多模態 | 文字 + 影像 + 音訊 + 影片 | 文字 + 影像 + 音訊 + 影片 |
| 原生 ASR | ✅（≤30 秒） | ✅（≤30 秒） |
| 16 GB 手機 | ✅ 舒適 | ✅ 輕鬆 |
| 12 GB 手機 | ⚠️ 勉強 | ✅ 可行 |

#### Gemma 4 26B A4B：值得關注的 MoE 方案

26B A4B 使用 MoE 架構，僅 3.8B 有效參數（128 專家中 8 個活躍）：
- **推理效率接近 4B 級別**，但品質接近更大模型
- **但總參數 25.2B → 量化後仍需 ~12-15 GB**，手機無法載入
- **更適合 Desktop 使用**（替代現有 Gemma 4 4B，品質更好）
- 無原生音訊支援

> **結論：Android 端選 E4B（或 E2B 降級），Desktop 端可考慮升級至 26B A4B。**

#### 電池與散熱

| 項目 | 估算 |
|------|------|
| 持續推理功耗 | 3-6W |
| 每小時電池消耗 | 15-25% |
| 散熱降頻 | 連續推理 5-15 分鐘後降速 30-50% |
| **緩解策略** | 批次處理（每 3-5 分鐘摘要一次而非連續推理）、空閒時散熱、使用 E2B 降低負載 |

> 本 App 的週期性摘要架構（見 [[system_overview#4.2 週期性摘要更新]]）天然適合行動端 — 推理是間歇性的，不會持續燒 GPU。

### 2.3 Embedding：sentence-transformers → ONNX Runtime Mobile

**現狀：Python sentence-transformers 無法在 Android 運行。** PyTorch 依賴太重。

#### 推薦方案

**ONNX Runtime Mobile + 匯出的 MiniLM-L12-v2 模型**

- 使用 `optimum-cli export onnx` 一鍵匯出 ONNX 格式
- ONNX Runtime Android AAR 包大小 ~5-15MB
- 推理速度：每句 ~50-150ms（現代手機）
- **嵌入向量與 Desktop 版完全相容** — 同一模型，只是推理引擎不同

### 2.4 向量資料庫：ChromaDB → sqlite-vec / 原生 SQLite

**現狀：ChromaDB 無法在 Android 運行。** 依賴 hnswlib C++ 擴充等原生套件，未針對 Android 建構。

#### 替代方案

| 方案 | 適用性 | 備註 |
|------|--------|------|
| **sqlite-vec** | ⭐ 最佳 | Alex Garcia 開發，純 SQLite 擴充，支援 KNN 查詢，Android 原生支援 |
| 原生 SQLite + cosine | 簡單可靠 | 小語料庫（<10K 向量）直接計算，零額外依賴 |
| LanceDB | 實驗性 | Rust 核心，行動端支援不成熟 |
| FAISS | 可行但重 | 需交叉編譯，二進位檔大 |

> 本 App 的知識庫規模（數百至數千詞條）很小，sqlite-vec 甚至原生 SQLite cosine 計算都綽綽有餘。

### 2.5 UI 框架：Flet ✅ 原生支援 Android

Flet 自 0.21+（2024 年初）起正式支援 Android，0.25+ 後基本功能穩定。

| 項目 | 說明 |
|------|------|
| 打包方式 | `flet build apk` / `flet build aab` |
| Python runtime | 透過 Kivy python-for-android (p4a) 交叉編譯 CPython |
| APK 大小 | ~60-100MB（含 Python runtime） |
| 已知限制 | 純 Python 套件沒問題，C 擴充套件需 p4a recipe；部分 Desktop 專用 API（視窗管理等）不可用 |
| 效能 | 比原生 Flutter 稍慢（Python↔Dart bridge 開銷），但足夠 |

> ⚠️ Flet UI 層本身可以跑，但底層 ML 元件（faster-whisper、ChromaDB 等 C 擴充）無法透過 p4a 直接帶上。需要改用 Android 原生 SDK（JNI/AAR）整合。

---

## 3. 硬體需求評估

### 3.1 目標規格

#### 方案 A：Gemma 4 E4B 統一模型（ASR + 摘要）

| 資源 | 需求估算 | 備註 |
|------|---------|------|
| RAM | 6-8 GB 可用（12 GB 總量起跳） | Gemma E4B ~5-7GB + Embedding ~200MB + App ~300MB |
| 儲存 | ~5-6 GB | E4B 模型 + App + 資料 |
| SoC | Snapdragon 8 Gen 2+ / Dimensity 9200+ | 需要強 CPU 核心 + GPU compute |

> 統一模型方案省去 Whisper 的 ~500MB RAM，但 E4B 本身比之前估算的略大（8B 總參數）。

#### 方案 B：whisper.cpp + Gemma 4 E4B（分離模型）

| 資源 | 需求估算 | 備註 |
|------|---------|------|
| RAM | 7-9 GB 可用（16 GB 總量起跳） | Whisper ~500MB + Gemma E4B ~5-7GB + Embedding ~200MB + App ~300MB |
| 儲存 | ~5.5-7 GB | Whisper small Q5 ~180MB + E4B + App + 資料 |
| SoC | Snapdragon 8 Gen 2+ / Dimensity 9200+ | 同上 |

> 雙模型方案 RAM 需求更高，但 ASR 品質有 Whisper 的成熟保證。

### 3.2 高階手機規格對照

| 手機 | SoC | RAM | 可行性 |
|------|-----|-----|--------|
| **Google Pixel 9 Pro** | Tensor G4 | 16 GB | ✅ 最佳（Google 晶片 + AI Edge 深度優化），方案 A/B 皆可 |
| **Samsung S25 Ultra** | Snapdragon 8 Elite | 12/16 GB | ✅ 16GB 方案 A/B 皆舒適；12GB 建議方案 A |
| **Samsung S24 Ultra** | Snapdragon 8 Gen 3 | 12 GB | ⚠️ 僅方案 A（統一模型）可行，或用 E2B 降級 |
| ⭐ **Samsung Z Fold6**（甲方持有） | Snapdragon 8 Gen 3 | 12 GB | ⚠️ 方案 A 勉強可行（E4B 需 6-8GB，系統佔 4-6GB）；**建議用 E2B 更穩**。大螢幕展開後適合儀表板三欄佈局 |
| ⭐ **Samsung S22 Ultra**（甲方持有） | Snapdragon 8 Gen 1 | 12 GB | ❌ **不建議。** Gen 1 CPU/GPU 效能偏弱，即使用 E2B 也會很吃力。可作為純 UI 端 + 雲端推理的備案 |
| **OnePlus 13** | Snapdragon 8 Elite | 12/16 GB | ✅ 16GB 版方案 A/B 皆可 |
| **Pixel 8 Pro** | Tensor G3 | 12 GB | ⚠️ 僅方案 A + E2B 可行 |

> 💡 **Google Pixel 系列有天然優勢**：Tensor 晶片對 Google AI Edge SDK + Gemma 有硬體級優化。

### 3.3 電池消耗估算（一小時會議）

| 場景 | 估算電池消耗 |
|------|------------|
| 方案 A：Gemma E4B 統一（ASR+摘要） | ~15-25% |
| 方案 B：whisper.cpp 轉錄 + Gemma E4B 摘要 | ~20-30% |
| RAG 校正 + Embedding | ~2-3% |
| **合計（一小時會議）** | **方案 A: ~18-28% / 方案 B: ~22-33%** |

> 4000-5000mAh 旗艦機可支撐約 3-4 小時會議。建議提供「省電模式」：降級模型 + 延長摘要週期。

---

## 4. 推薦 Android 技術棧

| 層 | Desktop（現有） | Android（推薦） |
|---|----------------|----------------|
| 語音轉文字 | faster-whisper (small) | Gemma 4 E4B 原生 ASR（首選）/ whisper.cpp（穩健） |
| 摘要推理 | Gemma 4 4B via Ollama | Gemma 4 E4B via Google AI Edge SDK |
| Embedding | sentence-transformers (MiniLM) | ONNX Runtime Mobile (同模型 ONNX 匯出) |
| 向量資料庫 | ChromaDB | sqlite-vec |
| UI 框架 | Flet (Desktop) | Flet (Android) 或原生 Kotlin/Flutter |
| 語言 | Python 3.11+ | Python (Flet) + Kotlin/C++ (ML 層) |

---

## 5. 架構影響：Desktop + Android 雙平台

### 5.1 可共用模組

| 模組 | 共用程度 | 說明 |
|------|---------|------|
| `models.py` | ✅ 完全共用 | 純 dataclass，無平台依賴 |
| `session_manager.py` | ✅ 完全共用 | 業務邏輯，無底層依賴 |
| `exporter.py` | ✅ 完全共用 | Markdown 產生，純字串操作 |
| `config_manager.py` | ✅ 完全共用 | YAML 讀寫 |
| `feedback_store.py` | ✅ 完全共用 | JSON 讀寫 |
| `stream_processor.py` | ⚠️ 大部分共用 | 管線控制邏輯共用，底層呼叫需抽象化 |
| UI 層 | ⚠️ 大部分共用 | Flet 跨平台，但需調整響應式佈局（手機必定單欄） |

### 5.2 需要平台抽象的模組

| 模組 | 需要做的事 |
|------|-----------|
| `transcriber.py` | 定義 `TranscriberBase` 介面，Desktop 用 faster-whisper、Android 方案 A 用 Gemma 4 E4B ASR、方案 B 用 whisper.cpp |
| `knowledge_base.py` | 定義 `VectorStoreBase` 介面，Desktop 用 ChromaDB、Android 用 sqlite-vec |
| `rag_corrector.py` | Embedding 呼叫需抽象化（Desktop: sentence-transformers、Android: ONNX Runtime） |
| `summarizer.py` | 定義 `LLMBase` 介面，Desktop 用 Ollama API、Android 用 AI Edge SDK |
| `audio_recorder.py` | 麥克風存取 API 不同，需平台特定實作 |

### 5.3 建議架構

```
app/core/
├── interfaces/              # 新增：平台抽象介面
│   ├── transcriber_base.py  # TranscriberBase
│   ├── llm_base.py          # LLMBase  
│   ├── embedder_base.py     # EmbedderBase
│   ├── vector_store_base.py # VectorStoreBase
│   └── audio_base.py        # AudioRecorderBase
├── desktop/                 # Desktop 實作
│   ├── whisper_transcriber.py
│   ├── ollama_llm.py
│   ├── st_embedder.py
│   ├── chroma_store.py
│   └── desktop_audio.py
├── android/                 # Android 實作
│   ├── whispercpp_transcriber.py
│   ├── aiedge_llm.py
│   ├── onnx_embedder.py
│   ├── sqlite_vec_store.py
│   └── android_audio.py
└── ... (共用業務邏輯不變)
```

> 這種 Strategy Pattern 讓 `stream_processor.py` 等核心管線邏輯完全不用改，只在啟動時注入不同平台的實作。

---

## 6. 風險與挑戰

| 風險 | 嚴重度 | 緩解方式 |
|------|:------:|---------|
| Gemma 4 E4B（4.5B 有效參數）摘要/ASR 品質未經實測 | 高 | 需 POC 驗證中文 ASR 與摘要品質；E4B 是 Gemma 4 家族、140+ 語言，理論上有保障 |
| Flet Android 打包含 C 擴充困難 | 高 | ML 層用 Android 原生 SDK（JNI），不走 p4a |
| whisper.cpp small 即時轉錄在中低階手機太慢 | 中 | 提供 base model 降級選項 |
| 手機散熱影響長會議體驗 | 中 | 省電模式 + 彈性摘要週期 |
| 雙平台維護成本增加 | 中 | 先穩定 Desktop 版本，Android 作為第二階段 |
| APK 體積大（模型 + Python runtime） | 低 | 模型首次下載、增量更新 |

---

## 7. 結論與建議

### 可行性判定

**技術上可行，但不是直接移植，而是「共用架構 + 替換引擎」。** 約 60% 的程式碼可跨平台共用，40% 需要 Android 特定實作。

### 開發建議

1. **先不急著做 Android 版。** Desktop 版尚在開發中，應先完成並穩定。
2. **現階段可以預做的事：** 在 Desktop 開發過程中，將 transcriber / summarizer / embedder / vector store 設計為可插拔介面。這不增加太多工作量，但未來移植時會省很多力。
3. **Android 版開發時程估計：** 若架構已預留抽象層，Android 版主要工作是實作各 platform-specific 模組 + 測試調優。
4. **優先驗證兩件事：**
   - Gemma 4 E4B 的**原生 ASR 中文品質** — 能否取代 Whisper？
   - Gemma 4 E4B 的**中文摘要品質** — 4.5B 有效參數是否足夠？
5. **Desktop 端也可受益：** Gemma 4 26B A4B（MoE，3.8B 活躍參數）在 Desktop 上可能比現有 4B dense 品質更好，值得評估。

### 技術棧對照總結

```
Desktop:  faster-whisper ──→ Ollama/Gemma4 4B ─→ sentence-transformers ─→ ChromaDB ─→ Flet
              │                    │                      │                  │           │
Android   Gemma 4 E4B ────────────┘              ONNX Runtime Mobile  ─→ sqlite-vec ─→ Flet
(方案A)   (ASR+摘要統一)        via AI Edge SDK
                                    
Android   whisper.cpp ──→ Gemma 4 E4B ──→ ONNX Runtime Mobile ──→ sqlite-vec ──→ Flet
(方案B)   (ASR 專用)    (摘要專用)         via AI Edge SDK
```

> **方案 A（統一模型）** 是 Gemma 4 多模態能力帶來的獨特機會 — 一個模型同時處理音訊轉錄與文字摘要，RAM 佔用更低、架構更簡潔。需 POC 驗證 ASR 品質。

---

> 本報告由 Researcher (Claude) 產出，供甲方決策參考。
> 如需進一步深入特定元件的 POC 測試，請指示。
