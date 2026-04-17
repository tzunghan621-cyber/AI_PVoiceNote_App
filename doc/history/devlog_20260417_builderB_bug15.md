---
title: 碼農 B 開發日誌 — Bug #15 DashboardView audio_recorder late binding 修復
date: 2026-04-17
type: devlog
agent: 碼農 B（Builder B）
tags:
  - devlog
  - bug-15
  - late-binding
  - wiring
  - integration-test
related:
  - "[[bug_report_flet_api_20260406]]"
  - "[[verification_report_20260405]]"
  - "[[devlog_20260417_verifier_vphase6]]"
  - "[[devlog_20260417_builderB_bug14_miclive]]"
---

# 碼農 B 開發日誌 — Bug #15 DashboardView audio_recorder late binding 修復

## 任務來源

V Phase 第六輪實驗者靜態複核抓到 Bug #15；大統領裁決採 Verifier 推薦 **方案 A + A1** 組合 + 回應 V6 反思補整合 smoke test。

## 根因摘要

Python name binding + closure late binding 陷阱：

```python
# main.py line 49
recorder: AudioRecorder | None = None  # ← main scope 宣告

# main.py line 246-253（constructor 階段）
dashboard = DashboardView(
    ...,
    audio_recorder=recorder,  # ← 傳入當下 None，dashboard._audio_recorder = None
    ...,
)

# main.py on_start_recording（事件觸發時）
def on_start_recording(title, participants):
    nonlocal recorder
    recorder = AudioRecorder(config)  # ← 只 rebind main scope 的 name
    # dashboard 內部 self._audio_recorder 仍是 None（同一物件不同 reference）
```

結果：
- Mic Live 會中音量條：`_start_level_poll` 第一行 `if not self._audio_recorder: return` → silent
- Mic Test idle 模式：`_handle_mic_test` 同樣 early return → 按按鈕無反應
- 無 log、無錯誤 → 極難 debug

### 為什麼單元/contract 測沒抓到

- Unit：只測單一 class 行為，不測跨模組 wiring
- Contract（T-F1~T-F8）：只測 Flet framework 假設 + panel pre-mount safety
- 兩者都不觸發「main.py 的 on_start_recording → recorder = AudioRecorder()」這條 late binding 路徑

這對應實驗者三輪反思：
| 輪次 | 反思 | 本次回應 |
|---|---|---|
| V4 | 單元綠燈 ≠ 符合 spec | 已在 V5/V6 加 spec-level integration test |
| V5 | spec 綠燈 ≠ 符合 framework runtime | 已在 V6 加 contract test（T-F1/T-F8）|
| **V6** | **contract 綠燈 ≠ 符合跨模組 wiring** | **本次新增 `tests/integration/`** |

---

## Part 1 — 方案 A：DashboardView setter 注入

### 1-A. DashboardView 加 `set_audio_recorder`

**位置：** `app/ui/dashboard_view.py`（`_stop_level_poll` 後面）

```python
def set_audio_recorder(self, recorder: AudioRecorder):
    """外部注入 AudioRecorder（Bug #15 修復）。"""
    self._audio_recorder = recorder
    # 若 Mic Live poll 已在跑，重啟 binding 到新 recorder
    if self._level_poll_running:
        self._stop_level_poll()
        self._start_level_poll()
```

同時加 `from app.core.audio_recorder import AudioRecorder`（用於 type hint；循環檢查：`audio_recorder.py` 不 import UI，安全）。

### 1-B. main.py on_start_recording 呼叫 setter

**位置：** `app/main.py` line 105 後

```python
recorder = AudioRecorder(config)
# Bug #15：把新建 recorder 注入 dashboard（constructor 階段 recorder is None）
dashboard.set_audio_recorder(recorder)
local_recorder = recorder
```

## Part 2 — 方案 A1：Mic Test 內 fallback 臨時建 recorder

idle 階段甲方可能點「測試麥克風」，此時尚未進 `on_start_recording`，
`self._audio_recorder` 永遠是 None（即使 setter 機制已修好，首次 idle 仍未注入）。

**位置：** `app/ui/dashboard_view.py` `_handle_mic_test`

邏輯變動：
1. 不再用 `if not self._audio_recorder or ...: return`，只守 `_level_poll_running`
2. 若 `_audio_recorder is None`：try 建 `temp_recorder = AudioRecorder(self.config)`
3. 記在 `self._mic_test_temp_recorder`（供 `_stop_mic_test` 清理）
4. `active_recorder` 變數統一後續使用（閉包 `_mic_test_loop` 捕獲 active_recorder 而非 `self._audio_recorder`）

`_stop_mic_test` 同步改造：
```python
temp = getattr(self, '_mic_test_temp_recorder', None)
active = temp if temp is not None else self._audio_recorder
if active is not None:
    active.stop_level_probe()
self._mic_test_temp_recorder = None
```

