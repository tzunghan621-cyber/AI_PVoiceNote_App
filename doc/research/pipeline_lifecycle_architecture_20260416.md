---
title: Pipeline Lifecycle 架構 Review — Bug #10/#11 修復指引
date: 2026-04-16
type: research
status: draft
author: 研究者（Researcher）
tags:
  - research
  - architecture
  - pipeline
  - lifecycle
  - concurrency
  - bug-10
  - bug-11
related:
  - "[[system_overview]]"
  - "[[data_schema]]"
  - "[[ui_spec]]"
  - "[[bug_report_flet_api_20260406]]"
  - "[[devlog_20260416_verifier_vphase4]]"
  - "[[devlog_20260416_builderA_bug9]]"
---

# Pipeline Lifecycle 架構 Review — Bug #10/#11 修復指引

> **任務來源**：V Phase 第四輪實驗者警告「修 Bug 變出新 Bug」，請求架構 review 再動手。
> **範圍**：Bug #10（正常停止 → session 遺失）+ Bug #11（Summarizer 阻塞主迴圈）。Bug #12 不在本次範圍。
> **產出形式**：架構 invariants + 修復指引（不寫 code）。

---

## 0. 問題全景圖

```
甲方正常按「停止錄音」（3 分 20 秒）
        │
        ▼
on_stop_recording ──┬── page.run_task(recorder.stop)  ← 軟停（只設 flag）
                    │
                    └── pipeline_task.cancel()        ← 硬中斷（即時拋 CancelledError）
                                │
                                ▼
          _run 的 except CancelledError → raise
                                │
                                ▼ （跳過 processor.run() 末段的 end_recording / final summary / mark_ready）
                            finally 切 idle
                                │
                                ▼
                     _on_pipeline_done 從未被呼叫
                                │
                                ▼
                    session_mgr.save 沒跑 ⇒ data/sessions/ 空白
                    ☠ 3 分 20 秒錄音全滅
```

同時間、另一條軸線：

```
錄音 180 秒（summarizer 第一次觸發）
        │
        ▼
stream_processor.run() 主迴圈 ─── await summarizer.generate(...)  ← Gemma E2B CPU 30~90s
                                                │
                                                ▼
                            await 期間主迴圈停在這行不跑
                                                │
                                                ▼
                          上游 async gen 沒人 consume → 逐字稿凍結
                                                │
                                                ▼
                     甲方以為掛了 → 按停止 → 觸發上面 Bug #10
```

**兩個 bug 糾纏**：Bug #11 讓甲方誤判 → 觸發 Bug #10。修 Bug #11 可降低 Bug #10 觸發頻率，但 Bug #10 本身的資料遺失仍要獨立修。

---

## §1 「停止錄音」語意規範

### 1.1 Spec 目前狀態

**明確的部分（= 碼農應遵守的事實）**：

