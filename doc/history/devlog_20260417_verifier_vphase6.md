---
title: 開發日誌 2026-04-17 — 實驗者 V Phase 第六輪（Bug #13/#14 修復 + Mic Live 新增 重驗）
date: 2026-04-17
type: devlog
status: active
author: 實驗者（Verifier）
tags:
  - devlog
  - verifier
  - v-phase
  - v-phase-6
  - bug-13
  - bug-14
  - bug-15
  - mic-live
  - contract-tests
related:
  - "[[verification_report_20260405]]"
  - "[[devlog_20260417_builderA_bug13]]"
  - "[[devlog_20260417_builderB_bug14_miclive]]"
  - "[[flet_0.84_async_lifecycle_20260417]]"
  - "[[ui_spec]]"
  - "[[bug_report_flet_api_20260406]]"
---

# 實驗者 V Phase 第六輪 — Bug #13/#14 修復 + Mic Live 新增 重驗 — 2026-04-17

> 前一棒：
> - 研究者 [[flet_0.84_async_lifecycle_20260417]]（第三篇 Flet 研究，給 Bug #13/#14 修復條件）
> - 碼農 A（commit `f6dc568`）修 Bug #13：方案 A 輪詢取代 `asyncio.shield(cf.Future)`
> - 碼農 B（commit `481b36e` + `458ae75` + `edcb35a`）修 Bug #14 全面掃清假守衛 + 實作 Mic Live 新功能
> - 單元 + contract tests：140 passed
>
> 本輪 autonomous 已完成（Step 1 regression + Step 2 靜態複核 + 產出報告）；Step 3-7 實機待甲方協同。
> 詳細結果：[[verification_report_20260405#十、V Phase 第六輪]]

---

## 第六輪 autonomous 結果總表

| Step | 任務 | 結果 | 摘要 |
|---|---|---|---|
| 1 | Regression `pytest -m "not slow and not real_audio"` | ✅ PASS | 140 passed / 0 failed（相對 V5 baseline 126 → +14 個 contract + lifecycle tests） |
| 2a | 靜態複核 Bug #13 修復（碼農 A） | ✅ PASS | 方案 A 輪詢對齊研究者 §5；無 asyncio.shield/wait_for/await on cf.Future；Phase 2 10s 硬 timeout 防死鎖 |
| 2b | 靜態複核 Bug #14 修復（碼農 B） | ✅ PASS | `grep "if self\.page:" app/ui/` = 0 匹配；`_mounted` pattern 覆蓋 5 UI 檔 45 處 |
| 2c | 靜態複核 Mic Live 實作對齊 ui_spec §2.5（碼農 B Part 2） | ✅ 對齊 | AudioRecorder level API + rolling buffer + 四級顏色 + Mic Test 5 秒倒數。實機待驗 |
| 2d | Contract tests 認證 | ✅ 齊全 | T-F1/F2/F3/F4/F8 10 條全綠；T-F5/F6 以碼農 A 的 `_FakeCfFuture` 融入 |
| 2e | **靜態發現 Bug #15 候選** | 🔴 | DashboardView `audio_recorder` late-binding → Mic Live + Mic Test 實機將 dead |
| 3-7 | 實機 T1-T6 + Mic Live + S2/S4/S5/S9 | ⏳ 待甲方協同 |
| 產出 | verification_report §10 + 本 devlog | ✅ |

## 靜態複核結論

### Bug #13 修復 ✅

碼農 A 選方案 A（輪詢），對齊研究者 §5 推薦。[main.py:176-217](app/main.py#L176-L217) `_stop_recording_async` 兩階段：

- **Phase 1**：`while not task.done()` + `loop.time() >= deadline` → `task.cancel()` + break；正常 drain 期間每 200ms `await asyncio.sleep(0.2)` 不卡 event loop
- **Phase 2**：cancel 後等 task 真完成，10s 硬 timeout 防極端死鎖

**關鍵**：整段不碰 `asyncio.shield / wait_for / await task / wrap_future` — 完全避開 asyncio↔cf.Future bridge 假設。`task.cancel()` 仍是 cf.Future 原生 API，`run_coroutine_threadsafe` 特化版會 propagate 到底層 asyncio task（研究者 §1.3 實測確認）。

### Bug #14 修復 ✅

`grep "if self\.page:" app/ui/` = **0 匹配**。`_mounted` 遍佈：
- `dashboard_view.py` 25 處（含 Panel 三兄弟 + DashboardView 本身）
- `main_view.py` 7 處（StatusBar）
- `settings_view.py` 5 處（含 `hasattr` 假守衛也清掉）
- `terms_view.py` 4 處
- `feedback_view.py` 4 處

**滿足 ui_spec §8 UI Mount Lifecycle 守則**：所有 custom control `__init__` 加 `_mounted = False`；`did_mount` / `will_unmount` 維護；update-before-mount 全改 `if self._mounted:` 或純賦值等待首次 render。

### Mic Live 對齊 ui_spec §2.5 ✅（靜態）

[audio_recorder.py:19-85](app/core/audio_recorder.py#L19-L85) 新增：
- `_level_ring: deque[float]` + `_current_dbfs`
- `_audio_callback` 同時 put queue + `_update_level`（正常錄音路徑共用）
- `_probe_callback` 純 level 更新（Mic Test 路徑）
- `get_current_level()` / `start_level_probe()` / `stop_level_probe()`

Dashboard 側 `_update_mic_level_ui` / `_handle_mic_test` / `_stop_mic_test` 實作四級顏色 + 靜音警訊 + 5 秒倒數。**但因 Bug #15，實機將無法運作**（見下）。

### Contract tests ✅

T-F1（cf.Future 型別契約）+ T-F2/F3/F4（三 Panel pre-mount safety）+ T-F8（BaseControl.page 未 mount raise）共 10 條。每一條都是「框架契約守護」—— Flet 升版改契約就 fail，trigger researcher 重新 review。**這層是研究者 §7「framework contract test」主張的首次落地**，Verifier 接受為 V6 充分覆蓋。

## 本輪新發現 — Bug #15 候選

### 根因（靜態推論）

兩碼農並行協作的 glue gap：

```python
# main.py line 49-51
recorder: AudioRecorder | None = None    # ← main() 開場，recorder = None

# main.py line 246-253
dashboard = DashboardView(..., audio_recorder=recorder, ...)
#          ↑ 此時傳入 None，dashboard._audio_recorder = None

# main.py line 105（on_start_recording 觸發時）
recorder = AudioRecorder(config)   # ← rebind main scope 的 local `recorder` name
#          ↑ 不會改 dashboard._audio_recorder（它已存住 None）
```

**沒有 `set_audio_recorder()` setter**（grep 確認）。

### 為何兩個碼農都沒抓到

- 碼農 B devlog Part 2 明確寫「main.py 建構 DashboardView(...) 時新增 `audio_recorder=recorder` 參數，碼農 A 正在修 main.py（Bug #13），請順手加上」
- 碼農 A commit `edcb35a` 標題「main.py DashboardView 建構補 audio_recorder 參數」— 確實加了 `audio_recorder=recorder` 參數位
- **但兩人都沒驗「加在 main() 頂部的 recorder 當時是 None」這個 Python name binding 細節**
- 單元測試不測 late-binding 閉包互動；contract test 不測這類跨模組生命週期問題

### 為何 Verifier 抓到

V6 靜態 grep `set_audio_recorder` → 0 匹配 → 推論 dashboard 一旦拿到 None 就永遠 None → 配合 `on_start_recording` 的 rebind 行為 → 推出 Bug #15。

這一層是「**跨模組生命週期靜態推論**」，第四輪反思「單元綠燈 ≠ 符合 spec」+ 第五輪反思「spec 綠燈 ≠ 符合 framework runtime」之後，第六輪反思補充：**contract test 綠燈 ≠ 符合跨模組 wiring**。

### 實機影響

- [dashboard_view.py:796](app/ui/dashboard_view.py#L796) 會中 Mic Live poll 首行 `if not self._audio_recorder: return` → 音量條永不更新
- [dashboard_view.py:828](app/ui/dashboard_view.py#L828) idle Mic Test `if not self._audio_recorder or ...: return` → 按鈕按下無反應
- [dashboard_view.py:860](app/ui/dashboard_view.py#L860) `self._audio_recorder.start_level_probe()` 根本到不了

**非阻塞 Bug #13/#14 核心**：T1 正常錄音 → processor 自己建立 recorder 生命週期，跟 dashboard._audio_recorder 無關。所以 T1 仍可驗 Bug #13（停止有反應）+ Bug #14（UI 切 review 不炸）。

### 修復建議

**方案 A（推薦）** — 加 setter（改動最小）：
- dashboard_view.py 加 `set_audio_recorder(recorder)` method
- main.py `on_start_recording` 在 `recorder = AudioRecorder(config)` 之後 call `dashboard.set_audio_recorder(recorder)`
- idle Mic Test 另解：app 啟動時預建一個 recorder instance 給 dashboard，或 `_handle_mic_test` 內臨時建

**方案 B** — 預建 recorder：
- main.py 開場就 `recorder = AudioRecorder(config)`，Dashboard 建構拿到有效 reference
- 缺點：app 啟動就 instantiate AudioRecorder（目前看無副作用，可接受）

**派工建議**：碼農 A 或 B 任一人，幾行改完。獨立 PR 或併入 Bug #13/#14 後續補丁皆可。

## 反思 — 三輪累積的新測試層

| 輪次 | 發現的 gap | 補的測試層 |
|---|---|---|
| V4 反思 | 單元綠燈 ≠ 符合 spec | V5 碼農 A 補 spec-level invariants tests（14 個） |
| V5 反思 | spec 綠燈 ≠ 符合 framework runtime | V6 碼農 A/B 補 contract tests（10 個 T-F*） |
| **V6 反思** | **contract 綠燈 ≠ 符合跨模組 wiring** | **未補（建議加 integration smoke test）** |

**建議 V7（若需要）**：加 `tests/integration/test_main_wiring.py`，測 main.py 建構 DashboardView 時各 dependency（kb/recorder/processor/...）是否正確接上。具體用 smoke-style：跑 `main(fake_page)` 一次、檢查 `dashboard._audio_recorder` 不為 None 等關鍵 wiring。

但若 V6 實機 T1/#13/#14 全過 + Bug #15 被快速補掉，可不急開 V7；此反思 log 留給未來參考即可。

## 實機協同計畫（Step 3-7）

### 建議順序

**先 T1/T6 驗 Bug #13/#14 核心（主戰場）**：

1. 啟 App + Monitor log（寬 filter + tee 完整 log 路線，V5 驗證有效）
2. 甲方按「開始錄音」→ 填會議資訊 → 錄 5+ 分鐘（跨 180s 第一次 summary + 跨 360s 第二次）→ 按停止
   - 驗 Bug #13：停止按鈕立即反饋、log 無 `TypeError: An asyncio.Future...`
   - 驗 Bug #14：UI 自動切 review、log 無 `Control must be added to the page first`
   - 驗 I1：`data/sessions/{id}.json` 存在、status=ready
   - 驗 I4：跨 summary 觸發點逐字稿不凍結 > 15s
   - 驗 Bug #12 回歸：log 無 `async generator ignored GeneratorExit`
3. 切左側「詞條」「回饋」「設定」分頁 → 驗 Bug #14 同類殘留全掃清（Lazy view lifecycle）

**再 Mic Live（Bug #15 驗收）**：

4. 點 idle「🎤 測試麥克風」按鈕 → 預期倒數 + 音量條動 + peak dBFS 文字
   - 若 **dead**（按鈕無反應）→ 確認 Bug #15，回報大統領快速派工補
   - 若意外 work → Bug #15 推論錯誤，我補更仔細的 post-mortem
5. 錄音中觀察頂部列 Mic Live 音量條 + 四級顏色
   - 甲方需先排查麥克風設定（V5 Obs-4 peak -52 dBFS），讓訊號進正常範圍
6. 若 Mic Live 運作 → 測靜音 > 3 秒 SnackBar 警訊

**最後 S2/S4/S5/S9**：

7. S2 響應式佈局 / S4 對話框 / S5 SnackBar（含 fallback + Mic Live 警訊）/ S9 拖動切換

### Invariants I1-I7 實機覆蓋目標

| Invariant | 實機驗證方式 |
|---|---|
| I1（必落盤） | 停止後 `data/sessions/` 有檔 + `load` 回得來 |
| I2（ready 前 final summary） | UI 真的切到 review（V5 因 Bug #14 這條表象成立但 UI 不閉環） |
| I3（cancel 只在真卡死） | 正常停止走 drain、log 無 `"forcing cancel (watchdog safety net)"` |
| I4（summary 不 block transcribe） | 跨 180s summary 觸發時逐字稿仍產（不凍結 > 15s） |
| I5/I6（SSoT=status） | session JSON status=ready、mode=review（衍生對）、無直接賦值 |
| I7（async gen cleanup 不 yield） | log 無 `async generator ignored GeneratorExit` |

## 未做（守 Verifier 本分）

- ❌ 不改 code（Bug #15 只提建議不動手）
- ❌ 不改 spec（ui_spec §2.5 + §8 由大統領處理）
- ❌ 不指派具體實作細節（修法方案 A/B 碼農自選）
- ❌ 不 commit 文件變更（交棒大統領簽核）

## 交棒

| 對象 | 請求 |
|---|---|
| **大統領** | (1) 裁決 Bug #15 修復優先級：建議 Verifier 協同甲方跑完 T1/#13/#14 核心驗證後，甲方若需驗 Mic Live 再快速派工補；(2) 實機協同時段安排 |
| **甲方（協同時）** | 依 §10.4 建議順序跑；Mic Test 點下去若 dead 直接回報 — 快速驗證 Bug #15；**錄音前請先排查 Windows 麥克風設定**（V5 Obs-4 peak -52 dBFS 需提升到 -20~-10） |
| **碼農 A 或 B** | Bug #15 補 `set_audio_recorder` setter（方案 A），或改 main.py 預建 recorder（方案 B）— 大統領派 |
| **研究者** | 目前待命。若 V6 實機還有未預期的 framework 或 lifecycle 問題，可能需第四篇研究（目前不預期） |

> 實驗者簽核：V6 autonomous（regression + 靜態複核 + contract tests）全綠 + 發現 Bug #15 候選（跨模組 wiring 靜態推論）。實機 T1-T6 + Mic Live + S2/S4/S5/S9 **待甲方協同後補 §10 章節最終結論**。若 Bug #13/#14 實機通過 + Bug #15 快速補完 + Mic Live 驗證過 → 建議大統領送甲方最終簽核，Desktop 版本 ready for delivery。