保險：`AudioRecorder(self.config)` 若 raise（config 缺 / sounddevice 缺），silent return 不炸 UI。

---

## Part 3 — Integration smoke test（回應 V6 反思）

**新增目錄：** `tests/integration/`（專案第一個整合測試目錄）
**新增檔案：** `tests/integration/__init__.py` + `tests/integration/test_main_wiring.py`

### 覆蓋的 wiring contract

| Test class | 驗什麼 |
|---|---|
| `TestSetAudioRecorderAPI::test_set_audio_recorder_method_exists` | `DashboardView.set_audio_recorder` 方法存在（公開 API contract，防未來誤刪） |
| `TestSetAudioRecorderAPI::test_dashboard_constructor_leaves_audio_recorder_none_when_passed_none` | 復現 Bug #15 壞狀態（`audio_recorder=None` → `_audio_recorder is None`） |
| `TestSetAudioRecorderAPI::test_set_audio_recorder_updates_internal_ref` | setter 注入後 internal ref 確實更新（核心修復） |
| `TestSetAudioRecorderAPI::test_set_audio_recorder_can_rebind` | 二次呼叫可 rebind（多場錄音） |
| `TestMainWiringContract::test_main_on_start_recording_calls_set_audio_recorder` | **inspect main.py 原始碼**，斷言 `on_start_recording` 函式 body 內有 `dashboard.set_audio_recorder` — 防 regression |
| `TestMicTestFallback::test_handle_mic_test_no_longer_short_circuits_on_none_recorder` | `_audio_recorder is None` 時 `_handle_mic_test` 走 A1 fallback（monkeypatch AudioRecorder 類驗 constructor 被呼叫） |

### 設計要點

- 使用 `MagicMock` 模擬 `ft.Page`（Flet runtime 需 driver，CLI 測試環境無法真建）
- `minimal_config` fixture 讀真實 `config/default.yaml`，避免重新建
- `dashboard` fixture 刻意傳 `audio_recorder=None` 復現 Bug #15 壞狀態作為前置條件
- Mic Test test monkeypatch `dashboard_view.AudioRecorder` 為 `_FakeRecorder`，避免真開 sounddevice

### 為什麼是 inspect 而非執行

`test_main_on_start_recording_calls_set_audio_recorder` 走的是 inspect 路徑（讀 main.py 原始碼字串）：
- 原因：`on_start_recording` 實際執行需要 ML 模組（Whisper / Gemma / ChromaDB）成本高
- 替代：靜態驗 callback body 確實含 `dashboard.set_audio_recorder`
- 若未來 refactor（例如把 recorder 建構搬去別處），此 test fail 提醒 wiring 已變 → trigger 重新 review

---

## Part 4 — pytest marker

**位置：** `pyproject.toml` `[tool.pytest.ini_options]` markers

新增：
```toml
"integration: cross-module wiring smoke tests (main.py glue, DashboardView setter)"
```

### 日常使用

```bash
pytest -m "not slow and not real_audio and not integration" -q   # 快速 unit+contract
pytest -m integration -q                                          # wiring smoke
pytest                                                            # 全跑
```

---

## 測試結果

```
pytest -m "not slow and not real_audio and not integration" -q
→ 140 passed, 28 deselected, 1 warning in 19.61s

pytest -m integration -v
→ 6 passed, 162 deselected, 11 warnings in 7.91s
```

無 regression。

---

## 實機層明確委交實驗者

此次修復**只驗到 wiring 契約層**，未驗實機 GUI 流程。委交實驗者 V Phase 第七輪驗證：

### 必驗項目

| # | 場景 | 預期 |
|---|---|---|
| 1 | 實機啟動 App → idle → 按「🎤 測試麥克風」 | 5 秒倒數音量條顯示 peak dBFS + 顏色分級（非 silent early return） |
| 2 | idle → 開始錄音 → 會中 | 頂部列音量條即時更新（200ms），甲方 Surface Pro 9 環境應仍顯示 ~-52 dBFS 提醒收音異常 |
| 3 | 會中 → 停止 → review → 再開始錄音 | Mic Live 重新綁定到新 recorder（setter 二次呼叫路徑） |
| 4 | 靜音 > 3 秒 | SnackBar 警訊「麥克風訊號極弱，請檢查設定」 |
| 5 | Mic Test 取消按鈕 | 立即停 probe + 隱藏 UI |

### 碼農 B 不碰範圍

- 實機 GUI 驗證（交實驗者）
- 其他 V6 可能抓到的後續 bug（待實驗者第七輪結語）

---

## 規則符合

- ✅ 不改 spec（ui_spec / system_overview / data_schema 皆未動）
- ✅ 不碰 main.py 邏輯以外（只加一行 `dashboard.set_audio_recorder(recorder)`）
- ✅ 分兩個 commit（Bug #15 修復 / integration smoke test + marker）
- ✅ 所有改動對齊研究者既有報告 + 實驗者 V6 反思
