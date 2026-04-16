---
title: 開發日誌 2026-04-16 — 實驗者 V Phase 第四輪（Bug #9 重驗 → 發現 Bug #10/#11/#12）
date: 2026-04-16
type: devlog
status: active
author: 實驗者（Verifier）
tags:
  - devlog
  - verifier
  - v-phase
  - bug-9
  - bug-10
  - bug-11
  - bug-12
  - pipeline-lifecycle
related:
  - "[[bug_report_flet_api_20260406]]"
  - "[[verification_report_20260405]]"
  - "[[devlog_20260416_builderA_bug9]]"
  - "[[devlog_20260416_verifier_vphase3]]"
---

# 實驗者 V Phase 第四輪 — Bug #9 重驗 + 3 個新 Bug 發現 — 2026-04-16

> 前一棒：[[devlog_20260416_builderA_bug9]]（碼農 A 依 bug report §Bug #9 修復建議 A1/A2/A3/B1/C1 實作，commit `b428369`，112 tests 綠燈，CLI 無法實機驗證委交給我）

---

## 任務脈絡

V Phase 第三輪撞 Bug #9（Pipeline crash → 殭屍 live，只能 kill process），完整根因 A/B/C/D 已寫進 bug report。

碼農 A 修完 commit `b428369`（僅改 [main.py](app/main.py) + 新增 [test_main_pipeline_lifecycle.py](tests/test_main_pipeline_lifecycle.py)），112 asyncio lifecycle tests 綠燈，但**誠實標示** CLI 無 GUI driver，無法跑 5-10 分鐘實機錄音 + 拔 Ollama 模擬，明確委交給我協同甲方驗證。

本輪任務：Bug #9 實機重驗 + S2/S4/S5/S9 smoke。

---

## 執行紀錄

### Step 1 — Regression（autonomous）

```bash
python -m pytest -m "not slow and not real_audio" -q
→ 112 passed, 22 deselected, 1 warning in 13.61s
```

| 項目 | 結果 |
|---|---|
| baseline 106 fast tests | ✅ |
| 碼農 A 新增 6 個 lifecycle tests | ✅ |
| regression | ✅ 無 |

### Step 2a — 靜態 diff 複核（autonomous）

逐項對照 bug report §Bug #9「修復方向建議」表：

