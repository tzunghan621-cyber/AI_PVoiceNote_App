---
title: 決策紀錄 — Mic Live 指示器納入 spec
date: 2026-04-17
type: decision
status: active
author: 大統領
tags:
  - decision
  - spec-change
  - ui
  - audio
---

# 決策紀錄 — Mic Live 指示器

## 背景

V Phase 第五輪實機錄音時，實驗者發現甲方 Surface Pro 9 內建麥克風峰值 -52 dBFS（正常說話應 -20 ~ -10 dBFS），VAD 全過濾導致 segments 全空 — **錄完才發現收音失敗**。

甲方主動提出 UX 改善：「可以有一個 mic live 的動態指示圖標」。

## 甲方決策

甲方同意規格變動（對應 v4.0 director_handbook §簽核權責分級「規格變更」類別）。

## 規格變更內容

### ui_spec 新增

**§2.1 idle 畫面：** 新增「🎤 [測試麥克風]」按鈕

**§2.3 即時儀表板頂部列：** 計時器旁加 Mic Live 音量條

**§2.5 Mic Live 指示器（新節）：**
- 10 格音量條 + 四級顏色（靜音/正常/大聲/爆音）
- 會中常駐 + Mic Test 模式（5 秒閒置預覽）
- Mic Test 不建 Session、不寫 WAV
- 無障礙：dBFS 文字顯示 + 長靜音 SnackBar 警訊

### system_overview §3.2 AudioRecorder 職責擴增

- `get_current_level() -> float`（dBFS, -80 ~ 0）
- `start_level_probe()` / `stop_level_probe()`（Mic Test 純量測模式）
- 背景 rolling buffer（最近 200ms RMS），不影響轉錄主路徑

### data_schema §8 config 新增

```yaml
ui:
  mic_indicator:
    poll_interval_ms: 200
    threshold_silent_dbfs: -40
    threshold_normal_dbfs: -30
    threshold_loud_dbfs: -12
    threshold_clipping_dbfs: -3
    test_duration_sec: 5
```

## 實作時機

**不插隊當前 Bug #13/#14 修復流程。** 排入碼農 B 修 Bug #14 的同一批次（兩者都改 `app/ui/dashboard_view.py` 且主題都是 UI lifecycle，一次做完）。

順序：
1. 研究者補 Flet 0.84 async/lifecycle 研究（進行中）
2. 碼農 A 修 Bug #13（邏輯層）
3. 碼農 B 修 Bug #14 + **同批實作 Mic Live 指示器**
4. 實驗者 V Phase 第六輪（含 mic live 驗證）

## 連帶價值

除了解決甲方當下痛點，此功能也對齊 [[project_voicenote_overview|太極門共用計畫]]：
- 非技術人員能自檢麥克風硬體
- 會議中可即時發現收音異常（耳機拔掉、USB 斷線）
- 降低「錄完整場才發現全空」的挫敗風險

## 相關文件

- [[ui_spec#2.5 Mic Live 指示器]]
- [[system_overview#3.2 模組職責]]（AudioRecorder 列）
- [[data_schema#8. 設定檔]]
- [[devlog_20260416_verifier_vphase5]]（環境觀察引出此需求）