| 出處 | 條文 |
|---|---|
| [[data_schema#5. Session（單次會議）]] 狀態流轉圖（L184-204） | `recording → processing → ready → exported`；`processing` 的職責寫死是「產生最終摘要」；`ready` 時 `mode` 由 `"live"` 翻成 `"review"` |
| [[ui_spec#2.4 會後編輯模式]]（L189-191） | 「**停止錄音 → 最終摘要產生完成 → 自動切換為會後編輯模式。**」 |
| [[system_overview#4. 串流處理 Pipeline]]§4.2 | 「最終摘要：停止錄音後，全部內容的最終整合摘要」 |
| [[data_schema#4. 摘要結果]] `SummaryResult.is_final` | 欄位本身存在就意味「停止 → 必須有一份 is_final=True 的摘要」 |

→ **spec 清楚規範**：正常停止 = 進 `processing` → 產 final summary → `ready/review` → session 必須落盤（`data/sessions/{id}.json` 存在）。

**模糊 / 缺漏的部分（見 §6 送大統領決定是否送甲方裁決）**：

1. **`processing` 的超時行為**：final summary 若 60 秒以上沒結果（Ollama hang、模型崩潰）要等多久？fallback 為何？
2. **停止當下 summarizer 正在跑：等完還是取消？** 兩個選擇後果不同，spec 沒寫。
3. **異常路徑（Pipeline crash）的 session 命運**：`status` 沒有 `aborted`；已累積的 segments 要丟還是保 partial session 入 review？
4. **`recorder.stop()` 的語意契約**：是「請求停止」（設 flag）還是「保證停止」（await 直到真停）？目前實作名實不符。
5. **Session `status` 欄位與 UI `mode` 欄位的真值**：哪個是 SSoT？轉換規則？

### 1.2 推薦的完整狀態機

```
                           ┌────────────────────┐
                           │        idle        │
                           │   (無 session)     │
                           └─────────┬──────────┘
                                     │ user: Start / Import
                                     ▼
                           ┌────────────────────┐
                           │     recording      │ Session.status=recording, mode=live
                   ┌───────│  (transcribe loop  │
                   │       │   + async summary) │◄─────────┐
                   │       └─────────┬──────────┘          │
                   │                 │                      │  summary 回來
                   │                 │ user: Stop           │  (update_summary
                   │                 ▼                      │   + on_summary)
                   │       ┌────────────────────┐          │
                   │       │      stopping      │──────────┘
                   │       │ (recorder stop flag│
                   │       │  set, drain audio  │
                   │       │  generator)        │
                   │       └─────────┬──────────┘
                   │                 │ async gen 自然結束
                   │                 ▼
                   │       ┌────────────────────┐ Session.status=processing
                   │       │    finalizing      │
                   │       │ (final summary run,│
                   │       │  is_final=True)    │
                   │       └────┬────────┬──────┘
                   │   超時/失敗│        │ 成功
                   │            ▼        ▼
                   │    ┌──────────┐  ┌──────────────┐ Session.status=ready, mode=review
                   │    │ review   │  │    review    │
                   │    │ (partial │  │   (ready,    │
                   │    │  saved)  │  │  saved OK)   │
                   │    └──────────┘  └──────────────┘
                   │
                   │ Pipeline 例外
                   ▼
        ┌────────────────────┐
        │      aborted       │  Session.status=aborted（建議新增）
        │ (unrecoverable;    │  或異常錄音路徑：segments 太少 → idle
        │  save partial, go  │  匯入路徑：已有 segments → review(partial)
        │  review OR idle)   │
        └────────────────────┘
```

### 1.3 每個轉換的觸發事件 + Invariants

| # | 轉換 | 觸發 | 必須成立的 Invariants |
|---|------|------|---------------------|
| T1 | idle → recording | `on_start_recording` / `on_import_audio` | Session.id 已建立；Session.status = recording；ML 模組已載入 |
| T2 | recording → stopping | `on_stop_recording`（正常） | `recorder._recording = False`（軟停止）；**不 cancel pipeline_task**；UI 可顯示「停止中...」 |
| T3 | stopping → finalizing | async gen 耗盡，`async for` 自然退出 | Session.status = processing；`end_recording` 已設 `ended` 時間戳 |
| T4 | finalizing → review (ok) | final summary OK + save OK | Session.status = ready；Session.mode = review；summary_history 至少一筆 is_final=True；**`data/sessions/{id}.json` 實體存在** |
| T5 | finalizing → review (partial) | final summary timeout / fail | Session 仍落盤；summary 可能用上一個週期版（非 is_final），或空 highlights + fail note；UI 顯示「摘要生成失敗，可手動補」 |
| T6 | any → aborted | Pipeline 內部 exception（非 Cancel） | logger.exception 完整 traceback；UI 彈持久錯誤對話框；**若已有 segments → save 進 review(partial)**；無 segments → idle |
| T7 | review/aborted → idle | 使用者離開 / 新錄音 | 無（review/aborted 已落盤） |
| T8 | stopping → aborted (escape) | 甲方二次按停 or 全域 timeout（例 > 90 秒沒進 review） | pipeline_task.cancel() 真正當安全網啟動；UI 彈「強制中止」提示；partial save |

### 1.4 核心 Invariants（所有路徑都必須成立）

| ID | Invariant | 違反後果（現況就是 Bug #10）|
|----|-----------|-------------------------|
| **I1** | **任何離開 recording/stopping/finalizing 的路徑，Session 都必須已寫入 `data/sessions/`**（可含 partial 資料、標 aborted status） | 3 分 20 秒錄音全滅 |
| **I2** | **正常停止路徑必須先完成 final summary 才觸發 UI 轉場**（轉場順序：save → mark_ready → set_mode("review") → status_bar） | 目前 finally 搶先切 idle → 轉場與 save 解耦 → data race |
| **I3** | **`pipeline_task.cancel()` 只在「真卡死」時啟動**（使用者二次按停 / 全域 timeout 超過 N 秒），不得是正常停止預設路徑 | B1 把 cancel 當預設 → 翻轉語意 |
| **I4** | **Summarizer 執行不得 block audio_source 的 consume**（`async for audio_chunk` 必須持續推進，否則 transcribe / UI 全凍結） | Bug #11：逐字稿 180s 後凍結 30-90s |
| **I5** | **UI mode 只由 Session.status 驅動**（單一 SSoT）：`recording→live`、`processing/stopping/finalizing→live+stopping indicator`、`ready→review`、`aborted→review(partial) or idle` | 目前 UI 狀態由 finally 塊與 `_on_pipeline_done` 分頭寫，易衝突 |
| **I6** | **Session 狀態轉換由 SessionManager 專屬 API 負責，UI/main.py 不可直接改 `session.status`** | 目前分散寫；未來若加 aborted 狀態會再炸 |
| **I7** | **async generator 的 cleanup（GeneratorExit）路徑不產生新 yield**（Bug #12 領域，附帶對 I1 有影響：若 flush 殘餘走 finally-yield → 殘餘音訊遺失） | 目前會 `async generator ignored GeneratorExit` |

---

## §2 Bug #10 修復指引

### 2.1 碼農修完後程式必須滿足的條件（檢核清單）

**C1. 正常停止路徑**
- [ ] 甲方按「停止錄音」後，`on_stop_recording` **不**立即 cancel pipeline_task。
- [ ] `recorder.stop()` 設旗標後，`processor.run()` 主迴圈的 `async for` 必須**自然結束**（audio_source 的 generator 耗盡）。
- [ ] 主迴圈結束後必須跑到 [stream_processor.py:71-83](app/core/stream_processor.py#L71-L83)：`end_recording` → final summary (`is_final=True`) → `update_summary` → `mark_ready`。
- [ ] `_on_pipeline_done` 被呼叫：`session_mgr.save(session)` 必須實際落盤（`data/sessions/{id}.json` 存在且可 `load` 回來）。
- [ ] UI 切到 `review` mode（不是 `idle`）。
- [ ] 滿足 **I1 + I2 + I5**。

**C2. cancel 只當安全網**
- [ ] `pipeline_task.cancel()` 只在以下情境啟動：
  - 甲方在 `stopping/finalizing` 狀態再次按「停止」（強制逃生）
  - 全域 watchdog：進 `stopping` 超過 N 秒（建議 90~120 秒）還沒進 review
- [ ] cancel 啟動時 UI 必須顯示持久提示（SnackBar ≥ 30 秒）：「處理逾時強制中止，已保留 X 分 Y 秒逐字稿於會後編輯」。
- [ ] cancel 路徑的 `finally` 必須**嘗試 save 已累積 segments**（partial session），status 設 `aborted` 或保持 `processing` 標註（見 §6 gap #3）。
- [ ] 滿足 **I3 + I1**。

**C3. 異常路徑與正常路徑分離**
- [ ] Bug #9 修好的異常處理（logger.exception、SnackBar、UI 回 idle）行為不得回歸。
- [ ] 但對「異常時已有 segments」：錄音路徑若 segments ≥ M（例 ≥ 5）也進 review(partial) 而非 idle，避免「錄了 2 分鐘但 summarizer 一崩整場丟」；匯入路徑維持 Bug #9 的 review。
- [ ] 滿足 **I1 + I6**。

**C4. `recorder.stop` 語意修正**
- [ ] [main.py:155](app/main.py#L155) `page.run_task(recorder.stop)` 傳的是 **coroutine function 本體**；改方案後應為 `page.run_task(recorder.stop())` 或直接 `await recorder.stop()`（若 on_stop_recording 改 async）。
- [ ] 若要明確語意：把 `recorder.stop()` 改名 `request_stop()` 或加 `await recorder.wait_stopped()` 的阻塞版（本次可不拆，但把現狀記入 §6 gap）。

### 2.2 具體動點（僅標位置，不寫 diff）

| # | 檔案 | 位置 | 要做什麼 |
|---|------|------|---------|
| 1 | [main.py](app/main.py) | L149-157 `on_stop_recording` | 移除主動 cancel 當預設路徑；保留 cancel 作為 watchdog / 二次按停的安全網 |
| 2 | [main.py](app/main.py) | L84-108 錄音 `_run` | `finally` 區塊內區分三種收尾：(a) 正常完成（_on_pipeline_done 已跑，不動 UI）；(b) Cancel 路徑 + 有 segments → save partial + review；(c) 例外或無 segments → idle |
| 3 | [main.py](app/main.py) | L126-145 匯入 `_run` | 同上 (b)/(c) 分流（原本就是 review/partial，但要確保 save 有跑） |
| 4 | [main.py](app/main.py) | 新增 watchdog | 進 `stopping` 時起計時，N 秒未完成強制 cancel |
| 5 | [stream_processor.py](app/core/stream_processor.py) | L71-83 收尾段 | 保護：`end_recording` + `final_summary` + `mark_ready` 任一失敗都要確保 save 有被呼叫（try/finally 包住） |
| 6 | [session_manager.py](app/core/session_manager.py) | `save` | 確認 save 具冪等性（多次呼叫不出錯）；必要時新增 `save_partial(session, reason)` 專門路徑 |
| 7 | [audio_recorder.py](app/core/audio_recorder.py) | L82-84 `stop` | 若改名 `request_stop`，同步更新所有引用 |

### 2.3 兩個可行實作方向給碼農選

| 方案 | 做法概述 | 優點 | 缺點 |
|------|---------|------|------|
| **A（推薦）** | `on_stop_recording` 改 async；`await recorder.request_stop()` + `await asyncio.wait_for(pipeline_task, timeout=90)`；timeout 才 cancel | 語意清晰、符合 spec；drain 成功率高 | UI 按鈕事件變 async；需處理「停止中」UI 狀態 |
| **B** | `on_stop_recording` 保同步；啟動 watchdog task；正常路徑完全靠 `recorder.stop()` 旗標 | 改動小、相容目前 Flet callback 簽章 | watchdog 實作複雜；狀態傳遞分散 |

→ 建議採方案 A。如果碼農判斷 Flet 0.84.0 的事件 callback 不支援 async，請回報，研究者再補研究。

---

## §3 Summarizer 並發架構選型

### 3.1 選項比較表

| 面向 | **Option A**：fire-and-forget task | **Option B**：queue + dedicated consumer task | **Option C**：保持 serial，只改 UI 提示 |
|------|---------------------------------|-------------------------------------------|-------------------------------------|
| **做法** | 主迴圈 `asyncio.create_task(self._run_summary_async(...))` 後繼續跑；`_summarizing` flag 防重入 | 主迴圈 put `(segments, prev)` 進 `summary_queue`；獨立 consumer task `async for req in queue: await generate(req)` | 主迴圈 `await` 照舊；觸發時 `on_status_change("summarizing")` 讓 UI 顯示 spinner；文案告知「推理中」 |
| **改動範圍** | `stream_processor.py` 新增 helper method + 幾行 create_task；`main.py` callback 不變 | `stream_processor.py` 新增 queue + consumer；`run` 要管兩條 task 的 lifecycle；`on_stop_recording` 要 drain queue | `stream_processor.py` L56-L69 幾乎不動；`dashboard_view.py` 加 summarizer 狀態指示 |
| **錯誤傳播** | 任務內 try/except + log；失敗用 `session.summary` 保留上一版；可設 task.add_done_callback 捕 exception 傳給 UI | consumer 統一處理；錯誤可通知主迴圈（sentinel 或 Event） | 同現況 — 錯誤直接炸主迴圈（這就是為什麼過去 Bug #9 曾被 summarizer timeout 引爆） |
| **順序保證** | `self._summarizing` + 單一 pending task 保證**不並發同一份 summary**；`version` 仍單調遞增；若 fire 第二次時前一次還沒完成 → **skip 本次觸發**（避免 race） | queue FIFO 天然保證順序；可以堆積多筆待算（會累積 lag） | 天然 serial，無順序問題 |
| **與 I4 相容性** | ✅ 主迴圈立即返回繼續 consume | ✅ 主迴圈 put 後立刻返回 | ❌ 根本沒解 — 主迴圈仍卡住 |
| **停止整合（§3.2）** | 直觀：進 stopping 時 `await pending_summary_task`（給它完成權）；真 timeout 才 cancel | 複雜：停止時要決定 queue 內未處理項目怎辦（drain vs flush） | 直觀但不治本 |
| **複雜度** | 中 | 中高 | 低 |
| **治本程度** | 🟢 治本 | 🟢 治本（更穩但過度設計） | 🔴 不治本 |

### 3.2 推薦方案與理由

**推薦 Option A（fire-and-forget task + `_summarizing` flag）**。

理由：
1. **與 spec 一致**：[[system_overview#4.2 週期性摘要更新]] 寫「累積足夠新內容後觸發」＋「每次送新段落 + 前次摘要」，這是**單點觸發 + 最多一個 pending 任務**的語意，不是多筆 queue。
2. **現有 `_summarizing` flag 幾乎就是為此設計**（[stream_processor.py:24](app/core/stream_processor.py#L24) 已有，只是目前在 serial 模式沒實際用途）。
3. **改動最小**：只需把 L58-L69 的 inline await 抽成 `async def _run_summary_async`，用 `asyncio.create_task` 啟動。
4. **停止整合明確**：final summary 路徑可直接 `await self._summarizer_task if self._summarizer_task else None`，drain 成功就走 T4，timeout 走 T8。
5. **Option B 過度設計**：queue 意味「可以累積多個摘要請求」，但我們的觸發條件天然已防連發（`summary_interval` 至少 180 秒 + `_summarizing` 保護），queue 沒額外價值只增複雜度。
6. **Option C 不治本**：UI 提示只是遮羞布，逐字稿仍凍結 → 甲方仍可能誤判按停 → 仍觸發 Bug #10。

### 3.3 對 `session_manager.update_summary` 介面的影響

**無介面變更**。

`update_summary(session, summary)` 仍由新的 `_run_summary_async` helper 呼叫；只是呼叫時機從「主迴圈 await 完」改成「background task 回來後」。

**需注意的 thread/task 安全性**：
- `session.summary_history.append(summary)` 與 `session.summary = summary` 是單純 list append + 欄位賦值，在 single event loop 內沒競爭。
- 但若主迴圈同時在讀 `session.summary` 當下次 `previous_summary` 傳入：**必須在 fire 下一個 task 之前，先用當下 `session.summary` snapshot**，避免 task 啟動到完成之間 `session.summary` 被別的路徑改。現狀是 serial 所以沒事，改 A 後要 snapshot。

### 3.4 停止期間 pending summary 的處理規則

這是 §6 gap #2 的 spec 缺漏，研究者**建議規則**如下（等大統領/甲方裁決）：

| 情境 | 規則 | 理由 |
|------|------|------|
| `stopping` 進入時 pending summary 還在跑 | **等它完成**（最多 60 秒）再觸發 final summary | 沒完成的週期摘要代表「甲方停止前最後一段內容已被 AI 消化」，丟掉會讓 final summary 看不到這段的 incremental 結果（雖然 final 會重跑，但保留週期結果還是比較合理）|
| pending summary 60 秒仍沒完 | cancel 它，直接跑 final | final summary 會 cover 全部內容，pending 結果反正要被覆蓋 |
| final summary 超時（例 > 120 秒）| 用上一個週期版本的 summary 當 final（標 fallback）+ save | spec I1（session 必存）優先於 summary 完整性 |

---

## §4 Bug #11 修復指引

### 4.1 碼農修完後程式必須滿足的條件

**C5. 非阻塞 Summarizer**
- [ ] 主迴圈 `async for audio_chunk in audio_source:` 在 summarizer 推理期間持續 consume（例：60 秒內至少 yield 5 次新 segment，假設 transcribe_chunk_sec=10）。
- [ ] `on_segment` callback 在 summarizer 推理期間持續被呼叫（UI 逐字稿持續更新）。
- [ ] 滿足 **I4**。

**C6. 單一 pending summary**
- [ ] `_summarizing` flag 在 summary task 真正啟動時設 True，task 結束（成功/失敗/cancel）時設 False。
- [ ] 週期觸發條件 `not self._summarizing` 仍有效，第二次觸發時若前一次未完，**本次 skip**（由下一個週期再試，不排隊）。
- [ ] `session.summary` 被後來的 task 覆蓋時 **version 單調遞增**（`Summarizer._version` 已保證，驗一下）。

**C7. 錯誤不炸主迴圈**
- [ ] summary task 內部 exception 不得 propagate 到主迴圈（否則主迴圈死掉 → Bug #9 重現）。
- [ ] task 失敗時：log.exception + `_summarizing=False` + `session.summary` 保留上一版 + 在 UI 狀態列顯示「摘要 N 失敗，下次週期重試」（可選）。

**C8. 停止與 pending summary 協調**
- [ ] 進 stopping 時：若有 pending summary task，最多 `asyncio.wait_for(pending, timeout=60)`；timeout 則 cancel。
- [ ] 然後觸發 final summary（is_final=True）— 不論 pending 結果如何。
- [ ] Final summary 也適用 timeout（建議 120 秒），超時走 §3.4 fallback 規則。

### 4.2 具體動點

| # | 檔案 | 位置 | 要做什麼 |
|---|------|------|---------|
| 1 | [stream_processor.py](app/core/stream_processor.py) | L54-L69 | 週期觸發分支：改為 `asyncio.create_task(self._run_summary_async(...))`，主迴圈立即 continue |
| 2 | [stream_processor.py](app/core/stream_processor.py) | 新增 `_run_summary_async` helper | 包 `self.summarizer.generate + session_mgr.update_summary + on_summary + _summarizing=False (finally)`；內部 try/except 保護 |
| 3 | [stream_processor.py](app/core/stream_processor.py) | L71-L88 收尾段 | 進 finalize 前 `await` pending summary task（timeout 60s）；final summary 本身加 timeout 包裝 |
| 4 | [stream_processor.py](app/core/stream_processor.py) | `__init__` | 新增 `self._summary_task: asyncio.Task | None = None` |
| 5 | [summarizer.py](app/core/summarizer.py) | L152-L164 `_call_ollama` | **不改**（httpx timeout=120 已夠，治本在上游 fire-and-forget） |
| 6 | [dashboard_view.py](app/ui/dashboard_view.py) | status bar | 若採 §3 附帶建議：加 summarizer 狀態指示（可選，低優先） |

### 4.3 回歸風險

- **順序反轉**：若 task B 啟動比 task A 晚但跑比較快，`session.summary = summaryB` 後 task A 回來又覆蓋成 summaryA → 摘要倒退。但因 `_summarizing` flag + 週期 180 秒間隔，同時只會有一個 task，此風險在 A 方案下不存在。加注釋提醒後人別把 flag 拿掉。
- **race on `session.summary`**：A 方案下，summary task 啟動前後 `session.summary` 只由 task 自己寫；主迴圈不寫。OK。但讀 `previous_summary` 時要 snapshot（§3.3）。

---

## §5 新增 Regression Tests 建議

### 5.1 反思為什麼既有 112 tests 抓不到

實驗者第四輪 devlog 說對了：「test 驗的是 pattern 實作，不是 spec 語意」。

| 既有 test | 驗了什麼 | 為什麼抓不到 Bug #10 |
|----------|---------|------------------|
| `test_recording_cancelled_propagates_but_finally_runs` | CancelledError 正確傳遞 + finally 跑 | 沒問「cancel 路徑應不應該是正常停止」 — 直接接受 implementation intent |
| `test_recording_normal_completion_does_not_reset_ui` | 正常完成 `_on_pipeline_done` 跑過後 finally 不覆寫 | 沒問「正常按停止是否能走到正常完成路徑」 |

→ **設計新 test 的原則**：以 [[ui_spec]] / [[data_schema]] 的行為描述為輸入，驗證**行為結果**（session 有沒有存、UI 進了哪個 mode），而不是驗「程式有沒有照某段邏輯跑」。

### 5.2 必加的 Spec-Level Tests

| Test 名 | 驗證 Invariant | 場景描述 |
|---------|---------------|---------|
| `test_stop_recording_saves_session_to_disk` | I1 | 啟動 fake 錄音 → 餵 N 個 fake segments → 呼叫 `on_stop_recording` → 驗 `data/sessions/{id}.json` 存在 + `load` 可還原 + `status == "ready"` |
| `test_stop_recording_transitions_to_review_mode` | I2 + I5 | 同上 → 驗 `session.mode == "review"` 且 `dashboard.set_mode` 最後一次呼叫帶 `"review"` |
| `test_stop_recording_produces_final_summary` | spec L139 `is_final` | 同上 → 驗 `session.summary.is_final is True` 且 `summary in session.summary_history` |
| `test_stop_recording_does_not_lose_segments` | I1 + I7 | 餵 N segments，其中最後一個在 stop 前剛好 yield 出來 → 停止後 session.segments 長度 == N |
| `test_summarizer_does_not_block_transcription` | I4 | fake Ollama 回應延遲 60 秒；主迴圈期間應該繼續 consume audio_source，`on_segment` 在這 60 秒內至少被呼叫 X 次 |
| `test_summarizer_failure_does_not_crash_pipeline` | C7 | Ollama fake 拋例外 → pipeline 繼續跑、主迴圈繼續 consume；下一個週期應該會重試 |
| `test_stop_during_summarization_waits_for_pending` | §3.4 rule 1 | fake Ollama 延遲 30 秒；在 summary 推理中觸發 stop → final summary 仍產生；session 落盤 |
| `test_stop_timeout_cancels_and_saves_partial` | I3 + T8 + C2 | fake Ollama hang 超過 watchdog timeout → pipeline_task.cancel() 啟動 → session 以 partial 狀態落盤（status=aborted 或類似） |
| `test_pipeline_crash_persists_partial_session_if_segments_exist` | C3 | 餵 10 segments 後 fake transcriber 拋例外 → 驗 session 仍落盤（可 partial）而非全丟 |
| `test_second_stop_forces_cancel` | T8 | 第一次 stop 後 10 秒內第二次按 stop → 視為逃生 → cancel pipeline_task |

### 5.3 非單元層的測試（文字化 checklist，交實驗者）

單元層到不了的，明確寫進 [[verification_report_20260405]] 的 V Phase 第五輪 checklist：

1. **實機錄音 5 分鐘（跨過 180 秒 summarizer 觸發）**：逐字稿不可凍結超過 15 秒（UI 觀察）。
2. **實機錄音 3 分鐘 + 正常停止**：UI 進 review；`data/sessions/` 有檔；甲方能點「匯出 Markdown」。
3. **實機錄音中拔 Ollama**：pipeline 繼續跑（不崩）；週期摘要改顯示「摘要失敗，重試中」；停止時 final summary 嘗試（可能 fallback）；session 仍落盤。
4. **實機錄音中連按兩次停止**：第一次 stop 後 UI 顯示「停止中...」；第二次 stop 在 10 秒內 → 強制 cancel + partial save + SnackBar 提示。
5. **匯入音檔完整流程**：match T1 sequence；對應 Bug #9 的 review 分流不得回歸。

---

## §6 與 Spec 的 Gap 清單（送大統領裁決）

### G1（🟥 高優先）— Session.status 缺 `aborted` 狀態

**位置**：[[data_schema#5. Session（單次會議）]] L168 + L184-204 狀態流轉圖

**現況**：`status` 只有 `recording | processing | ready | exported`。Pipeline crash、cancel watchdog、summary timeout 等異常路徑沒有合法的 `status` 值 — 目前碼農 A 在異常路徑做 `set_mode("idle"/"review")` 但 `session.status` 從未設成非正常值。

**建議**：
- 新增 `status: "aborted"`（已有部分資料但未產 final summary）
- 可選：新增 `status: "finalizing"`（精細化 processing 的子狀態）
- 增加欄位 `abort_reason: str | None`（如 `"pipeline_error" | "stop_timeout" | "ollama_failure"`）

**建議文字**（data_schema.md L168 附近）：
```
status: "recording" | "processing" | "ready" | "exported" | "aborted"
abort_reason: str | None   # 僅 status=aborted 時填入
```

**影響**：此變更**直接決定 Bug #10 的修復形式**，需甲方簽核後碼農才能動。

### G2（🟥 高優先）— 正常停止路徑的 Summarizer 超時行為

**位置**：[[system_overview#4.2 週期性摘要更新]] + [[ui_spec#2.4]]

**現況**：spec 寫「停止 → 最終摘要 → review」但沒寫「最終摘要要多久」「Ollama 壞了怎麼辦」。

**建議**：補一段「逾時與 fallback」規範：
- final summary 最長等待 120 秒（可設定）
- 超時 → 用最近一版週期 summary 當 final（`is_final=True` + 註記 `fallback_reason="ollama_timeout"`）
- 仍必須進 `review`，session 必須落盤

**建議 config 欄位**（`config/default.yaml`）：
```yaml
streaming:
  final_summary_timeout_sec: 120
  stop_drain_timeout_sec: 90
```

### G3（🟧 中優先）— 停止期間 pending summary 的處理

**位置**：[[system_overview#4. 串流處理 Pipeline]]

**現況**：spec 沒寫停止當下如果正好在算週期摘要怎麼辦。

**建議**：採 §3.4 表（等最多 60 秒 → timeout 則 cancel → 進 final）。把這段直接寫進 system_overview §4.2 尾段。

### G4（🟧 中優先）— Session.status 與 UI mode 的真值關係

**位置**：[[data_schema#5. Session（單次會議）]] + [[ui_spec#2.4]]

**現況**：`Session.status` 和 `Session.mode` 是兩個獨立欄位，但 UI 顯示又有第三個「idle/live/review」狀態（main.py `dashboard.set_mode`）。哪個驅動哪個？不明確。目前 `_on_pipeline_done` 兩個都改，異常路徑只改 UI mode 不改 session.status。

**建議**：
- **SSoT = Session.status**。`Session.mode` 為衍生欄位（由 status 推導：recording/processing → live，ready/aborted/exported → review）。考慮簡化 data_schema 把 `mode` 變成 `@property`。
- UI `dashboard.set_mode` 只能透過 `session.status` 查詢決定。
- 新增 `SessionManager.transition(session, new_status)` 統一改 status + mode 原子化。

### G5（🟨 低優先）— `recorder.stop()` 語意

**位置**：[[system_overview#3.2 模組職責]] AudioRecorder 列

**現況**：`stop()` 是 async 函式但只是設旗標（軟停止），名稱暗示同步停止。

**建議**：
- 改名 `request_stop()` 或 `signal_stop()`；或
- 加 `async def wait_stopped(self)` 當真正阻塞版
- system_overview 表格補說明「串流生命週期：start() async gen 在 request_stop() 設旗標後，於下一個 `while` 迴圈自然退出；消費者應 drain generator 而非靠 task.cancel」

### G6（🟨 低優先）— Summarizer 併發模型

**位置**：[[system_overview#4. 串流處理 Pipeline]] §4.1 時間軸圖

**現況**：時間軸圖含混；文字寫「週期性」但沒寫 summarizer 是否與 transcribe 並行。目前 Bug #11 暴露「實作是 serial，但時間軸圖和使用者期待都是並行」。

**建議**：補一小段「Summarizer 在獨立 task 執行，不阻塞轉錄主迴圈；同時最多一個 pending summary」— 正式把 §3 Option A 寫進 spec。

### G7（🟩 資訊性）— Spec 缺「異常處理原則」總則

**位置**：建議新增 [[system_overview]] §X 或獨立 `doc/specs/error_handling.md`

**現況**：spec 沒寫系統層級的異常處理原則（例如「資料優先於功能完整」、「寧可 partial 落盤也不丟整場」）。碼農每次自己推理，結果就是 Bug #10 這種「選了 cancel 來 graceful shutdown，結果資料全滅」。

**建議**：補一段原則：
1. **資料保全優先**：任何包含已處理 segments 的 session 必須落盤（即使 partial）。
2. **降級而非崩潰**：Summarizer 失敗 → 降級為無摘要版；Transcribe 失敗 → 降級為空 segment；不整條死。
3. **明確告知使用者**：所有降級路徑必須在 UI 彈出持久提示。

這對應 v4.0 director_handbook §簽核權責分級的「規格變更（補原則）」類別。

---

## §7 研究者結論與交棒建議

### 7.1 結論

- **Bug #10 根因**：B1 把 `pipeline_task.cancel()` 從「安全網」錯當「預設停止路徑」，語意翻轉。修復核心是**讓正常停止走 drain（靠 recorder 旗標），cancel 只當 watchdog 用**。
- **Bug #11 根因**：`stream_processor.run()` 主迴圈 `await summarizer.generate()` 讓這個 task 的執行點停在這行 → 上游 async gen 沒人 consume。修復核心是**把 summarizer 丟 background task（fire-and-forget）**。
- **兩個 bug 糾纏**：Bug #11 讓甲方誤判 → 觸發 Bug #10。先修 #11（UI 不凍結）可大幅降低 #10 觸發概率，但 #10 本身的資料遺失必須獨立修。**修復順序建議 #11 → #10**（順序與實驗者建議相反，因為修 #11 後才能跑滿 5 分鐘重現 #10；但若碼農有信心可並行修）。
- **Spec 有 5+ 處缺漏**（§6），其中 G1（新增 `aborted` status）+ G2（summary timeout fallback）必須先送甲方裁決才能開工。

### 7.2 給大統領的派工建議

1. **先裁決 spec**（G1 + G2 強制，其他可延後）：
   - G1（新增 `aborted` status）— 建議送甲方簽核，因為涉及資料結構
   - G2（summary timeout + fallback）— 建議大統領自行裁決（屬實作細節）
   - G3/G4/G5/G6/G7 — 大統領依權責分級裁決（§6 已標優先級）
2. **Spec 敲定後派工**：
   - 碼農 A 修 Bug #11（依 §4）— 改動範圍小、風險低，可先單獨一個 commit 觀察
   - 碼農 A 修 Bug #10（依 §2）— 需要 Bug #11 先修才能實機重現 drain 路徑
   - Bug #12（不在本次 review 範圍）可併入 Bug #10 的 PR
3. **Reviewer 獨立 CLI 審 PR**：對照本文 §1.4 Invariants 逐項勾選
4. **實驗者 V Phase 第五輪**：用 §5.2 tests + §5.3 checklist 重驗

### 7.3 不做的事（守研究者本分）

- ❌ 不寫 code（本文 0 行 Python）
- ❌ 不直接改 spec（G1-G7 僅建議，送大統領/甲方裁決）
- ❌ 不補 bug_report 章節（架構 review 是獨立 research 文件）
- ❌ 不指派 Builder 具體做法（只給 invariants 與位置，Builder 自行選實作細節）

---

> 研究者簽核：架構 review 完成，已識別 §1.4 七條 invariants + §3 summarizer 並發選型 + §6 七項 spec gap。交棒大統領裁決後派工。
