---
title: Ollama 使用指南
date: 2026-04-06
type: manual
status: active
author: 大統領
tags:
  - ollama
  - gemma
  - local-llm
  - setup
---

# Ollama 使用指南

> 本 App 使用 Ollama 運行本地端 Gemma 4 模型。本文件涵蓋 Ollama 的基本概念、安裝設定、日常操作。
> 系統架構見 [[system_overview]]

---

## 1. Ollama 是什麼

**Ollama 是本地端大型語言模型的管理器與推理引擎。** 類似 Docker 管理容器，Ollama 管理 LLM 模型。

| 概念 | Docker 類比 | Ollama |
|------|-----------|--------|
| 映像檔 | Docker Image | 模型檔（如 `gemma4:e4b`） |
| 容器 | Container | 載入記憶體的模型實例 |
| 倉庫 | Docker Hub | ollama.com/library |
| 指令 | `docker pull/run/ps` | `ollama pull/run/ps` |

**核心特點：**
- 一鍵下載模型（`ollama pull`）
- 自動量化管理（不用自己轉 GGUF）
- 提供 REST API（`http://localhost:11434`）讓程式呼叫
- 支援同時載入多模型
- 自動管理 GPU/CPU 推理切換

---

## 2. 安裝

### Windows

1. 下載安裝檔：https://ollama.com/download/windows
2. 執行安裝（預設路徑即可）
3. 安裝完成後 Ollama 會自動啟動（系統匣有圖示）

### 驗證安裝

開 PowerShell 或 CMD：

```bash
ollama --version
```

應顯示版本號（如 `ollama version 0.6.x`）。

---

## 3. 模型管理

### 下載模型

```bash
# 下載本專案預設模型（Gemma 3 4B，3.3GB）
ollama pull gemma3:4b

# 若硬體允許，可額外下載更高品質模型
# ollama pull gemma4:e2b   # 7.2GB，標準
# ollama pull gemma4:e4b   # 9.6GB，高階

# 查看下載進度（自動顯示）
# 模型大小約 3GB，首次下載需等待
```

### 常用指令

| 指令 | 用途 | 範例 |
|------|------|------|
| `ollama pull <model>` | 下載模型 | `ollama pull gemma4:e4b` |
| `ollama list` | 列出已下載的模型 | 顯示名稱、大小、修改日期 |
| `ollama ps` | 查看正在運行的模型 | 顯示模型名稱、記憶體用量 |
| `ollama run <model>` | 互動式對話（測試用） | `ollama run gemma4:e4b` |
| `ollama rm <model>` | 刪除模型 | `ollama rm gemma4:e4b` |
| `ollama show <model>` | 顯示模型資訊 | 參數量、量化格式、模板等 |

### 模型命名規則

```
模型名稱:標籤
gemma4:e4b            ← Gemma 4 E4B（4.5B 有效參數，預設 Q4_K_M 量化）
gemma4:e4b-it-q4_K_M  ← 明確指定量化格式（與 e4b 相同）
gemma4:e2b            ← Gemma 4 E2B（降級方案，2B 有效參數）
llama3.3:70b     ← Meta 的 Llama 3.3 70B
```

- 不指定標籤時，Ollama 會下載預設版本（通常是最常用的量化版本）
- `4b` = 4 Billion 參數，`q4` = 4-bit 量化

---

## 4. Ollama REST API

本 App 透過 HTTP API 呼叫 Ollama，不是用命令列。

### API 端點

| 端點 | 方法 | 用途 |
|------|------|------|
| `http://localhost:11434/api/generate` | POST | 文字生成（本 App 摘要用此端點） |
| `http://localhost:11434/api/chat` | POST | 對話模式 |
| `http://localhost:11434/api/tags` | GET | 列出已下載模型 |
| `http://localhost:11434/api/show` | POST | 模型詳細資訊 |
| `http://localhost:11434/` | GET | 健康檢查（回傳 "Ollama is running"） |

### 測試 API 連線

PowerShell：

```powershell
# 健康檢查
curl http://localhost:11434/

# 簡單生成測試
curl http://localhost:11434/api/generate -d '{
  "model": "gemma4:e4b",
  "prompt": "用一句話說明什麼是 RAG",
  "stream": false
}'
```

### 本 App 的呼叫方式

App 中的 `summarizer.py` 使用 `httpx` 呼叫 Ollama API：

