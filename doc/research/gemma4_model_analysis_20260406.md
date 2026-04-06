---
title: "Gemma 4 全系列模型能力調查 + 社群實測"
date: 2026-04-06
type: research
status: complete
author: Researcher (Claude)
tags:
  - gemma-4
  - model-analysis
  - benchmark
  - community-review
  - hardware-requirements
---

# Gemma 4 全系列模型能力調查 + 社群實測

> 調查日期：2026-04-06
> 目的：為 [[system_overview|AI_PVoiceNote_App]] 的模型選型提供數據化決策依據
> 硬體基準：Surface Pro 9（i7-1255U / 16GB RAM / CPU only）

---

## 1. 模型總覽

Gemma 4 於 2026-04-02 發布，Apache 2.0 授權（無商用限制，較 Gemma 3 的 "Gemma Open" 授權更開放）。

| 模型 | 有效參數 | 總參數 | 架構 | Context | 多模態 | 音訊 ASR |
|------|----------|--------|------|---------|--------|----------|
| **E2B** | 2.3B | 5.1B | Dense + PLE | 128K | 文字/圖像/影片 | :white_check_mark: 原生支援 |
| **E4B** | 4.5B | 8.1B | Dense + PLE | 128K | 文字/圖像/影片 | :white_check_mark: 原生支援 |
| **26B-A4B** | 3.8B active | 26B total | MoE | 256K | 文字/圖像/影片 | :x: |
| **31B** | 30.7B | 30.7B | Dense | 256K | 文字/圖像/影片 | :x: |

> **PLE**（Per-Layer Embeddings）：E2B/E4B 採用的技術，讓小模型具備接近大模型的表達深度，同時維持低記憶體佔用。
> **MoE**（Mixture of Experts）：26B 的 26B 總參數中，推理時只啟動 3.8B，大幅降低延遲。

