---
title: 開發日誌 2026-04-16 — 實驗者 V Phase 第五輪（Bug #10/#11/#12 修復重驗 + 發現 Bug #13/#14）
date: 2026-04-16
type: devlog
status: complete
author: 實驗者（Verifier）
tags:
  - devlog
  - verifier
  - v-phase
  - v-phase-5
  - bug-10
  - bug-11
  - bug-12
  - bug-13
  - bug-14
  - invariants
related:
  - "[[verification_report_20260405]]"
  - "[[devlog_20260416_builderA_bug11_10_12]]"
  - "[[devlog_20260416_verifier_vphase4]]"
  - "[[pipeline_lifecycle_architecture_20260416]]"
  - "[[system_overview]]"
  - "[[data_schema]]"
  - "[[bug_report_flet_api_20260406]]"
---

# 實驗者 V Phase 第五輪 — Bug #10/#11/#12 修復重驗 — 2026-04-16

> 前一棒：碼農 A [[devlog_20260416_builderA_bug11_10_12]]（Step 1 `c22c1a2` Bug #11 → Step 2 `9c6b96e` Bug #10 → Step 3 `49c54f9` Bug #12），明確委交實機層檢核 6 項。
> 本輪 autonomous 部分（Step 1 + 2）已完成；Step 3/4 實機 + S2/S4/S5/S9 待甲方協同。
> 詳細結果：[[verification_report_20260405#九、V Phase 第五輪]]

---

## 第五輪結果總表

| Step | 任務 | 結果 | 摘要 |
|---|---|---|---|
| 1 | Regression `pytest -m "not slow and not real_audio"` | ✅ PASS | 126 passed / 0 failed / 22 deselected（20.33s） |
| 2 | 靜態複核碼農 A diff 對照研究者 7 invariants | ✅ PASS（1 觀察） | I1-I7 全部對應代碼落地；C1-C8、G1-G7 逐條驗通。Obs-1 exporter.py 小缺口（非阻塞） |
| 3 | 實機 T1 協同甲方（兩次 session） | 🔴 **FAIL** | 兩個新 bug 爆發：Bug #13（`asyncio.shield(page.run_task result)` TypeError）+ Bug #14（`SummaryPanel.update_highlights` mount 前 RuntimeError）。**停止按鈕 UI 無反應、永不切 review**，但資料保全層 ✅（session 仍 save 到 disk） |
| 3a | 實機 T6（Bug #12 log 驗證） | ✅ **PASS** | 整輪含 stop drain + flush 無 `async generator ignored GeneratorExit`。Bug #12 修復實機有效 |
| 3b | 實機 T2/T3/T4/T5 | ⏸ 阻塞 | T1 失敗後續不跑 |
| 4 | S2/S4/S5/S9 GUI smoke | ⏸ 阻塞 | T1 阻塞 |
| 5 | Bug report + verification report + devlog | ✅ | Bug #13/#14 完整章節寫入 [[bug_report_flet_api_20260406]]；V5 結論寫入 [[verification_report_20260405#9]] |

## 靜態複核結論（Step 2 詳情）

相較第四輪抓到的「B1 語意翻轉」（碼農 A 把 cancel 當預設停止路徑），本輪靜態複核**未發現同類 invariant 偏差**。逐條對照：

- **I1**（必落盤）：`main.py:_run.finally` 無條件呼 `_persist_session`，CancelledError/Exception 分支先 `mark_aborted` 再 save ✅
- **I2**（ready 前先 final summary）：`stream_processor.run()` 順序 drain → final → update → mark_ready → on_status_change("ready") → `_on_pipeline_done` save + UI review ✅
- **I3**（cancel 只當安全網）：`_stop_recording_async` 用 `wait_for(shield, 90s)` + `TimeoutError` 才 cancel ✅
- **I4**（summary 不阻塞 audio）：`asyncio.create_task(_run_summary_async)` fire-and-forget + `_summarizing` flag 防連發 ✅
- **I5**（UI mode SSoT = status）：`Session.mode` @property + `_finalize_ui` 讀 status ✅
- **I6**（status 唯一入口）：`SessionManager.transition` 為原子化入口（⚠️ 見下方 Obs-1）
- **I7**（async gen cleanup 不 yield）：`audio_recorder.start` 的 flush 已從 finally 移出到 while 退出後；finally 只剩 stream.stop/close + WAV flush ✅

**C1-C8 / G1-G7 全對齊**，詳見 [[verification_report_20260405#9.2]] 的三張表。

## 本輪新發現（非 bug）

### Obs-1 — exporter.py 的 I6 覆蓋缺口

[exporter.py:15-16](app/core/exporter.py#L15-L16)：

```python
def export(self, session: Session, output_path: str):
    ...
    session.status = "exported"        # ← 直接賦值，未走 transition
    session.export_path = output_path
```

- **嚴重度**：🟩 低 — 不影響資料遺失，不影響 T1-T6 實機路徑（exporter 僅在會後手動匯出時呼叫）
- **類別**：spec-invariant 覆蓋不完整（非 Bug #10/#11/#12 修復範圍）
- **為什麼抓到**：實驗者第四輪反思「拿 spec 當校準尺」— 研究者 §1.4 I6 寫「所有」status 轉換都必須走 transition，exporter 是例外
- **建議**：派工碼農 A 補 `SessionManager.mark_exported(session, path)` helper（需先補 spec：匯出從 `ready` 以外 status 進是否合法？`aborted` 可匯出嗎？）。**不阻塞甲方簽核**
- **為什麼第四輪沒抓到**：第四輪焦點在 Bug #10 資料遺失 / Bug #11 UI 凍結，未掃到匯出路徑；本輪靜態全面 grep `session.status = ` 才浮出

### Obs-2 — 二次按停止無強制逃生

[main.py:187-189](app/main.py#L187-L189) `_stop_recording_async`：

```python
task = pipeline_task
if task is None or task.done():
    return            # 第二次按停止時 task 還在跑 → 也 early return
```

- **嚴重度**：🟩 低 — 研究者 §1.3 T8 有「二次按停作為 cancel 觸發」建議，但不是必需
- **碼農 A devlog 已標**：「由 Reviewer 判斷是否需加」
- **實機驗證路徑**：T5-3 若甲方耐不住 90s 連按停止，會觀察到行為偏離期待 → 可補
- **非阻塞** — T5-3 能靠 90s 後 watchdog 自動 cancel 收斂

## 為什麼靜態沒抓到 Bug #13/#14（本輪反思）

### Bug #13 — Flet `page.run_task` 回傳型別

- **研究者 review 層**：[[pipeline_lifecycle_architecture_20260416]] §2.3 方案 A 建議 `asyncio.wait_for(pipeline_task, timeout)`，但沒寫「pipeline_task 在 Flet 0.84 下是 concurrent.futures.Future 不是 asyncio.Task」這個關鍵差異。這是研究者的漏網之魚
- **碼農 A 測試層**：單元測試用 `asyncio.create_task` 模擬 pipeline_task → `asyncio.shield` 可接受 → 測試通過。生產環境 Flet 不同型別 → 只在實機暴露
- **我自己靜態複核層**：§9.2 表格看到 `_stop_recording_async` 用 `wait_for(shield(task), timeout)` 覺得符合 I3 invariant，沒追問「task 實際型別是什麼」就打 ✅。**我也有責任沒抓到**

### Bug #14 — `self.page` property 在 Flet 0.84 嚴格 lifecycle

- **歷史教訓**：第三輪 Bug #7 已經發生過**完全同類**的問題（`FeedbackView.__init__` 呼 `refresh` → `update`），commit `43932d3` 修了但**沒 grep 全項目其他位置**
- **結果**：`dashboard_view.py` 的 `SummaryPanel.update_highlights` 裡 `if self.page:` 是同類 pattern，這次實機爆出
- **這是第三輪結語「補做 Flet 0.84 Lifecycle 變動清單，掃出所有在 __init__ 或 build 階段就呼叫 update() 的位置」沒被執行的後果**

### 靜態收斂 vs 實機新類

第四輪反思「Test 設計要比對 spec 不只比對實作 intent」在碼農 A 本次 Step 2 測試重寫裡實行（`test_recording_normal_completion_saves_as_ready` 直接斷言 `session.status == "ready"` 並驗 `session_mgr.load` 落盤，這是 spec-level）。**這個層面的反思已收斂**。

但本輪實機暴露**新一類漏抓**：
- Bug #13 類 — 單元測試的 mock 和生產環境 runtime 型別差異
- Bug #14 類 — 歷史 bug 的同類 pattern 沒被全面掃

這些不是 invariants 層面的偏差，而是「spec 正確、invariants 正確、實作**看起來**符合 invariants、但 framework runtime 行為讓實作炸」的 Flet 整合類 bug。

**建議未來派工要求**：
- 研究者 review 涉及 Flet 層代碼時，必須查 Flet 對應版本的 API signature 與 runtime 行為
- Bug fix commit 必須附 `grep` 命令證明同類 pattern 全掃完（例如第三輪結語要求的 `\.update\(\)` 與 `if self.page` 類）

## 交棒（最終）

| 對象 | 請求 |
|---|---|
| **大統領** | 派工 (1) 碼農 A 修 Bug #13（輪詢方案 A 推薦）+ 順手 Obs-1/2/3；(2) 碼農 B 修 Bug #14（全面 grep `if self.page:` pattern）；(3) 研究者補 Flet 0.84 async bridge + lifecycle 完整映射研究 |
| **甲方** | (1) 排查 Windows 麥克風設定（Obs-4，peak -52dBFS 需拉增益或換 device）；(2) 修完 #13/#14 後協同 V Phase 第六輪 T1-T6 + S2/S4/S5/S9 |
| **碼農 A** | 詳見 [[bug_report_flet_api_20260406#Bug #13]]「修復方向建議」。單元測試要能 catch Flet future vs asyncio.Task 差異 — 建議加 integration test 或用 mock Flet-style future |
| **碼農 B** | 詳見 [[bug_report_flet_api_20260406#Bug #14]]「修復方向建議」方案 C。grep 清單示意：`grep -rn "if self.page" app/ui/` 找出所有候選 + 在建構/初始化路徑上的 `.update()` 呼叫 |
| **研究者** | 需要的話補一份獨立 research（類似 [[pipeline_lifecycle_architecture_20260416]]），主題：Flet 0.84 async bridge 與 lifecycle。應列出 `page.run_task` 回傳型別與 asyncio bridge 方案、`BaseControl.page` property 的 strict lifecycle 所有影響範圍、其他第三輪結語提過但未執行的 grep pattern |

> 實驗者簽核：第五輪 autonomous（regression + 靜態）綠燈；實機 **FAIL** 發現 Bug #13 + #14。Bug #10/#11/#12 資料保全層 ✅，Bug #12 實機 ✅。Desktop 版本**不可**進甲方最終簽核，需修完 Bug #13/#14 後 V Phase 第六輪再驗。

---

## 實機協同詳記（2026-04-16 晚間）

### 環境預檢

- Ollama 0.20.2 + `gemma4:e2b` 7.2GB 模型 ready
- `data/sessions/` 空（新）
- `data/temp/` 含上次殘留 `chunk_0000.wav` + 舊 `錄製.m4a`
- App 啟動方式：`python -u -m app.main 2>&1 | tee doc/reports/vphase5_raw_round2.log | grep ...`
  - tee 完整捕獲原始 log（保留 Traceback stack 完整性）
  - Monitor 寬 filter 抓 TypeError/AttributeError/Error:/Traceback/transition/... 等關鍵字事件

### 第一次 session（`b90ad044-cdce-4309-97a0-b37057985b50`）

甲方按開始錄音 → 錄了約 63 秒 → 按停止。
- UI「停止按鈕沒反應」，甲方描述「按了錄音還在繼續」
- 背景 log：`transition: recording → processing` → Ollama POST 200 OK → `transition: processing → ready`
- Session 最終 save 到 disk：`data/sessions/b90ad044-cdce-4309-97a0-b37057985b50.json`（2400 bytes）
- 檢查 JSON：status=ready, mode=review（@property 衍生對）, segments=[], summary.is_final=true, summary.fallback_reason=null, **但 summary.highlights="（請在此處填入會議的主要討論主題和核心發現）"**（Gemma 吐 placeholder，因為 segments 空）
- 原始 log 當時 grep filter 太窄，Traceback 只抓到首行，未能立即定位 root cause

### 第二次 session（`61d54954-93b0-464c-a29d-19d773dcad68`）

甲方重開 App、改用**寬 filter + tee 完整 log**策略後重跑。
- 甲方依指示不切左側分頁，持續發聲講話
- log 顯示連續 10 秒 chunks 全被 VAD filter 100% 過濾：
  ```
  INFO:faster_whisper:Processing audio with duration 00:10.010
  INFO:faster_whisper:VAD filter removed 00:10.010 of audio
  ```
- 驗證「甲方確實在大聲講話」後，分析 `data/temp/chunk_0000.wav`（上次 session 留下的實體音訊檔）：
  ```
  sample_rate: 16000 Hz, mono, int16, duration: 105.82s
  max_abs: 80   (int16 滿幅 ±32768，僅用 0.24%)
  peak_dBFS: -52.2   (正常說話應 -20 ~ -10 dBFS)
  ```
- **結論**：Surface Pro 9 內建麥克風實際輸入振幅極低（近雜訊底噪），VAD 全過濾是訊號的合理行為。**非 App bug**，甲方側環境問題（Obs-4）
- 甲方按停止 → 仍「沒反應」 → Bug #13 重現
- 背景 log：`transition: recording → processing` → 200 OK → `transition: processing → ready` → RuntimeError（Bug #14）
- Session 最終 save：`data/sessions/61d54954-93b0-464c-a29d-19d773dcad68.json`（5301 bytes）

### Bug #13 完整 Traceback（tee 捕獲）

```
ERROR:concurrent.futures:exception calling callback for <Future at 0x2d0db2ecc90 state=finished raised TypeError>
Traceback (most recent call last):
  File "...\concurrent\futures\_base.py", line 340, in _invoke_callbacks
    callback(self)
  File "...\flet\controls\page.py", line 748, in _on_completion
    raise exception
  File "...\app\main.py", line 191, in _stop_recording_async
    await asyncio.wait_for(asyncio.shield(task), timeout=stop_drain_timeout_sec)
  File "...\asyncio\tasks.py", line 884, in shield
    inner = _ensure_future(arg)
  File "...\asyncio\tasks.py", line 674, in _ensure_future
    raise TypeError('An asyncio.Future, a coroutine or an awaitable is required')
TypeError: An asyncio.Future, a coroutine or an awaitable is required
```

**根因**：`task = page.run_task(_run)` — Flet 0.84 的 `page.run_task` 回傳 `concurrent.futures.Future`（跨 thread asyncio bridge），不是 `asyncio.Task`；`asyncio.shield._ensure_future` 只接受 asyncio awaitable → TypeError。

**影響**：停止按鈕 UI 無反饋；I3 watchdog 失效（但 `recorder.request_stop()` 先於 shield 已成功 → audio gen 自然退 → session 仍走到 ready）。

**未抓到原因**：
- 碼農 A 單元測試用 `asyncio.create_task(coro)` 模擬 pipeline_task → shield 可接受 → 測試通過
- 生產環境 Flet 下型別不同 → 只在實機暴露
- 研究者 [[pipeline_lifecycle_architecture_20260416]] §2.3 方案 A 建議 `asyncio.wait_for(pipeline_task, ...)` 但沒驗 Flet 0.84 下 `page.run_task` 回傳型別 — **研究者架構 review 的漏網之魚**

### Bug #14 完整 Traceback（tee 捕獲）

```
ERROR:__main__:Recording pipeline error
Traceback (most recent call last):
  File "app\main.py", line 114, in _run
    await processor.run(local_recorder.start(), session)
  File "app\core\stream_processor.py", line 149, in run
    self.on_status_change("ready")
  File "app\main.py", line 109, in <lambda>
    processor.on_status_change = lambda s: _on_pipeline_done(session) if s == "ready" else None
  File "app\main.py", line 212, in _on_pipeline_done
    dashboard.set_mode("review", session)
  File "app\ui\dashboard_view.py", line 377, in set_mode
    self._build_review()
  File "app\ui\dashboard_view.py", line 571, in _build_review
    self.summary_panel.update_highlights(self._session.summary.highlights)
  File "app\ui\dashboard_view.py", line 178, in update_highlights
    if self.page:
  File "flet\controls\base_control.py", line 279, in page
    raise RuntimeError(
RuntimeError: SummaryPanel(203) Control must be added to the page first
```

**根因**：[dashboard_view.py:561-571](app/ui/dashboard_view.py#L561-L571) `_build_review()` 剛 `new SummaryPanel()` 就立刻呼叫 `update_highlights` → 其內 `if self.page:` 在 Flet 0.84 下（`BaseControl.page` property 嚴格 lifecycle）未 mount 時 **raise RuntimeError**（不 return None）。

**影響**：`dashboard.set_mode("review")` 炸 → UI 永不切 review；RuntimeError 冒出到 `_run.except Exception` 被誤記為「Recording pipeline error」。

**未抓到原因**：第三輪 Bug #7 commit `43932d3` 修 `FeedbackView` 時只修該檔，沒 grep `if self.page:` pattern 全面掃 — 派**碼農 B** 本次要一次掃乾淨。

### Bug #13 + #14 連鎖效應

| 步驟 | 結果 |
|---|---|
| 甲方按停止 → `_stop_recording_async` request_stop OK → shield TypeError（#13） | UI 無反應；recorder flag 已設 |
| 背景 audio gen 退出 → processor.run 走完 final summary → mark_ready | session.status=ready |
| `on_status_change("ready")` → `set_mode("review")` → RuntimeError（#14） | UI 永停 live |
| `_run.except Exception` 抓到 → log "Recording pipeline error" | 但 session.status 已是 "ready"，不走 mark_aborted |
| `finally` → `_persist_session`（冪等）+ `request_stop`（冪等） | **I1 ✅ disk 有檔** |
| `if session.status != "ready": _finalize_ui` 擋住 | UI 永遠不進 review |

**I1 + Bug #12 守住資料** — 兩次 session 都落盤、summary.is_final=True（雖為 placeholder）、無資料遺失、無 `async generator ignored GeneratorExit` warning。

**但 UI 層完全不閉環** — 甲方使用體感是壞掉的。