| # | 檢核項 | 結果 |
|---|---|---|
| A1 CancelledError 分流 | [main.py:90-92](app/main.py#L90-L92) | ✅ |
| A1 logger.exception | [main.py:94, 136](app/main.py#L94) | ✅ |
| A1 finally recorder.stop() | [main.py:96-100](app/main.py#L96-L100) | ✅ |
| A2 SnackBar 非空 + 30s 停留 | [main.py:54-66](app/main.py#L54-L66) | ✅ |
| A3 匯入路徑鏡像 | [main.py:126-145](app/main.py#L126-L145) | ✅ |
| B1 pipeline_task handle + cancel | [main.py:49, 110, 147, 149-157](app/main.py#L49) | ⚠️ 實作為「預設路徑」而非「安全網」— 見 Bug #10 |
| C1 錄音異常→idle、匯入異常→review | [main.py:104, 141](app/main.py#L104) | ✅ |

**靜態層面 A1/A2/A3/C1 全綠，B1 有語意偏差疑慮，需實機才能確認影響**。

### Step 2b — T1 實機 5+ 分鐘錄音（甲方協同）

**設置**：

- 背景啟動 `python -m app.main`
- Monitor tail log + grep `Pipeline error|Traceback|ERROR|RuntimeError|CancelledError|Exception|Error|GeneratorExit`
- 甲方本人操作 GUI（麥克風錄音 + 按停止）

**執行結果**：

甲方錄音 ~3 分 20 秒（根據 log 20 個 10s chunks），按停止錄音。

甲方回報觀察：

1. 約 180 秒後「逐字稿停止新增 segment」（選項 2b）
2. 「會議重點 / Action Items 全空白」（選項 2c）
3. 按停止錄音「直接回開始錄音畫面（idle）」

log 實況：

```
INFO:faster_whisper:Processing audio with duration 00:10.010  × 20 次
INFO:faster_whisper:VAD filter removed ...
INFO:__main__:Recording pipeline cancelled by user    ← 唯一一行，且來自甲方停止
ERROR:asyncio:Task exception was never retrieved
future: <Task ... exception=RuntimeError('async generator ignored GeneratorExit')>
```

檢查 `data/sessions/` → **空目錄**（3 分多鐘錄音完全遺失）。

### 連鎖觀察拆三個獨立根因

#### Bug #10 — 正常停止 = 資料遺失（最嚴重）

[main.py:149-157](app/main.py#L149-L157) `on_stop_recording`：
```python
if recorder:
    page.run_task(recorder.stop)          # 軟停止（設 flag）
if pipeline_task is not None and not pipeline_task.done():
    pipeline_task.cancel()                 # 立刻 cancel（硬中斷）
```

Cancel 比軟停止快 → `_run` 走 CancelledError → finally 回 idle → `_on_pipeline_done` 從未被呼叫 → `session_mgr.save` 沒跑。

碼農 A devlog 自己寫的：「正常錄音中按停止 → recorder 停 + pipeline_task cancel → UI 回 idle（會跳過 final summary，這是 B1 設計選擇）」

但這違反 spec 預期：停止錄音 → review 模式 → 可編輯 / 匯出。

B1 把 cancel 從「卡死安全網」誤用成「預設停止路徑」，語意翻轉。

#### Bug #11 — Summarizer 阻塞主迴圈（UI 凍結根因）

[stream_processor.py:59](app/core/stream_processor.py#L59)：
```python
async for audio_chunk in audio_source:
    new_segments = await asyncio.to_thread(...)  # transcribe
    ...
    if elapsed >= self.summary_interval:
        summary = await self.summarizer.generate(...)  # ← 主迴圈被整串 await 住 30-90s
```

Gemma E2B 在 Surface Pro 9 CPU 推理 30-90s。期間：
- event loop 沒 block（httpx async）
- **但這個 task 的主迴圈被這行 await 擋著不跑**
- 上游 audio_source 沒人 consume → 卡在 yield
- 沒新 transcribe、沒新 segment 進 UI

甲方看到「逐字稿 180s 後不更新」就是這個。

**這是架構問題**，不是 Bug #9 造成。前三輪都沒錄到 summarizer 觸發點，V4 首次暴露。

#### Bug #12 — `audio_recorder.start()` async gen finally-yield

[audio_recorder.py:73-80](app/core/audio_recorder.py#L73-L80)：
```python
try:
    while self._recording:
        ...
finally:
    stream.stop()
    stream.close()
    if transcribe_buffer:
        yield np.concatenate(transcribe_buffer)   # ❌ finally 內 yield
```

Python async gen 規則：finally 內 yield 會吞掉 GeneratorExit → `RuntimeError: async generator ignored GeneratorExit`。

碼農 A 在 bug_report §Bug #9 連鎖 D 預測「A+B+C 修好後應自然消失」**失敗**。

### Step 2c/2d/3（T2/T3/S2-S9）— 未執行

依規則「有新 bug 立刻回報大統領，不要 loop」：

- Bug #10 使「正常錄音流程」整條不可用
- 繼續跑 T2/T3/S2-S9 只會：
  - 重複浪費甲方時間
  - 驗證明知已壞的路徑
  - 可能觸發連鎖新問題污染 bug 診斷
- 即刻停止、整合回報

### Step 4 — 文件產出（本次）

1. **[[bug_report_flet_api_20260406]] 新增 Bug #10 / #11 / #12 章節**（含根因、修復建議、驗證條件、與其他 bug 的關係）
2. **[[verification_report_20260405]] §八（第四輪）** 新增完整紀錄
3. **本 devlog**

---

## 判讀與給大統領的建議

### 緊急度分級

| Bug | 嚴重度 | 原因 |
|---|---|---|
| #10 | 🟥🟥🟥 最急 | 資料遺失（每次正常停止 = 所有錄音丟失），違反 spec |
| #11 | 🟧 高 | UI 凍結 30-90s，雖不致命但讓甲方以為掛了 → 觸發 Bug #10 |
| #12 | 🟨 中 | asyncio log 噪音，不致命但污染診斷 |

### 派工建議

**三個全派碼農 A**：
- 他修了 Bug #9，架構他最熟
- #10 是他 B1 的副作用，他理解脈絡
- #11 是架構重構（summarizer 背景化），邏輯類
- #12 是 async gen 規則，邏輯類

**施工順序**：#10 → #11 → #12（#10 資料安全最優先；#11 修完讓 #10 的實機驗證能真的跑完 5+ 分鐘；#12 可併入 #10/#11 PR）

### 反思（供大統領參考）

1. **單元測試綠燈 ≠ 符合 spec**：碼農 A 的 6 個 asyncio tests 驗的是「cancel → finally → idle」pattern 實作，沒有任何 test 問「正常按停止，預期應進哪個 mode？」若當時 test 案設計「正常錄音 → stop → 應進 review」，B1 語意偏差在單元層就會被抓到。**建議未來 test 設計要比對 spec 而非實作 intent**。

2. **Flet 相關 PR 必須 GUI + 真實 pipeline 時長實機驗證**（第三輪結語主張再印證）：本輪若沒跑到 180s summarizer 觸發，Bug #10/#11/#12 全都抓不到。

3. **「修 Bug 變出新 Bug」模式警訊**：Bug #10 直接源自 Bug #9 修復、Bug #12 是 Bug #9 連鎖 D 沒消失。整個 Pipeline lifecycle 層可能需要 **Researcher 做一次系統性架構 review 再讓碼農動手**，而非繼續一個 bug 一個 bug 打補丁。

---

## 規則遵守確認

- [x] **Regression 先跑** — 112/112，依任務第一步
- [x] **靜態複核碼農 diff** — A1/A2/A3/B1/C1 逐項對照 bug report
- [x] **協同甲方實機** — T1 有跑到 3+ 分鐘 summarizer 觸發點，才抓到 #11
- [x] **有新 bug 立刻回報、不 loop** — T1 觸發後即刻停驗，不做 T2/T3/S2-S9
- [x] **bug 分級 + 指派建議** — #10/#11/#12 全標邏輯類派碼農 A（依 team_roster 邏輯 = 碼農 A）
- [x] **devlog 已寫** — 本檔
- [x] **不動 code** — Verifier 角色，只驗證 / 診斷 / 報告

---

## 交棒大統領

待派工。若大統領決定派碼農 A 修 Bug #10/#11/#12，本人重驗清單已在 [[verification_report_20260405]] §8.6 列出（T1 5+ 分鐘 + T2 拔 Ollama + T3 匯入 + S2/S4/S5/S9）。

---

> 實驗者簽核：Bug #9 修復單元層綠燈但實機引發 Bug #10 資料遺失 + Bug #11 UI 凍結 + Bug #12 async gen 未消失；即刻停驗交棒大統領。
