---
title: 碼農 B 開發日誌 — Bug #14 lifecycle 掃清 + Mic Live 指示器
date: 2026-04-17
type: devlog
agent: 碼農 B（Builder B）
tags:
  - devlog
  - bug-14
  - lifecycle
  - mic-live
  - ui
related:
  - "[[flet_0.84_async_lifecycle_20260417]]"
  - "[[decision_20260417_mic_live_indicator]]"
  - "[[bug_report_flet_api_20260406]]"
  - "[[ui_spec]]"
---

# 碼農 B 開發日誌 — Bug #14 lifecycle 掃清 + Mic Live 指示器

## 任務來源

大統領派工，依研究者 [[flet_0.84_async_lifecycle_20260417]] §6 修復指引 + 甲方簽核 [[decision_20260417_mic_live_indicator]] 規格變更。兩個任務同批做（同檔 + 同主題），碼農 A 並行修 main.py Bug #13 不衝突。

---

## Part 1 — Bug #14 + 全面 lifecycle 掃清

### 根因回顧

Flet 0.84 把 `BaseControl.page` 改為 property，未 mount 時 **raise RuntimeError** 而非返 None。全專案 9+ 處 `if self.page:` 守衛都是**假守衛** — 在 unmount 狀態下會 raise 而非短路。

Bug #14 現場：`_build_review` → `SummaryPanel.update_highlights` → `if self.page:` → RuntimeError。

### 採用方案

研究者推薦 **Pattern A**（`_mounted` flag + `did_mount` / `will_unmount`），碼農 B 全面套用。

### 改動清單

#### 階段 1 — Panel 類改造（🔴 高危 A1~A4）

| class | 改動 |
|---|---|
| `TranscriptPanel` | `__init__` 加 `self._mounted = False`；加 `did_mount` / `will_unmount`；`append` L102 改 `self._mounted`；`_scroll_to_bottom` L124 改 `self._mounted` |
| `SummaryPanel` | 同上；`_on_highlights_changed` / `update_highlights` / `update_decisions` 三處改 |
| `ActionsPanel` | 同上；`_refresh_ui` 改 |

#### 階段 2 — DashboardView 本身（🟢 低危一致性）

| 位置 | 改動 |
|---|---|
| `set_mode` L378 | `if self.page:` → `if self._mounted:` |
| `_on_page_resized` L638 | 同 |
| `_apply_responsive_layout` L643 | `self.page and self._page_ref.window` → `self._mounted and self._page_ref.window` |

#### 階段 3 — 其他 view

| 檔案 | 改動 |
|---|---|
| `feedback_view.py` | 加 `_mounted` flag + `did_mount` / `will_unmount`；`refresh` 內 `if self.page:` → `if self._mounted:` |
| `terms_view.py` | 同上；`refresh` 內改 |
| `settings_view.py` | 同上；`_save` 的 `hasattr(self, 'page') and self.page` 假守衛 → `if self._mounted:`；`_reset` 內 `if self.page:` 同改 |
| `main_view.py` StatusBar | 同上；四個 `update_*` 方法全改 |

#### 最終掃描

```
grep "if self\.page:" app/ui/   → 0 matches
grep "hasattr(self.*page" app/ui/  → 0 matches
```

### 設計決策

- **Pattern A 而非 Pattern C**：研究者 §6.1 C16 不確定 Flet 首次 mount 是否自動 render ctor 當下的 property 值。碼農 B 選 Pattern A — `_build_review` 先賦值 `_highlights_field.value`（mount 前），mount 後 Flet 首次 render 會帶出新值。若 V6 實機不顯示，再補 Pattern C（`did_mount` 內 render）。
- **事件 callback 內不需守門**：研究者 §3.4 確認 Flet 事件派發前 control 必 mount。但為一致性，碼農 B 仍全面用 `_mounted`（如 `_on_highlights_changed` 是事件觸發，但改了也不壞）。

---

## Part 2 — Mic Live 指示器

### 規格對齊

