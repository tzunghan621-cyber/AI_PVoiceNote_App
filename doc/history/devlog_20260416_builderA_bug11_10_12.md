---
title: 開發日誌 2026-04-16 — 碼農 A 修 Bug #11 / #10 / #12（Pipeline Lifecycle 架構重寫）
date: 2026-04-16
type: devlog
status: active
author: 碼農 A（Builder A）
tags:
  - devlog
  - builder-a
  - bug-10
  - bug-11
  - bug-12
  - pipeline-lifecycle
  - summarizer-concurrency
  - async-generator
related:
  - "[[devlog_20260416_researcher_pipeline_arch]]"
  - "[[devlog_20260416_verifier_vphase4]]"
  - "[[devlog_20260416_builderA_bug9]]"
  - "[[pipeline_lifecycle_architecture_20260416]]"
  - "[[system_overview]]"
  - "[[data_schema]]"
  - "[[bug_report_flet_api_20260406]]"
---

# 碼農 A — Bug #11 / Bug #10 / Bug #12 修復 — 2026-04-16

> 前一棒：研究者 [[devlog_20260416_researcher_pipeline_arch]]（7 invariants + 3 option 選型 + 7 spec gaps）→ 甲方簽 G1 → 大統領更新 specs（commit f56bb6a）→ 派工到我。
> 脈絡：Bug #9 我用 `pipeline_task.cancel()` 當預設停止路徑，實驗者第四輪實機跑 5+ 分鐘發現三連爆（[[devlog_20260416_verifier_vphase4]]）。本次依研究者架構 review 重寫。
> Spec SSoT：[[pipeline_lifecycle_architecture_20260416]]（invariants）+ [[system_overview]] §4.2/§6 + [[data_schema]] §5/§8

---

## 執行順序（依研究者建議）

研究者強烈建議 #11 → #10（# 11 先修，才能實機跑滿 5 分鐘重現 #10 drain 路徑）。#12 在 #10 PR 中併入。

我遵循單獨 commit 方式方便 Reviewer 逐階段審：

| Step | Bug | Commit | 檔案變動數 | 新 tests |
|---|---|---|---|---|
| 1 | #11 Summarizer fire-and-forget | `c22c1a2` | 3 | +4 |
| 2 | #10 Session aborted + stop 語意 | `9c6b96e` | 8 | +8 |
| 3 | #12 async gen finally yield | `49c54f9` | 2 | +2 |

最終 baseline：**147 passed, 1 skipped**（baseline 133 → +14 新增）

---

## Step 1 — Bug #11 Summarizer fire-and-forget（commit c22c1a2）

### 根因回顧
[stream_processor.py](app/core/stream_processor.py) 主迴圈 `await self.summarizer.generate(...)` 讓整個主迴圈（含 audio_source consume）停在這行 30-90 秒（Gemma E2B CPU 推理時長）。上游 async gen 沒人 consume → 逐字稿 UI 凍結 → 甲方以為掛了按停止 → 觸發 Bug #10。

### Diff 位置 + 變動邏輯

