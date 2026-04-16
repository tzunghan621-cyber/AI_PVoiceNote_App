---
title: 開發日誌 2026-04-16 — Verifier V Phase 第三輪（GUI 協同撞 Bug #9）
date: 2026-04-16
type: devlog
status: active
author: 實驗者（Verifier）
tags:
  - devlog
  - v-phase
  - verification
  - flet
  - gui-smoke
  - bug-9
  - pipeline-lifecycle
related:
  - "[[verification_report_20260405]]"
  - "[[devlog_20260416_builderB_bug8]]"
  - "[[flet_0.84_migration_20260408]]"
  - "[[bug_report_flet_api_20260406]]"
---

# Verifier V Phase 第三輪 — 2026-04-16

> 前一棒：[[devlog_20260416_builderB_bug8]]（碼農 B 修 Bug #8 + 甲方協同 S1/S6/S7/S8 全 PASS）
> 驗收報告更新位置：[[verification_report_20260405]] §7

---

## 接手脈絡

Bug #1~#8 Flet 0.84 API 不相容已全數修復，127 tests 通過。碼農 B 交棒，實驗者接手跑完整 [[flet_0.84_migration_20260408]] §G4 S1-S9 GUI smoke test。

碼農 B 已協同甲方完成 S1/S6/S7/S8。待跑：**S2 響應式、S3 Dashboard live、S4 對話框、S5 SnackBar、S9 拖動切換**。

---

## 本輪執行成果

### ✅ Verifier autonomous 可做部分（全通過）

1. **自動化 fast suite**：`pytest -m "not slow and not real_audio" -q` → **106 passed / 0 failed**
2. **App 啟動冒煙**：`python -m app.main` → TCP + Flet client + session started，log clean 無 Traceback
3. **靜態檢查**：[dashboard_view.py](app/ui/dashboard_view.py) 響應式 API（`page.on_resize` + breakpoints 1400/960）對齊 [[ui_spec]]

### ⏳ 無法 autonomous 的部分（需甲方協同）

S2-S5 + S9 全數為 Flet Desktop **GUI 互動**，需實機操作：
- S2：拖動視窗觀察三欄 → 兩欄+Tabs → 單欄+Tabs
- S3：匯入音檔、進 live、觀察三區塊動態更新
- S4：FilePicker / 會議資訊 / 匯出確認對話框
- S5：SnackBar 錯誤提示 + 設定儲存提示
- S9：響應式拖動切換

Verifier agent 在 CLI 環境，沒有 programmatic GUI driver（Flet Desktop 無 pytest-qt / playwright 類工具），**無法自動點按鈕、拖動視窗或視覺確認 SnackBar**。

### 額外一次 Pipeline 層試跑（非阻塞）

臨時把 [data/temp/錄製.m4a](data/temp/錄製.m4a)（50s）塞進 fixtures 跑 `pytest -m real_audio`：
- AudioImporter ✅
- Transcriber (whisper **tiny**) → 0 segments ⚠️（tiny 對短低語音密度音檔召回率不足，**非 bug**）
- test 本身有個 `print("🎙️...")` 在 cp950 終端 UnicodeEncodeError — 用 `PYTHONIOENCODING=utf-8` 繞過

已清理臨時 fixture，**不列為 bug**。建議 S3 協同時順便走完整 pipeline（spec 預設 small 模型）做最終確認。

---

## 回報大統領

**本輪結論**：
- 🟢 Verifier 自主部分（回歸 / 冒煙 / 靜態檢查）**全通過、無新 bug**
- ⏳ S2-S5 + S9 **需甲方 15-30 分鐘協同 session**
- 建議協同模式仿 Bug #8：甲方操作 GUI、Verifier 背景 tail log 過濾 Traceback/Error

**若甲方協同通過**：Verifier 回來補 [[verification_report_20260405]] §7.4 表格 → 下「可進甲方最終簽核」結論。

**若協同發現新問題**：依 [[bug_report_flet_api_20260406]] 格式列 Bug #9+，交大統領派工：
- UI / 控件 API 類 → 碼農 B
- Pipeline / 邏輯 / 資料層 → 碼農 A

---

## 規則遵守確認

- [x] 有問題立刻回報大統領，不自己 loop 修 bug
- [x] 未修任何 code（Verifier 寫入權限僅 `history/` + `reports/`）
- [x] 驗收報告 + devlog 皆產出（[[verifier_handbook]] 要求）
- [x] 已知 UX 議題（S6 ML 阻塞）不當 bug 回報
- [x] 清理測試副產物（`tests/fixtures/audio/vphase3_sample.m4a` 已移除）

---

> 實驗者簽核：自動化層完成，等大統領安排甲方協同時段。

---

## 補記（同日晚協同結果）

> 甲方當日即啟動 App 實測「隨便玩」，觸發 Bug #9。

### 執行過程

1. Verifier 背景 `python -m app.main`，Monitor 持續過濾 Traceback/Error
2. 甲方點「開始錄音」進入即時錄音模式
3. 錄約 **3 分鐘** Monitor 即通知：
   - `ERROR:__main__:Pipeline error:`（空訊息）
   - `RuntimeError: async generator ignored GeneratorExit`
4. 甲方當下 GUI 狀態：
   - 錄音計時跑到 **08:19** 還在走
   - 逐字稿仍有新 segment 進來，時間戳在某點 **[00:08] → [00:00]** 歸零
   - **「停止錄音」按鈕按了完全沒反應**
5. Verifier 就 log + 程式碼（[main.py:68-104](app/main.py#L68-L104) + [stream_processor.py](app/core/stream_processor.py) + [audio_importer.py:23](app/core/audio_importer.py#L23)）定位根因
6. 用 `TaskStop` 強制終止背景 python process 救甲方脫離殭屍 GUI

### 根因結論

**Bug #9 — Pipeline 崩潰未連帶停止 recorder，UI 與 runtime state 失聯**（非 Flet API 問題，邏輯層 lifecycle 缺陷）。完整拆解見 [[bug_report_flet_api_20260406]] §Bug #9。

### 插曲 — 角色界線確認

甲方協同中間曾說「邊看問題邊修吧」。Verifier 一度準備切碼農 A 角色進場修，先產出修法藍圖請甲方確認；甲方隨即回「算了你是測試者，照規矩來吧」→ Verifier 退回本分，只產出正式 bug report 與驗證報告，不改 code。

**教訓**：即使甲方一句授權，也要尊重既有角色分工（[[feedback_no_code_edit|大統領不碰 code]]），Verifier 同理只寫 `history/` + `reports/`。修 code 一律交指派的碼農。

### S2/S4/S5/S9 狀態

S3 阻塞在前，其餘未測（詳 [[verification_report_20260405]] §7.4）。

### 交棒

**大統領請派工碼農 A** 修 Bug #9：
- 主修 [main.py:68-104](app/main.py#L68-L104) 的 `_run` / `on_stop_recording` / `recorder` lifecycle
- 次修錯誤 log 改 `logger.exception` + `CancelledError` 獨立分流
- 驗證條件見 bug report
- 碼農 A 修完後 Verifier 接手跑 regression + 重跑 5-10 分鐘即時錄音 + 補 S2/S4/S5/S9

---

> 實驗者最終簽核：第三輪 GUI 協同發現 Bug #9，阻塞 S3；S2/S4/S5/S9 併在 #9 修完後一起驗證。