**來源：** [Google Blog — Gemma 4](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/) | [Gemma 4 Model Card](https://ai.google.dev/gemma/docs/core/model_card_4)

---

## 2. 官方 Benchmark 成績

### 2.1 文字推理與知識

| Benchmark | E2B | E4B | 26B-A4B | 31B | 說明 |
|-----------|-----|-----|---------|-----|------|
| **MMLU Pro** | 60.0% | 69.4% | 82.6% | 85.2% | 知識 + 推理 |
| **AIME 2026** | 37.5% | 42.5% | 88.3% | 89.2% | 競賽數學 |
| **GPQA Diamond** | 43.4% | 58.6% | 82.3% | 84.3% | 科學知識 |
| **BigBench Extra Hard** | 21.9% | 33.1% | 64.8% | 74.4% | 困難推理 |
| **MMMLU** | 67.4% | 76.6% | 86.3% | 88.4% | 多語言知識 |

### 2.2 程式碼

| Benchmark | E2B | E4B | 26B-A4B | 31B |
|-----------|-----|-----|---------|-----|
| **LiveCodeBench v6** | 44.0% | 52.0% | 77.1% | 80.0% |
| **Codeforces ELO** | 633 | 940 | 1718 | 2150 |

### 2.3 多模態視覺

| Benchmark | E2B | E4B | 26B-A4B | 31B |
|-----------|-----|-----|---------|-----|
| **MMMU Pro** | 44.2% | 52.6% | 73.8% | 76.9% |
| **MATH-Vision** | 52.4% | 59.5% | 82.4% | 85.6% |
| **OmniDocBench** | 0.290 | 0.181 | 0.149 | 0.131 |

### 2.4 音訊 ASR（僅 E2B / E4B）

| Benchmark | E2B | E4B | 說明 |
|-----------|-----|-----|------|
| **CoVoST** | 33.47 | 35.54 | 語音翻譯（BLEU 分） |
| **FLEURS** | 0.09 | 0.08 | ASR 錯誤率（WER，越低越好） |

### 2.5 Agentic（工具使用 / 自主代理）

| Benchmark | E2B | E4B | 26B-A4B | 31B |
|-----------|-----|-----|---------|-----|
| **Tau2** | 24.5% | 42.2% | 68.2% | 76.9% |

### 2.6 長上下文

| Benchmark | E2B | E4B | 26B-A4B | 31B |
|-----------|-----|-----|---------|-----|
| **MRCR v2 8-needle** | 19.1% | 25.4% | 44.1% | 66.4% |

### 2.7 Arena 排名

| 模型 | Arena ELO 排名 |
|------|---------------|
| 31B | #3 開源模型 |
| 26B-A4B | #6 開源模型（ELO 1441） |

**來源：** [Gemma 4 Model Card](https://ai.google.dev/gemma/docs/core/model_card_4)

---

## 3. 與 Gemma 3 的比較

### 3.1 跨代升級幅度

| Benchmark | Gemma 3 27B | Gemma 4 26B-A4B | Gemma 4 31B | 升級幅度 |
|-----------|-------------|-----------------|-------------|----------|
| **AIME** | 20.8% | 88.3% | 89.2% | **+68.4%** (最大躍進) |
| **GPQA Diamond** | ~45% | 82.3% | 84.3% | **近乎翻倍** |
| **BigBench Extra Hard** | 19% | 64.8% | 74.4% | **+55%** |
| **LiveCodeBench** | — | 77.1% | 80.0% | 顯著提升 |

> **結論：升級非常值得。** Gemma 4 在數學推理（AIME +68%）、科學知識（GPQA 翻倍）、程式碼（Codeforces ELO 大幅提升）方面的進步是跨代級別的。

### 3.2 小模型比較

E4B（4.5B 有效參數）在多數 benchmark 上**超越 Gemma 3 27B（無 thinking 模式）**，這意味著 E4B 以 ~1/6 的參數量達到甚至超過上一代大模型的水準。

### 3.3 架構改進

| 面向 | Gemma 3 | Gemma 4 |
|------|---------|---------|
| 授權 | Gemma Open（有限制） | Apache 2.0（完全開放） |
| Context | 128K | 128K (edge) / 256K (large) |
| 音訊 ASR | 無（需外部工具） | E2B/E4B 原生支援 |
| Function Calling | 有限 | 原生支援 + 結構化 JSON |
| 幻覺抑制 | 一般 | logit soft-capping + sliding window attention |
| 音訊編碼器 | 681M 參數（Gemma 3n） | 305M 參數（壓縮 55%） |

**來源：** [Latent Space — Gemma 4 dramatically better than Gemma 3](https://www.latent.space/p/ainews-gemma-4-the-best-small-multimodal) | [HuggingFace Blog — Gemma 4](https://huggingface.co/blog/gemma4)

---

## 4. 硬體需求與推理速度

### 4.1 Ollama 模型檔案大小

| 模型 | Q4_K_M | Q8_0 | BF16 |
|------|--------|------|------|
| **E2B** | 7.2 GB | 8.1 GB | 10 GB |
| **E4B** | 9.6 GB | 12 GB | 16 GB |
| **26B-A4B** | 18 GB | 28 GB | — |
| **31B** | 20 GB | 34 GB | 63 GB |

**來源：** [Ollama — gemma4 tags](https://ollama.com/library/gemma4/tags)

### 4.2 運行時記憶體需求（含 KV Cache）

| 模型 @ Q4 | 模型載入 | + 4K context | + 8K context | + 128K context |
|-----------|----------|-------------|-------------|----------------|
| **E2B** | ~2 GB | ~3 GB | ~4 GB | — |
| **E4B** | ~5 GB | ~6 GB | ~7 GB | — |
| **26B-A4B** | ~18 GB | ~18 GB | ~19 GB | ~23 GB |
| **31B** | ~20 GB | ~21 GB | ~22 GB | ~40 GB |

**來源：** [Avenchat — Gemma 4 Hardware Requirements](https://avenchat.com/blog/gemma-4-hardware-requirements)

> **KV Cache 問題：** Gemma 4 的 KV Cache 佔用顯著高於同級競品。31B 在 256K context 下，僅 KV Cache 就需 ~22GB（模型權重之外）。llama.cpp 最新更新已優化記憶體約 40%，但 Ollama 可能尚未整合。
> **來源：** [n1n.ai — Gemma 4 KV Cache Fix](https://explore.n1n.ai/blog/gemma-4-local-inference-llama-cpp-kv-cache-fix-npu-benchmarks-2026-04-05)

### 4.3 CPU 推理速度

| 環境 | 模型 | 量化 | 速度 | 來源 |
|------|------|------|------|------|
| **CPU only（通用）** | E2B/E4B | Q4 | **~5-10 tok/s** | [Unsloth Docs](https://unsloth.ai/docs/models/gemma-4) |
| Mac Mini M4 24GB | E4B | Q4 | ~18 tok/s | [Medium — E4B benchmark](https://medium.com/@rviragh/can-googles-gemma4-e4b-10-gb-benchmark-itself-06b79218a071) |
| Laptop + Ollama | E4B | Q4 | ~25 tok/s（think=false） | [DEV.to — Gemma 4 on laptop](https://dev.to/david_shawn_e308bed98c45b/i-tested-gemma-4-on-my-laptop-and-turned-it-into-a-free-intelligence-layer-for-my-ai-apps-8dh) |
| 5060 Ti 16GB | 26B-A4B | Q4 | **11 tok/s**（問題回報） | [Community report](https://dev.to/dentity007/-gemma-4-after-24-hours-what-the-community-found-vs-what-google-promised-3a2f) |
| RTX 3090 | 31B | Q4 | 30-34 tok/s | [Community report](https://dev.to/dentity007/-gemma-4-after-24-hours-what-the-community-found-vs-what-google-promised-3a2f) |
| 雙 NVIDIA GPU | 31B | — | 18-25 tok/s | Community report |

> **注意：** CPU only 的 5-10 tok/s 數據是通用估計。i7-1255U 具備 AVX2 指令集但無 AVX-512，實際速度可能在此範圍的低端。25 tok/s 的數據來自有 GPU 的筆電，不適用於我們的 CPU-only 場景。

---

## 5. 多模態與 ASR 能力

### 5.1 原生音訊能力（E2B / E4B 專屬）

E2B 和 E4B 內建音訊編碼器（305M 參數），支援：
- **ASR（語音轉文字）**：多語言語音辨識
- **AST（語音翻譯）**：直接從語音翻譯為另一語言文字
- 訓練語言：官方聲稱 140+ 語言，但未公布 ASR 專用語言清單

### 5.2 ASR Benchmark

| 指標 | E2B | E4B | 對比：faster-whisper small |
|------|-----|-----|--------------------------|
| FLEURS WER | 0.09 | 0.08 | ~0.05-0.10（依語言） |
| CoVoST BLEU | 33.47 | 35.54 | N/A（Whisper 不做翻譯） |

> **ASR 與我們的關係：** 目前 [[system_overview]] 使用 faster-whisper small 做 ASR。E4B 的原生 ASR 能力理論上可替代 Whisper，但需驗證中文 ASR 品質。此為未來優化方向，不影響當前架構選擇。

### 5.3 Function Calling / 結構化 JSON

Gemma 4 原生支援：
- **Function Calling**：可輸出結構化 JSON 指定呼叫函式與參數
- **Structured Output**：vLLM guided decoding 可約束輸出符合指定 JSON Schema
- **System Instructions**：原生支援系統指令

> **社群評價：** Agentic tool use 是此次最顯著的升級。Tau2 benchmark 從 Gemma 3 的極低分跳到 76.9%（31B）。但社群提醒：「benchmark 受控環境下的數據漂亮，但在 messy schema 和 partial information 下的可靠性仍需驗證。」
> **來源：** [Google AI — Function Calling with Gemma 4](https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4)

---

## 6. 社群實測報告

### 6.1 24 小時社群發現

發布後 24 小時內社群回報的關鍵問題：

**速度問題（最多回報）：**
- 26B-A4B 在 5060 Ti 16GB 上僅 11 tok/s，同硬體 Qwen 3.5 35B-A3B 達 60+ tok/s
- 社群成員反映：「why is it super slow?」
- **根因：** Google 未採用 Qwen 3.5 的 KV 縮減技術，導致 MoE 模型在推理效率上落後

**記憶體問題：**
- 同一張 5090 GPU：Gemma 3 27B Q4 僅能用 20K context，Qwen 3.5 27B Q4 可用 190K context
- 31B 在 256K context 下 KV Cache 額外需要 ~22GB

**穩定性問題：**
- Google AI Studio 出現無限迴圈和圖片讀取失敗
- LM Studio 載入時 Mac 硬當
- 基本 system prompt 即可 jailbreak
- Fine-tuning 工具鏈不兼容（HuggingFace Transformers 不認 gemma4 架構、PEFT 無法處理 Gemma4ClippableLinear）

**來源：** [DEV.to — Gemma 4 After 24 Hours](https://dev.to/dentity007/-gemma-4-after-24-hours-what-the-community-found-vs-what-google-promised-3a2f) | [Let's Data Science — Community Found Catches](https://letsdatascience.com/blog/google-gemma-4-open-source-apache-community-found-catches)

### 6.2 多語言表現

**正面回報：**
- 社群一致認為 Gemma 4 在**非英語任務**上顯著優於 Qwen 3.5
- 德語、阿拉伯語、越南語、法語測試結果均超越 Qwen 3.5
- 有使用者稱翻譯品質「in a tier of its own」
- MMMLU（多語言知識）：E4B 76.6%、26B 86.3%、31B 88.4%

**中文特定：**
- 官方訓練涵蓋 140+ 語言含中文
- **但：** Gemma 系列（包括 4）的 instruction tuning 主要以英文進行，中文能力依賴 pretrain 階段
- 有社群成員進行中文 instruction fine-tuning 以補強（[GitHub — Gemma Chinese Instruction Tuning](https://github.com/windmaple/Gemma-Chinese-instruction-tuning)）
- 整體評估：中文能力不如 DeepSeek 或 Qwen 等中國廠商模型，但在同級開源模型中屬於中上水準
- **來源：** [Trending Topics — Gemma 4 Lags Behind Chinese Competitors](https://www.trendingtopics.eu/google-gemma-4-launch/)

### 6.3 與 Qwen 3.5 的社群對比

| 面向 | Gemma 4 | Qwen 3.5 |
|------|---------|----------|
| MMLU-Pro | 85.2%（31B） | 86.1% |
| Codeforces ELO | **2150**（31B，勝） | 1899 |
| 推理速度（MoE） | 11 tok/s | **60+ tok/s** |
| Context 效率 | 低（KV Cache 大） | **高** |
| 非英語表現 | **勝** | 一般 |
| 中文表現 | 中上 | **勝**（母語優勢） |
| 生態系統成熟度 | 較新 | **較成熟** |

LMArena Discord 社群總結：「Gemma 4 ties with Qwen, if not Qwen slightly ahead.」

### 6.4 JSON 輸出穩定性

- 官方原生支援結構化 JSON 輸出
- vLLM guided decoding 可強制輸出符合 schema
- **但 Ollama 環境下**：需依賴 `format: json` 參數或 prompt engineering
- 小模型（E2B/E4B）的 JSON 格式穩定性低於大模型，需額外約束
- **建議：** 使用 Ollama 時配合嚴格的 JSON schema prompt + 輸出驗證

### 6.5 幻覺與可靠性

- 官方稱 logit soft-capping + sliding window attention 可顯著降低幻覺
- 社群評價：相較 Gemma 3 有改善，但小模型（E2B/E4B）仍有幻覺風險
- **與 Llama 比較：** Gemma 4 的 sliding window attention 在長上下文尾端較不容易幻覺

---

## 7. 對我們場景的適用性分析

### 7.1 場景定義

```
輸入：中文會議逐字稿（~500-3000 字，含校正後文字）
輸出：結構化 JSON
  - highlights: 會議重點摘要（Markdown）
  - action_items: [{content, owner, deadline, priority, ...}]
  - decisions: [str]
  - keywords: [str]
硬體：Surface Pro 9（i7-1255U / 16GB RAM / CPU only）
```

### 7.2 各模型可行性評估

#### E2B（Q4_K_M = 7.2 GB）

| 面向 | 評估 | 說明 |
|------|------|------|
| **記憶體** | :white_check_mark: 可行 | 載入 ~3-4 GB，16GB RAM 餘裕充足 |
| **速度** | :warning: 堪用 | CPU ~5-8 tok/s，500 字摘要輸出約 60-100 秒 |
| **摘要品質** | :x: 不建議 | MMLU Pro 60%，推理能力不足以產生可靠的結構化摘要 |
| **中文** | :warning: 一般 | MMMLU 67.4%，中文能力有限 |
| **JSON 穩定性** | :x: 較差 | 小模型格式控制不穩定 |
| **ASR 替代** | :bulb: 潛力 | FLEURS WER 0.09，可考慮未來替代 Whisper |

**結論：** 不適合作為摘要模型。但原生 ASR 能力值得日後評估。

#### E4B（Q4_K_M = 9.6 GB）:star: 當前最佳選擇

| 面向 | 評估 | 說明 |
|------|------|------|
| **記憶體** | :white_check_mark: 可行 | 載入 ~6-7 GB，16GB RAM 仍可同時跑 Whisper + ChromaDB |
| **速度** | :warning: 堪用 | CPU ~5-10 tok/s，500 字摘要輸出約 50-100 秒 |
| **摘要品質** | :white_check_mark: 中上 | MMLU Pro 69.4%，**超越 Gemma 3 27B**（無 thinking） |
| **中文** | :white_check_mark: 中上 | MMMLU 76.6%，多語言表現強於同級競品 |
| **JSON 穩定性** | :warning: 需約束 | 需嚴格 prompt + 輸出驗證，但官方原生支援 |
| **ASR 替代** | :bulb: 潛力 | FLEURS WER 0.08，品質略優於 E2B |
| **Agentic** | :white_check_mark: 可用 | Tau2 42.2%，function calling 能力足夠 |

**結論：** 在 16GB RAM + CPU only 的硬體限制下，E4B Q4 是最佳選擇。相較原計畫的 Gemma 3 4B，E4B 在推理、多語言、工具使用方面均有顯著提升。

#### 26B-A4B（Q4_K_M = 18 GB）

| 面向 | 評估 | 說明 |
|------|------|------|
| **記憶體** | :x: 不可行 | 僅模型就需 ~18 GB，超過 16GB RAM |
| **速度** | :x: 不可行 | 即使能載入（磁碟 offload），CPU 推理極慢 |
| **摘要品質** | :white_check_mark: 優秀 | MMLU Pro 82.6%，品質顯著提升 |

**結論：** 16GB RAM 無法執行。需 24GB+ RAM 或 GPU 才可行。

#### 31B（Q4_K_M = 20 GB）

| 面向 | 評估 | 說明 |
|------|------|------|
| **記憶體** | :x: 不可行 | 模型需 ~20 GB，遠超 16GB RAM |
| **速度** | :x: 不可行 | CPU 推理完全不實用 |
| **摘要品質** | :white_check_mark: 頂級 | MMLU Pro 85.2%，Arena #3 開源模型 |

**結論：** 16GB RAM 完全無法執行。

### 7.3 記憶體預算分析（Surface Pro 9 / 16GB）

```
系統 + 背景程式：         ~4 GB
faster-whisper small：    ~1 GB
ChromaDB + Embedding：    ~0.5 GB
Flet Desktop App：        ~0.3 GB
───────────────────────────────
已佔用：                  ~5.8 GB
可用於 LLM：              ~10 GB
───────────────────────────────
E4B Q4_K_M：              9.6 GB（模型檔，載入後 ~6-7 GB）
+ 8K context KV Cache：   ~1 GB
───────────────────────────────
總計（E4B 場景）：        ~13-14 GB ← 勉強可行，需注意 context 長度
```

> **風險：** E4B Q4 在 16GB RAM 下運行時，系統剩餘 RAM 約 2-3 GB。如果會議逐字稿較長（>8K tokens），KV Cache 膨脹可能導致系統開始使用 swap，速度會急劇下降。

### 7.4 預期延遲估算

以中文會議摘要任務為例（輸入 ~1500 字逐字稿，輸出 ~500 字結構化 JSON）：

| 階段 | E4B Q4 (CPU) | 預估時間 |
|------|-------------|----------|
| Prompt 處理（prefill） | ~1500 tokens | 15-30 秒 |
| 生成（decode） | ~500 tokens @ 5-10 tok/s | 50-100 秒 |
| **總延遲** | | **65-130 秒** |

> 對比：[[system_overview]] 原計畫使用 Gemma 3 4B（現為 Gemma 4 E4B 同級替代），預期延遲在同一量級。可接受（會後審閱場景，非即時互動）。

---

## 8. 建議與結論

### 8.1 模型選型建議

| 優先級 | 建議 | 理由 |
|--------|------|------|
| :star: **首選** | **Gemma 4 E4B Q4_K_M** | 16GB RAM 可行、品質超越 Gemma 3 27B、原生 JSON/function calling、多語言表現強 |
| :two: 備選 | Gemma 4 E2B Q4_K_M | 記憶體更寬裕（7.2 GB），但摘要品質不足 |
| :three: 未來升級 | Gemma 4 26B-A4B | 若硬體升級至 24GB+ RAM，品質大幅提升 |

### 8.2 Ollama 指令

```bash
# 安裝首選模型
ollama pull gemma4:e4b

# 驗證
ollama run gemma4:e4b "用繁體中文摘要以下會議內容，輸出 JSON 格式..."
```

### 8.3 需要注意的事項

1. **JSON 輸出穩定性**：E4B 的 JSON 格式控制不如大模型穩定，建議：
   - Prompt 中明確定義完整 JSON schema
   - 程式端加入 JSON 驗證 + 重試機制
   - 考慮使用 Ollama 的 `format: json` 參數

2. **中文品質**：Gemma 4 中文能力不如 DeepSeek/Qwen 系列，但在同級開源模型中屬中上。建議：
   - 搭配 [[data_schema#1. 知識詞條（Term）|RAG 知識庫校正]] 補強專有名詞
   - 摘要 prompt 使用繁體中文，明確要求輸出語言

3. **記憶體管理**：E4B Q4 在 16GB RAM 下為緊繃配置，建議：
   - 限制 context 長度（建議 ≤ 8K tokens）
   - Pipeline 設計中，Whisper 轉錄完成後再載入 LLM（避免同時佔用）
   - 監控 RAM 使用，設定告警閾值

4. **E4B 原生 ASR 的未來可能性**：
   - E4B 內建 ASR（FLEURS WER 0.08），理論上可同時完成轉錄 + 摘要
   - 但目前 Ollama 對音訊輸入的支援尚不成熟
   - 建議作為 v2.0 的研究方向，不影響當前 Whisper + E4B 的架構

5. **Gemma 4 生態系統仍在早期**：
   - KV Cache 優化補丁（llama.cpp）可能尚未進入 Ollama
   - 社群回報的穩定性問題預計在未來幾週內逐步修復
   - 建議追蹤 [ollama/ollama GitHub Issues](https://github.com/ollama/ollama/issues) 的 gemma4 相關問題

### 8.4 配置檔建議更新

```yaml
# config/default.yaml — 建議更新
ollama:
  model: "gemma4:e4b"        # 從 gemma4:4b 升級
  base_url: "http://localhost:11434"
  options:
    num_ctx: 8192             # 限制 context 避免 OOM
    temperature: 0.3          # 低溫度提升 JSON 穩定性
```

---

## 9. 資料來源索引

| 來源 | 類型 | 重點內容 |
|------|------|----------|
| [Google Blog — Gemma 4](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/) | 官方 | 發布公告、模型概覽 |
| [Gemma 4 Model Card](https://ai.google.dev/gemma/docs/core/model_card_4) | 官方 | 完整 benchmark 數據 |
| [HuggingFace — Welcome Gemma 4](https://huggingface.co/blog/gemma4) | 官方 | 技術細節、生態系統 |
| [Ollama — gemma4 tags](https://ollama.com/library/gemma4/tags) | 工具 | 模型檔案大小 |
| [Unsloth — Gemma 4 Local](https://unsloth.ai/docs/models/gemma-4) | 工具 | 量化、本地部署指南 |
| [Avenchat — Hardware Requirements](https://avenchat.com/blog/gemma-4-hardware-requirements) | 分析 | 硬體需求表 |
| [DEV.to — After 24 Hours](https://dev.to/dentity007/-gemma-4-after-24-hours-what-the-community-found-vs-what-google-promised-3a2f) | 社群 | 24 小時社群測試結果 |
| [Let's Data Science — Community Catches](https://letsdatascience.com/blog/google-gemma-4-open-source-apache-community-found-catches) | 社群 | 速度問題、KV Cache |
| [Latent Space — Gemma 4 AINews](https://www.latent.space/p/ainews-gemma-4-the-best-small-multimodal) | 分析 | 與 Gemma 3 比較 |
| [n1n.ai — KV Cache Fix](https://explore.n1n.ai/blog/gemma-4-local-inference-llama-cpp-kv-cache-fix-npu-benchmarks-2026-04-05) | 技術 | llama.cpp 記憶體優化 |
| [Trending Topics — Chinese Competitors](https://www.trendingtopics.eu/google-gemma-4-launch/) | 分析 | 中文競品對比 |
| [Google AI — Function Calling](https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4) | 官方 | Function calling 文件 |
| [Google AI — Audio Understanding](https://ai.google.dev/gemma/docs/capabilities/audio) | 官方 | ASR 能力文件 |

---

> 本報告由 Researcher Agent 產出，供 Director 決策參考。
> 相關 Specs：[[system_overview]] | [[data_schema]] | [[ui_spec]]
> 相關研究：[[competitive_analysis_20260404]]