| 檔 | 位置 | 變動 |
|---|---|---|
| [app/core/stream_processor.py](app/core/stream_processor.py) | `__init__` | 新增 `self._summary_task: asyncio.Task \| None = None`、`self.pending_summary_wait_sec` |
| 同上 | 新增 `_run_summary_async` | 包 summarizer.generate + session_mgr.update_summary + on_summary；try/except 保護，例外只 log 不 propagate；finally 重置 `_summarizing=False` |
| 同上 | 主迴圈 L54-L69（舊） | 把 inline `await self.summarizer.generate(...)` 改為 `asyncio.create_task(self._run_summary_async(...))`；fire 前 snapshot `list(session.segments)` + `session.summary` 避免 task 執行期間 state 變動 |
| 同上 | 新增 `_drain_pending_summary` | audio_source 耗盡後 `asyncio.wait_for(asyncio.shield(task), pending_summary_wait_sec)`；timeout 則 cancel pending，供 Step 2 的 final fallback 判斷 |
| [config/default.yaml](config/default.yaml) | `streaming` 區塊 | 新增 `pending_summary_wait_sec: 60`、`final_summary_timeout_sec: 120`、`stop_drain_timeout_sec: 90`（對齊 [[data_schema#8. 設定檔]]） |

### 對應 invariants
- **I4**（summary 不阻塞 audio consume）— 主迴圈不再 await summary.generate
- **C7**（summary 例外不炸主迴圈）— `_run_summary_async` 內部 try/except 吞例外只 log
- **C6**（單一 pending summary）— `_summarizing` flag 在 create_task 前設 True、task finally 重置；第二次週期若前次未完則 `not self._summarizing` 擋掉
- **§3.4 停止期 pending 規則** — `_drain_pending_summary` 等 `pending_summary_wait_sec` → 超時 cancel

### Spec-level tests
| Test | 驗證 |
|---|---|
| `test_summarizer_does_not_block_transcription` | I4：slow summary 期間主迴圈仍產出新 segment（差值 ≥ 1） |
| `test_summarizer_failure_does_not_crash_pipeline` | C7：summary 拋 RuntimeError 後 pipeline 仍進 final + mark_ready |
| `test_stop_during_summarization_waits_for_pending` | §3.4 rule 1：pending 未超時 → drain 等完成 |
| `test_stop_drain_timeout_cancels_pending_summary` | §3.4 rule 2：pending 超時 → cancel + 仍進 final |

---

## Step 2 — Bug #10 Session aborted + stop 語意重寫（commit 9c6b96e）

### 根因回顧
Bug #9 我把 `pipeline_task.cancel()` 當成預設停止路徑（安全網語意被翻轉）→ CancelledError 跳過 `processor.run()` 末段（end_recording → final summary → mark_ready）→ `_on_pipeline_done` 從未被呼叫 → `session_mgr.save` 沒跑 → **data/sessions/ 空白，3 分 20 秒錄音全滅**。

### Diff 位置 + 變動邏輯

#### A. 資料結構（G1 + G4）
| 檔 | 位置 | 變動 |
|---|---|---|
| [app/core/models.py](app/core/models.py) | `SummaryResult` | 新增 `fallback_reason: str \| None = None`（對應 [[system_overview]] §4.2） |
| 同上 | `Session` | 移除 `mode` field（改 @property，`mode = "live" if status in (recording, processing) else "review"`）；新增 `abort_reason: str \| None = None` |

#### B. SessionManager API（I6）
| 檔 | 位置 | 變動 |
|---|---|---|
| [app/core/session_manager.py](app/core/session_manager.py) | 新增 `transition(session, new_status, abort_reason=None)` | 原子化：檢查 status 合法性（含新加 `aborted`）；`aborted` 必帶 reason；轉 processing/ready/aborted 時若 `ended` 為 None 補時間戳；log 記錄轉換 |
| 同上 | `end_recording` / `mark_ready` / 新 `mark_aborted` | 皆改走 `transition`，不直接賦值 `session.status` |
| 同上 | `save` | 冪等；手動注入 `mode`（因 @property 不在 asdict 內） |
| 同上 | `_dict_to_session` / `list_sessions` | 移除 `mode` kwargs（不可當 ctor arg）；list 的 mode 由 status 衍生；讀 `abort_reason` 與 `fallback_reason` |

#### C. StreamProcessor 收尾（I2 + G2 + §6 降級原則）
| 檔 | 位置 | 變動 |
|---|---|---|
| [app/core/stream_processor.py](app/core/stream_processor.py) | `__init__` | 新增 `self.final_summary_timeout_sec` |
| 同上 | 新增 `_run_final_summary` | `asyncio.wait_for(summarizer.generate(..., is_final=True), final_summary_timeout_sec)`；`TimeoutError` → fallback `"ollama_timeout"`；其他 Exception → `"ollama_failure"` 或 `"pending_summary_timeout"`（若前一步 pending 超時）；**CancelledError re-raise 讓 main.py `_run` 轉 aborted** |
| 同上 | 新增 `_build_fallback_final` | 有最近週期版 → 複用 highlights/action_items/... + `is_final=True` + `fallback_reason`；無則產空殼 "(摘要生成失敗，已保留逐字稿供手動整理)" |
| 同上 | `run()` 收尾 | `pending_cancelled = await self._drain_pending_summary()` → `_run_final_summary(session, pending_cancelled)` → `update_summary` → `mark_ready`（仍是 ready，不是 aborted — 降級而非崩潰） |

#### D. AudioRecorder 軟停止（G5）
| 檔 | 位置 | 變動 |
|---|---|---|
| [app/core/audio_recorder.py](app/core/audio_recorder.py) | `stop` → `request_stop` | rename；docstring 註明語意（設旗標，while 下一輪退出；真阻塞用 wait_stopped — 本 PR 未加，視 Reviewer 要求決定） |
| [tests/test_audio_recorder.py](tests/test_audio_recorder.py) | 全部 | 呼叫點改為 `request_stop` |

#### E. main.py 停止路徑重寫（I1 + I2 + I3 + I5）
| 檔 | 位置 | 變動 |
|---|---|---|
| [app/main.py](app/main.py) | 新增 `_finalize_ui` | UI mode 由 `session.status` 驅動（I5）：`ready` → review；`aborted` 有 segments → review(partial)，無 segments → idle |
| 同上 | 新增 `_persist_session` | 包 save + logger.exception（I1 保證） |
| 同上 | `on_start_recording._run` | try → 正常；CancelledError → `mark_aborted(stop_timeout)` + re-raise；Exception → `mark_aborted(pipeline_error)`；**finally 無論如何 save + request_stop + finalize_ui** |
| 同上 | `on_import_audio._run` | 同上（無 recorder） |
| 同上 | `on_stop_recording` | 不再直接 `pipeline_task.cancel()`；改 `page.run_task(_stop_recording_async)` |
| 同上 | 新增 `_stop_recording_async` | `await recorder.request_stop()` → `asyncio.wait_for(asyncio.shield(pipeline_task), stop_drain_timeout_sec)` → `TimeoutError` 才 `task.cancel()`（I3 安全網） |

### 對應 invariants

| Invariant | 實作點 |
|---|---|
| **I1**（任何路徑必落盤） | `_run.finally` 呼叫 `_persist_session`（冪等）；`mark_aborted` 後 save |
| **I2**（ready 前先完成 final summary） | `stream_processor._run_final_summary` 在 mark_ready 前產生（即使 fallback 也是有 final） |
| **I3**（cancel 只當安全網） | `_stop_recording_async` 只在 `stop_drain_timeout_sec` 超時才 cancel |
| **I5**（UI mode SSoT = status） | `_finalize_ui` 讀 `session.status` 決定 UI；`Session.mode` 為 @property |
| **I6**（status 轉換唯一入口） | 所有路徑走 `session_mgr.transition / mark_ready / mark_aborted / end_recording`；不再有 `session.status = "..."` 直接賦值 |
| **G1**（aborted + abort_reason） | `Session.abort_reason`；transition 驗證必填 |
| **G2**（final summary fallback） | `_run_final_summary` + `_build_fallback_final` + `SummaryResult.fallback_reason` |
| **G4**（mode 衍生自 status） | `Session.mode` @property |
| **G5**（recorder 軟停止命名） | `request_stop` rename |

### Spec-level tests

Bug #9 regression 測試依實驗者第四輪批評「驗 pattern 不驗 spec」重寫 — `_recording_run`/`_import_run` helper 接受真 `SessionManager` + 真 `Session`，斷言 `session.status` / `abort_reason` / `session_mgr.load` 結果，而非 `on_reset_idle` 被呼叫次數。

| Test | Invariant |
|---|---|
| `test_recording_normal_completion_saves_as_ready` | I1 + I2 |
| `test_recording_exception_transitions_aborted_with_reason` | I1 + G1 |
| `test_recording_cancel_transitions_aborted_stop_timeout` | I3 + G1 |
| `test_recording_exception_message_non_empty_for_snackbar` | Bug #9 A2 共存 |
| `test_import_exception_transitions_aborted_and_saves` | I1（匯入路徑） |
| `test_import_normal_completion_saves_as_ready` | 匯入正常完成 |
| `test_stop_recording_saves_session_to_disk` | I1（整合 SessionManager real） |
| `test_stop_recording_transitions_to_review_mode` | I2 + I5 |
| `test_stop_recording_produces_final_summary` | spec L139 `is_final` |
| `test_final_summary_timeout_falls_back_to_ready_not_aborted` | G2 + §6 降級原則 |
| `test_pipeline_crash_transitions_aborted_and_saves` | I1 + C3 + G1 |
| `test_stop_timeout_transitions_aborted_stop_timeout_and_saves` | I3 + T8 + G1 |
| `test_session_mode_is_derived_from_status` | I5 + G4 |
| `test_transition_rejects_invalid_status_and_requires_abort_reason` | I6 |

---

## Step 3 — Bug #12 async gen finally yield（commit 49c54f9）

### 根因回顧
[audio_recorder.py](app/core/audio_recorder.py) `start()` 的 finally 區塊內 `yield np.concatenate(transcribe_buffer)`：當消費者 `aclose()` 觸發 `GeneratorExit`、或上游 exception 展開時，generator 進 finally 還想 yield → Python 拋 `RuntimeError: async generator ignored GeneratorExit`（對應 I7）。

### Diff 位置 + 變動邏輯

| 檔 | 位置 | 變動 |
|---|---|---|
| [app/core/audio_recorder.py](app/core/audio_recorder.py) | `start()` while 後 / finally 前 | 把「flush 殘餘 transcribe_buffer」的 `if transcribe_buffer: yield ...` 搬到 `while self._recording:` 退出後、`finally` 之前 |
| 同上 | `finally` | 僅保留不含 yield 的清理：`stream.stop()`、`stream.close()`、`save_buffer` WAV 寫檔（無 yield，安全） |

**正常停止路徑**（`request_stop` → `_recording=False` → while 下一輪退出）仍能 flush 殘餘。
**GeneratorExit / exception 路徑**跳過 flush 直接進 finally，不產生新 yield → I7 成立。

### 對應 invariant
- **I7**（async gen cleanup 不 yield）

### Spec-level tests
| Test | 驗證 |
|---|---|
| `test_bug12_aclose_does_not_raise_runtime_error` | 直接 `await gen.aclose()` — 若 finally 仍 yield 會立即拋 RuntimeError；修復後乾淨 |
| `test_bug12_flushes_partial_transcribe_buffer_on_normal_stop` | 正常停止（<transcribe_chunk_sec）殘餘仍能收到，搬移不退化 |

### 未盡事項
研究者提醒若無法完全消除 RuntimeError，回報大統領可能需重構為 async context manager。目前：

- `sounddevice.InputStream.stop/close` 為同步呼叫，放 finally 無 yield，OK
- `save_buffer` flush 為 disk I/O，無 yield，OK
- 唯一會 yield 的是 `transcribe_buffer` flush，已移出 finally

**結論**：當前實作已完全消除 I7 違反，無需重構為 context manager。若 Reviewer / 實驗者仍發現噪音，再升級。

---

## 實機層檢核（CLI blocker，委交實驗者）

如同 Bug #9 那次，以下 3 項 CLI 環境無法驗證，明確誠實委交實驗者 V Phase 第五輪：

1. **5-10 分鐘實機錄音 + 正常停止** — 驗 I1（data/sessions/ 有檔，status=ready）+ I2（UI 進 review）+ I4（逐字稿不凍結超過 15 秒，跨過 180s summarizer 觸發點）
2. **錄音中拔 Ollama** — 驗 G2 fallback（週期 summary 失敗改顯示「摘要失敗」；final 走 fallback_reason="ollama_failure"；session 仍 ready + saved）
3. **停止按鈕在各種狀態** — 驗 I3（正常停 drain 成功；人為 hang 則 stop_drain_timeout_sec 後 cancel + aborted + partial save）
4. **連按兩次停止** — 第二次在 drain 中 → 目前實作 _stop_recording_async 是 idempotent 的（task.done 即早 return），但二次按停的「強制逃生」路徑未特別處理，留給 Reviewer 判斷是否需加
5. **匯入音檔異常路徑** — 驗 I1 + aborted 落盤 + UI → review(partial)
6. **Bug #12 實機**：實機錄音結束時 log 應無 `RuntimeError: async generator ignored GeneratorExit`

> 單元層做到：assert session.status / abort_reason / save 落盤 / final summary fallback_reason / aclose 不拋錯。實機層無法（無麥克風、無 Ollama、無 Flet UI driver）。

---

## 測試彙總

**Baseline 133（起點）→ 147 passed, 1 skipped（+14 新 spec-level tests）**

- Step 1（#11）：+4 tests in `test_main_pipeline_lifecycle.py`（I4 / C7 / §3.4 rule 1&2）
- Step 2（#10）：+8 tests in `test_main_pipeline_lifecycle.py`（Bug #9 重寫 6 + Bug #10 新增 8 — 原 6 改寫為 spec-level 驗證）。實際淨增 8。
- Step 3（#12）：+2 tests in `test_audio_recorder.py`（aclose + 正常 flush）

補充修正：`test_exporter.py` 與 `test_audio_recorder.py` 因 Session.mode 成 @property + recorder.stop → request_stop 的介面變動需同步更新呼叫。

---

## 對研究者架構 review 的覆蓋度自評

對照 [[pipeline_lifecycle_architecture_20260416]] §1.4 七條 invariants：

| Invariant | 覆蓋 | 備註 |
|---|---|---|
| I1 | ✅ | _run.finally 無條件 save + transition aborted；tests 驗 load 回得來 |
| I2 | ✅ | _run_final_summary 在 mark_ready 前執行；fallback 也算有 final |
| I3 | ✅ | _stop_recording_async 只在 stop_drain_timeout_sec 超時才 cancel |
| I4 | ✅ | fire-and-forget summary，主迴圈不 await |
| I5 | ✅ | Session.mode 是 @property；_finalize_ui 讀 status |
| I6 | ✅ | transition 為唯一入口；直接賦值 session.status 的程式碼已全部 grep 清除 |
| I7 | ✅ | finally 內 yield 移出；aclose 不拋 RuntimeError |

§2 Bug #10 四項檢核（C1-C4）、§4 Bug #11 四項檢核（C5-C8）、§3.4 停止期 pending 規則 — 皆有對應測試。

§6 spec gap 中 G1/G2/G4/G5 已在 Step 2 一併實作，G3（停止期 pending 規則）在 Step 1。G6（併發模型）/G7（異常處理原則）— specs 層面大統領已補（commit f56bb6a），程式碼與之對齊。

---

## 不做與守碼農本分

- ❌ 不改 spec（specs 已由大統領簽核）— 我只動 code 與 tests
- ❌ 不實機驗證（CLI blocker，明確委交實驗者）
- ❌ 不加超出 invariants 範圍的 defensive code（例：不加「三次按停 → nuclear cleanup」這種推測性功能）
- ✅ 每 step 單獨 commit 方便 Reviewer 逐階段審
- ✅ 測試比對 spec invariants 而非實作 intent（實驗者第四輪明訓）

---

## 交棒

| 對象 | 請求 |
|---|---|
| **Reviewer** | 對照 [[pipeline_lifecycle_architecture_20260416]] §1.4 七條 invariants + §2/§4 檢核清單，逐 commit 審（c22c1a2 → 9c6b96e → 49c54f9）。特別留意 main.py `_stop_recording_async` 的 watchdog 語意是否足夠、是否該加「二次按停強制逃生」 |
| **實驗者（V Phase 第五輪）** | 實機 5-10 分鐘錄音 + 拔 Ollama + 匯入音檔異常 + Bug #12 log 驗證（見上方實機層 6 點） |
| **大統領** | (1) 若實機發現新 edge case，請判斷是再派碼農補 patch 還是先補 spec；(2) `Session.mode` @property 改後，data/sessions/ 既有檔保留舊 mode 欄位但被忽略（相容的）— 確認是否需要資料遷移腳本（我判斷不需，舊檔最多是冗餘欄位） |

> 碼農 A 簽核：Step 1/2/3 皆綠燈；單元層覆蓋七條 invariants；實機層誠實委交。等待 Reviewer 與實驗者 V Phase 第五輪結論。
