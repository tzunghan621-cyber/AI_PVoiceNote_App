---
title: 決策紀錄 — 模型選型修正（Gemma 4 E4B 預設 + E2B 降級）
date: 2026-04-06
type: decision
status: active
author: 大統領
tags:
  - decision
  - model-selection
  - gemma4
---

# 決策紀錄 — 模型選型修正

## 背景

V Phase 實驗者冒煙測試時發現 `gemma4:4b` 在 Ollama 上不存在，觸發一連串模型選型重新評估。

## 事件經過

### 1. 模型名稱錯誤（大統領失職）

- **問題**：specs 寫 `gemma4:4b`，實際 Ollama tag 是 `gemma4:e4b`
- **根因**：技術選型時未驗證外部依賴的實際名稱
- **影響**：全專案 doc + code 散布錯誤名稱，V Phase 才爆出
- **教訓**：技術選型寫入 specs 前，必須用 `ollama pull` 實際驗證模型可用性

### 2. 四層級方案（短暫存在）

大統領發現 E4B 檔案大小 9.6GB 後，擔心 Surface Pro 9（16GB RAM）跑不動，提出四層級方案：
- gemma3:1b / gemma3:4b / gemma4:e2b / gemma4:e4b

甲方同意，碼農實作完成並通過 Review。

### 3. 研究者報告推翻四層級

研究者完成 [[gemma4_model_analysis_20260406]]，關鍵數據：
- E4B **檔案** 9.6GB，但**載入 RAM 只需 6-7GB**
- 加上 Whisper + ChromaDB + App，總計 ~13-14GB，16GB 機器可行
- E4B 品質超越 Gemma 3 27B（MMLU Pro 69.4%）
- 原生 JSON/function calling 支援

### 4. 甲方最終決策

甲方明確：**「不，我沒要用 gemma3 系列的模型」**

## 最終決策

| 項目 | 決策 |
|------|------|
| 預設模型 | `gemma4:e4b`（4.5B 有效參數） |
| 降級方案 | `gemma4:e2b`（2B 有效參數） |
| Context 限制 | `num_ctx: 8192`（避免 KV Cache 膨脹） |
| Temperature | `0.3`（提升 JSON 穩定性） |
| Gemma 3 | **不使用** |

## 記憶體預算（Surface Pro 9 / 16GB）

```
系統 + 背景：         ~4 GB
faster-whisper small： ~1 GB
ChromaDB + Embedding： ~0.5 GB
App：                  ~0.3 GB
Gemma 4 E4B Q4：       ~6-7 GB
+ 8K context KV Cache： ~1 GB
────────────────────────────
總計：                 ~13-14 GB（餘裕 2-3 GB）
```

## 風險

- Context 超過 8K tokens 時 KV Cache 膨脹會導致 swap → 配合 `num_ctx: 8192` 緩解
- 同時開太多程式會擠壓餘裕 → 使用手冊提醒
- JSON 穩定性不如大模型 → 嚴格 prompt + 重試機制（已在 summarizer 實作）

## 相關文件

- [[gemma4_model_analysis_20260406]] — 研究者完整報告
- [[system_overview#摘要模型選型]] — 更新後的選型表
- [[data_schema#8. 設定檔]] — 新增 num_ctx / temperature
