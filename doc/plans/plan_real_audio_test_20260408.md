---
title: 實作計畫 — 真實錄音端對端自動化測試
date: 2026-04-08
type: plan
status: active
author: 碼農
tags:
  - plan
  - testing
  - e2e
  - automation
---

# 計畫 — 真實錄音端對端自動化測試

> 把過去靠手動 V Phase 驗證的「拿真錄音跑一次完整流程」變成 pytest 自動化。
> 相關：[[devlog_20260408_filepicker_api]]、[[plan_implementation_20260405]]

---

## 背景

V Phase 一直靠實驗者手動拖檔案進 App、肉眼看結果。這很慢、不可重現、容易漏。
甲方準備好真實會議錄音後，把這流程自動化成 pytest，CI 能跳過、本機可全跑。

---

## 目標

1. **自動掃描**：丟檔到 `tests/fixtures/audio/` 即被測試吃到，無需改 code
2. **完整 Pipeline**：每個檔案走 `AudioImporter → Transcriber → RAGCorrector → Summarizer → Exporter`
3. **可選性執行**：用 `@pytest.mark.real_audio` 與日常 unit test 隔離
4. **可觀察**：每階段印出耗時與 RSS，方便 Surface Pro 9 上效能調校

---

## 設計決策

| 項目 | 決策 | 理由 |
|---|---|---|
| Fixture 目錄 | `tests/fixtures/audio/` | 與其他測試同處，git 排除大檔 |
| Marker | `real_audio`（新增） | 與既有 `slow` 區隔，後者僅 ML 載入；前者還要 Ollama |
| 參數化 | `pytest.parametrize` 動態掃描 | 加檔即跑，無需改 code |
| Whisper 模型 | `tiny` | 加速；測 pipeline 通暢非辨識準度 |
| 記憶體量測 | psutil（缺則跳過） | 不強制依賴 |
| Ollama 失敗處理 | `pytest.skip` 而非 fail | 模型未 pull 不該掛掉測試 |
| 無檔案處理 | `skipif` 整檔跳過 | CI 無素材時保持綠燈 |

---

## 變更清單

| 檔案 | 動作 | 內容 |
|---|---|---|
| `pyproject.toml` | 修改 | 新增 `real_audio` marker |
| `.gitignore` | 修改 | 排除 `tests/fixtures/audio/*`，保留 `.gitkeep` 與 `README.md` |
| `tests/fixtures/audio/.gitkeep` | 新增 | 保留空目錄 |
| `tests/fixtures/audio/README.md` | 新增 | 使用者放檔說明 |
| `tests/test_e2e_real_audio.py` | 新增 | 端對端測試本體 |

---

## 驗證項目（逐音檔）

| 階段 | 驗證 |
|---|---|
| AudioImporter | `get_duration > 0`、至少產出一個 chunk |
| Transcriber | segments 非空、首段文字不為空 |
| RAGCorrector | 段數一致、命中數可為 0（無詞條也算正常） |
| Summarizer | 回傳 `SummaryResult`、`highlights` 欄位存在；Ollama 不可用 → `skip` |
| Exporter | Markdown 檔產出、含 `# 會議摘要` 與 `## 逐字稿` 標題 |

每階段印出：耗時、RSS、產出數量。最後印 RTF（real-time factor）。

---

## 執行方式

```bash
# 跑真實錄音測試
python -m pytest -m real_audio -v -s

# 日常開發跳過
python -m pytest -m "not real_audio and not slow"

# 全跑（包含 slow + real_audio）
python -m pytest -v -s
```

---

## 前置需求（執行真實錄音測試時）

- `ollama serve` 啟動中
- `ollama pull gemma4:e2b`
- `tests/fixtures/audio/` 至少一個 `.wav` / `.mp3` / `.m4a`
- 第一次跑會自動下載 faster-whisper `tiny` 模型

---

## 後續可擴充

- 加入「音檔 → 預期關鍵詞」對應檔，驗證 Summarizer 真有抓到關鍵字
- 多模型對比測試（E2B vs E4B）
- 跨機器效能基線（Surface Pro 9 vs 桌機）