```python
# 簡化示意
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "gemma4:e4b",
            "prompt": "請摘要以下會議內容...",
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_ctx": 8192
            }
        },
        timeout=120.0
    )
```

---

## 5. 記憶體管理

### 模型載入行為

- Ollama **不會一直佔用記憶體**
- 第一次呼叫 API 時，模型載入記憶體（需要幾秒到幾十秒）
- 閒置一段時間（預設 5 分鐘）後**自動卸載**
- 下次呼叫時重新載入

### 本專案的記憶體估算

| 元件 | 記憶體 |
|------|--------|
| Gemma 4 E4B Q4_K_M | ~9.6 GB（模型檔）|
| faster-whisper small | ~1.5 GB |
| ChromaDB + Embedding | ~0.5 GB |
| App 本身 | ~0.5 GB |
| **合計** | **~5.5 GB** |

在 Surface Pro 9（16GB RAM）上有足夠餘裕。

### 手動管理

```bash
# 查看哪些模型在記憶體中
ollama ps

# 強制卸載所有模型（釋放記憶體）
# 目前無直接指令，停止 Ollama 服務即可
```

---

## 6. 常見問題排除

### Ollama 沒有啟動

**症狀：** App 狀態列顯示 🔴 Ollama 未連線

**解決：**
1. 檢查系統匣有沒有 Ollama 圖示
2. 若沒有，開 PowerShell 執行 `ollama serve`
3. 或重新啟動 Ollama（右鍵系統匣圖示 → Quit → 重新開啟）

### 模型未下載

**症狀：** API 回傳 `model not found`

**解決：**
```bash
ollama pull gemma4:e4b
```

### 推理很慢

**可能原因：**
- 首次呼叫需要載入模型（冷啟動，可能需 10-30 秒）
- CPU 推理本來就比 GPU 慢（Surface Pro 9 無獨顯）
- 同時有其他 heavy 程式在跑

**緩解：**
- App 啟動時會自動預載模型（溫啟動）
- 關閉不必要的程式釋放 CPU 資源
- 設定頁可調整 `num_ctx`（context 越小越快）

### Port 被佔用

**症狀：** `localhost:11434` 無法連線但 Ollama 已啟動

**解決：**
```powershell
# 查看誰佔用 11434 port
netstat -ano | findstr 11434
```

---

## 7. 本 App 的 Ollama SOP

### 開會前

1. 確認 Ollama 已啟動（系統匣有圖示）
2. 開啟 App → 檢查狀態列顯示 🟢 Ollama 已連線
3. （選用）在設定頁按「測試連線」確認模型可用

### 首次設定

```bash
# 1. 安裝 Ollama（見 §2）

# 2. 下載預設模型
ollama pull gemma3:4b

# 3. 驗證
ollama run gemma3:4b "你好，請用繁體中文回答"
# 輸入 /bye 離開

# 4. 啟動 App，確認狀態列綠燈
```

### 更新模型

```bash
# Ollama 會自動檢查更新
ollama pull gemma3:4b

# 若有新版本會自動下載差異部分
```

---

## 8. 進階：可用的 Gemma 4 模型

| 模型名稱 | 參數量 | 大小 | 適用場景 |
|----------|--------|------|---------|
| `gemma3:1b` | Gemma 3 1B | ~1.0 GB | 極輕量 — 8GB RAM 舊筆電 |
| `gemma3:4b` | Gemma 3 4B | ~3.3 GB | **本 App 預設** — 16GB RAM 筆電舒適運行 |
| `gemma4:e2b` | E2B（2B 有效 / 5.1B 總） | ~7.2 GB | 標準 — 16GB + 不開其他程式 |
| `gemma4:e4b` | E4B（4.5B 有效 / 8B 總） | ~9.6 GB | 高階 — ≥32GB RAM 或有 GPU |
| `gemma4:26b` | 26B MoE | ~18 GB | 品質最好，需大量 RAM |

> 在 `config/default.yaml` 中修改 `ollama.model` 即可切換模型。
> Surface Pro 9（16GB RAM）預設用 `gemma3:4b`（3.3GB），需要更高品質可升 `gemma4:e2b`（7.2GB）。設定頁可切換。

---

## 相關文件

- [[system_overview#2. 技術選型]] — 為什麼選 Gemma 4 E4B
- [[system_overview#8. 前置需求]] — Ollama 為前置需求
- [[data_schema#8. 設定檔]] — Ollama 相關設定欄位