依 [[ui_spec#2.5 Mic Live 指示器]] + [[system_overview#3.2]] AudioRecorder 新 API + [[data_schema#8]] config。

### AudioRecorder 擴增（`app/core/audio_recorder.py`）

| API | 說明 |
|---|---|
| `get_current_level() -> float` | 回傳當前 RMS 的 dBFS（-80 ~ 0），背景 rolling buffer 200ms |
| `start_level_probe()` | Mic Test 純量測模式：開 InputStream 但不送 queue、不寫 WAV |
| `stop_level_probe()` | 停止純量測 |

實作細節：
- `_level_ring: deque[float]`（maxlen = sample_rate * poll_ms / 1000）
- `_update_level(indata)` 算 RMS → `20 * log10(rms)` → clamp -80~0
- 正常 `start()` 的 `_audio_callback` 同時更新 level ring（Mic Live 共用）
- `_probe_callback` 只更新 level 不送 queue

### DashboardView — 會中 Mic Live

- `_build_live` 頂部列加 🎤 + `ft.ProgressBar`（width=100, bar_height=8）+ dBFS 文字
- `_start_level_poll()` 以 `page.run_task` 啟 200ms 週期 poll
- `_update_mic_level_ui(dbfs)` 四級顏色：
  - `< -40`：`COLOR_TEXT_DIM`（靜音，深灰）
  - `-40 ~ -30`：隱含過渡
  - `-30 ~ -12`：`COLOR_GREEN`（正常）
  - `-12 ~ -3`：`COLOR_AMBER`（大聲）
  - `> -3`：`COLOR_RED`（爆音）
- 靜音 > 3 秒 → SnackBar 警訊「麥克風訊號極弱，請檢查設定」
- `set_mode` 離開 live 時 `_stop_level_poll()`

### DashboardView — Mic Test 模式

- idle 畫面新增「🎤 測試麥克風」按鈕
- `_handle_mic_test(e)`：
  1. 建 Mic Test UI（大音量條 + peak dBFS + 倒數文字 + 取消按鈕）
  2. `audio_recorder.start_level_probe()` 啟動純量測
  3. `page.run_task` 啟 poll loop，每 200ms 更新，倒數到 0 自動停
- `_stop_mic_test()`：停 probe + 隱藏 UI

### DashboardView 新參數

`audio_recorder=None` — main.py 建構時需傳入。碼農 A 修 main.py 時請配合。

---

## Part 3 — Contract Tests

新增 `tests/contract/test_flet_runtime_contract.py`：

| Test | 驗證 |
|---|---|
| T-F1 `test_run_task_source_uses_run_coroutine_threadsafe` | Flet `page.run_task` 內部走 `run_coroutine_threadsafe`（回傳 cf.Future） |
| T-F1 `test_cf_future_has_no_await` | `concurrent.futures.Future` 沒有 `__await__`（不能直接 shield） |
| T-F2 `test_update_highlights_pre_mount_no_raise` | SummaryPanel pre-mount 不 raise |
| T-F2 `test_update_decisions_pre_mount_no_raise` | 同上 decisions |
| T-F3 `test_set_items_pre_mount_no_raise` | ActionsPanel pre-mount 不 raise |
| T-F3 `test_merge_with_protection_pre_mount_no_raise` | 同上 merge |
| T-F4 `test_append_pre_mount_no_raise` | TranscriptPanel pre-mount 不 raise |
| T-F4 `test_scroll_to_bottom_pre_mount_no_raise` | 同上 scroll |
| T-F8 `test_page_raises_runtime_error_when_not_mounted` | `ft.Container().page` raise RuntimeError |
| T-F8 `test_page_raises_on_custom_control` | `SummaryPanel().page` 同 |

---

## 測試結果

```
161 passed, 1 skipped, 0 failed (29.52s)
```

含 10 個新 contract tests，舊 tests 無 regression。

---

## 碼農 A 配合事項

- `main.py` 建構 `DashboardView(...)` 時新增 `audio_recorder=recorder` 參數
- 碼農 A 正在修 main.py（Bug #13），請順手加上

## V Phase 第六輪驗證要點

1. Bug #14 不再現：按停止 → review 模式 → `update_highlights` 不 raise
2. `grep "if self\.page:" app/ui/` = 0
3. Mic Live 會中：音量條 200ms 更新、四級顏色、靜音警訊
4. Mic Test idle：5 秒倒數 + 純量測 + 不建 session
5. Contract tests 全綠

## 碼農 B 守本分

- 不動 `main.py`（碼農 A 領域）
- 不動 `stream_processor.py`（碼農 A 領域）
- 不動 spec（大統領已更新 ui_spec §8 + system_overview §3.2）
- 所有改動遵循研究者 §6 指引 + 甲方簽核規格
