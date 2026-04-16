---
title: 開發日誌 2026-04-16 — 碼農 A 修 Bug #9 Pipeline/Recorder Lifecycle
date: 2026-04-16
type: devlog
status: active
author: 碼農 A（Builder A）
tags:
  - devlog
  - builder-a
  - bug-9
  - pipeline-lifecycle
  - error-handling
  - flet
related:
  - "[[bug_report_flet_api_20260406]]"
  - "[[verification_report_20260405]]"
  - "[[devlog_20260416_verifier_vphase3]]"
  - "[[devlog_20260416_builderB_bug8]]"
---

# 碼農 A — Bug #9 Pipeline Lifecycle 修復 — 2026-04-16

> 前一棒：[[devlog_20260416_verifier_vphase3]]（實驗者 V Phase 第三輪甲方協同時撞上 Bug #9，交大統領派工 → 派給我）
> Bug 規格：[[bug_report_flet_api_20260406]] §「Bug #9」含完整根因 A/B/C/D 與修復建議 A1-E

---

## Bug #9 根因摘要（為什麼原本會殭屍）

甲方按「開始錄音」後，faster-whisper + Pipeline 運作到約 3 分鐘觸發內部例外。舊版 [main.py:68-75](app/main.py#L68-L75) 的 `_run`：

```python
async def _run():
    try:
        await processor.run(recorder.start(), session)
    except Exception as e:
        logger.error(f"Pipeline error: {e}")  # 空 str(e)，log 只留 "Pipeline error:"
        page.show_dialog(ft.SnackBar(content=ft.Text(f"處理失敗：{e}")))
```

三個獨立缺陷疊加造成「殭屍 live 模式」：

| 缺陷 | 後果 |
|---|---|
| A：沒 `finally` 呼叫 `recorder.stop()` | Pipeline 掛掉後 `AudioRecorder` 仍持有 `_recording=True` 和 sounddevice InputStream，計時器 UI 繼續跑 |
| B：`str(e)` swallow 空訊息例外 + `logger.error` 不帶 traceback | 甲方看不到 SnackBar 內容、log 無根因可查 |
| C：異常路徑沒把 `dashboard` 切回 idle / review | UI 留在 live 狀態，逐字稿區繼續顯示新 segment（時間戳歸零因 pipeline restart 副作用） |
| 衍生：`on_stop_recording` 只呼叫 `recorder.stop()` 設旗標 | recorder 的 async generator 已被 abandon，沒有 consumer 推進它；stop 按鈕看似無效 |

> 完整拆解見 [[bug_report_flet_api_20260406]] §Bug #9「根因拆解」。

---

## 本次 diff 位置與邏輯變動

**單一檔案修改**：[main.py:42-157](app/main.py#L42-L157)
**新增測試檔**：[tests/test_main_pipeline_lifecycle.py](tests/test_main_pipeline_lifecycle.py)（6 個 asyncio 單元測試）

### A1 — `on_start_recording._run` 例外處理（[main.py:84-108](app/main.py#L84-L108)）

```python
async def _run():
    completed_normally = False
    try:
        await processor.run(local_recorder.start(), session)
        completed_normally = True
    except asyncio.CancelledError:
        logger.info("Recording pipeline cancelled by user")
        raise
    except Exception as e:
        logger.exception("Recording pipeline error")  # 完整 traceback
        _show_pipeline_error(e, "錄音處理")
    finally:
        try:
            await local_recorder.stop()  # 保證 recorder 停，即使 except 路徑
        except Exception:
            logger.exception("Recorder stop failed in finally")
        if not completed_normally:
            try:
                dashboard.set_mode("idle", None)
                main_view.status_bar.set_meeting_mode(False)
                page.update()
            except Exception:
                logger.exception("Dashboard reset to idle failed")
```

**邏輯變動**：
- `except asyncio.CancelledError: raise` 不吞 cancel，讓 task 正確傳遞取消狀態
- `logger.exception` 取代 `logger.error(f"...: {e}")` — 寫入完整 traceback 到 log
- `finally` 區塊無條件呼叫 `local_recorder.stop()`，解決 A 根因
- `completed_normally` flag 避免 double-transition：正常完成時 `_on_pipeline_done` 已把 UI 切到 review，finally 不應覆蓋

> 額外防守：`local_recorder = recorder` 快照，避免 nonlocal `recorder` 在 _run 跑途中被另一次 `on_start_recording` 覆蓋（雖然 UI 流程不太可能發生，但便宜）。

### A2 — SnackBar 訊息保證非空（[main.py:54-66](app/main.py#L54-L66)）

抽出共用 helper `_show_pipeline_error`：

```python
def _show_pipeline_error(err: BaseException, origin: str):
    err_type = type(err).__name__
    err_msg = str(err) or "(無錯誤訊息)"
    text = f"{origin}失敗：{err_type} — {err_msg}"
    page.show_dialog(ft.SnackBar(
        content=ft.Text(text),
        duration=30000,  # 30 秒，確保甲方看到
    ))
    page.update()
```

**邏輯變動**：
- `type(err).__name__` 保證有錯誤類別（解決 `str(e) == ""` 時 SnackBar 空白）
- `duration=30000` 拉長停留時間（Flet SnackBar 預設約 4 秒）
- 把 `page.show_dialog` call site 集中，兩個 `_run` 共用

### A3 — `on_import_audio._run` 同步處理（[main.py:126-145](app/main.py#L126-L145)）

匯入音檔路徑鏡像 A1+A2，差異：
- 無 `recorder.stop()`（匯入沒 recorder）
- 異常時 `dashboard.set_mode("review", session)` 而非 idle（C1 決策：已 yield 的 segments 已寫入 session，保留給甲方審閱）

### B1 — 保留 task handle + stop 時 cancel（[main.py:49, 70, 110, 113, 147, 149-157](app/main.py#L149-L157)）

```python
pipeline_task: asyncio.Task | None = None  # nonlocal，兩個 _run 共用一個 slot

# 在兩個啟動點：
pipeline_task = page.run_task(_run)

def on_stop_recording():
    nonlocal recorder, pipeline_task
    if recorder:
        page.run_task(recorder.stop)  # 正常路徑：讓 generator 自然收尾走 final summary
    if pipeline_task is not None and not pipeline_task.done():
        pipeline_task.cancel()  # 安全網：若 pipeline 卡住（或上一個 crash 還沒收尾），強制 cancel
```

**邏輯變動**：
- 任何 pipeline 啟動都記錄 task handle 到 nonlocal `pipeline_task`
- 停止時先請 `recorder.stop()`（設旗標），再 `cancel()` 安全網
- 已 done 的 task cancel 是 no-op，所以 crash 後再按 stop 也安全（雖然此時 finally 已把 UI 切 idle，stop 按鈕已不在 live UI 上）

### C1 — Pipeline 異常 UI 回 idle / review

已在 A1 / A3 的 `finally` 區塊內實作。關鍵設計：
- 錄音路徑：idle（session 資料不完整，不值得保留給審閱）
- 匯入路徑：review（部分 segments 已寫入 session，給甲方看）

### 不做項目（bug report §「修復方向建議」D / E）

- **D**（`audio_importer.py:23` `GeneratorExit` 警告）：未改動。實驗者已說明 A+B+C 修好後應自然消失
- **E**（transcriber reset 時間戳歸零）：未改動。Pipeline 不再崩潰後此現象不再重現

---

## 自測結果

### 1. 自動化 regression（fast suite）

```
python -m pytest -m "not slow and not real_audio" -q
→ 112 passed, 22 deselected, 1 warning in 15.07s
```

| 項目 | 狀態 |
|---|---|
| baseline 106 fast tests | ✅ 全過 |
| 新增 [test_main_pipeline_lifecycle.py](tests/test_main_pipeline_lifecycle.py) 6 tests | ✅ 全過 |
| 合計 | ✅ 112 passed / 0 failed |

> 註：bug report / 任務中提到「127 tests」是早期一次性合併 `test_transcriber` + `test_knowledge_base` 的合計；實驗者第三輪改為以 `-m "not slow and not real_audio"` 為 baseline，得 106 fast。新增 6 個 lifecycle tests 後為 112。無 regression。

### 2. 新增測試覆蓋範圍（[tests/test_main_pipeline_lifecycle.py](tests/test_main_pipeline_lifecycle.py)）

提煉 `_run` 的 lifecycle pattern（移除 Flet runtime 依賴），用 asyncio + fake recorder 驗證：

| 測試 | 驗證點 |
|---|---|
| `test_recording_normal_completion_does_not_reset_ui` | 正常完成不覆寫 `_on_pipeline_done` 的 review 切換 |
| `test_recording_exception_resets_to_idle_and_stops_recorder` | **Bug #9 核心**：例外 → finally → recorder.stop + UI 切 idle |
| `test_recording_cancelled_propagates_but_finally_runs` | **B1**：CancelledError 向上拋，但 finally 仍跑（recorder.stop + idle） |
| `test_recording_exception_message_non_empty_for_snackbar` | **A2**：空訊息例外仍產生可見文字（含 `type(e).__name__` + fallback） |
| `test_import_exception_resets_to_review_not_idle` | **C1**：匯入路徑異常 → review 而非 idle |
| `test_import_normal_completion_no_review_reset` | 匯入正常完成不覆寫 `_on_pipeline_done` |

### 3. App import / parse smoke

```
python -c "import app.main; import ast; ast.parse(open('app/main.py',encoding='utf-8').read())"
→ import OK / parse OK
```

### 4. 5+ 分鐘實機錄音 — **CLI 無法執行，必須實驗者協同甲方做**

- 碼農 A 的 CLI 環境**沒有 GUI driver**（Flet Desktop 無 pytest-qt / playwright 類工具），無法真正觸發 Pipeline 在 3 分鐘後的例外，也無法目視確認 SnackBar / Dashboard 狀態轉換
- 這點與實驗者第三輪 devlog（[[devlog_20260416_verifier_vphase3]]）提到的 GUI autonomous 限制一致
- 單元測試（上述 6 個 asyncio tests）只能驗證 `_run` 的 lifecycle **pattern** 正確；無法覆蓋：
  - faster-whisper 長時間跑真實音訊的 memory / IO 路徑
  - Flet `page.run_task` / `page.show_dialog` 實際在 runtime 的行為
  - sounddevice InputStream 的釋放時序

### 5. 拔 Ollama 模擬 Pipeline 例外 — **CLI 無法執行**

同上理由。碼農無法在 CLI 啟 Flet App + 人工 `ollama stop` 觀察 GUI 反應。

> 本人對這個 blocker 的處置：**不跳驗證、不假稱通過**。單元測試已證 lifecycle pattern 的正確性；剩餘實機驗證明確委交實驗者（見下節「實驗者重驗遞交清單」）。

---

## 實驗者重驗遞交清單

交付物：
- [main.py](app/main.py)（diff 位置見「本次 diff 位置」表）
- [tests/test_main_pipeline_lifecycle.py](tests/test_main_pipeline_lifecycle.py)（新增）
- 本 devlog

請實驗者依 [[bug_report_flet_api_20260406]] §Bug #9「驗證條件」逐項檢核：

1. **Regression**：`python -m pytest -m "not slow and not real_audio" -q` → 預期 112 passed / 0 failed
2. **5-10 分鐘實機錄音**（協同甲方）：
   - [ ] 啟動 App → 開始錄音 → 刻意跑滿 5 分鐘以上
   - [ ] 若 Pipeline 掛：log 需有 `ERROR:...Recording pipeline error` + 完整 traceback（而非空 `Pipeline error:`）
   - [ ] GUI 彈出 SnackBar，文字包含錯誤類別（如 `RuntimeError — xxx`），停留 30 秒
   - [ ] Dashboard **自動** 回 idle，計時器停，status_bar 離開 meeting_mode
3. **停止按鈕測試**：
   - [ ] 正常錄音中按「停止」→ recorder 停 + pipeline_task cancel → UI 回 idle（會跳過 final summary，這是 B1 設計選擇）
   - [ ] 3 分鐘後若 Pipeline 自己掛 → UI 早已回 idle（無 stop 按鈕可按）
4. **拔 Ollama 模擬**：
   - [ ] 啟動 App → 開始錄音 → 中途 `ollama stop`
   - [ ] 等 Pipeline 週期摘要觸發 → 應在 summarizer 呼叫時炸例外
   - [ ] 觀察同 #2 檢核點
5. **匯入音檔路徑**（若有 real_audio fixture 可用）：
   - [ ] 匯入一個會觸發例外的音檔（或中途拔 Ollama）
   - [ ] GUI 回 review 而非 idle（已 yield 的 segments 可見）
6. **S2/S4/S5/S9** GUI smoke test（依 [[verification_report_20260405]] §7.4 表）：
   - Bug #9 修完後應該不再阻塞 S3，進而可續跑 S2 響應式、S4 對話框、S5 SnackBar、S9 拖動切換

> 若重驗發現 finally 區塊本身拋例外、或 `pipeline_task.cancel()` 行為與預期不符，請直接開 Bug #10 報回，我再修。

---

## 規則遵守確認

- [x] **不改 specs** — 這是邏輯層/錯誤處理修復，不涉及 `doc/specs/` 變更
- [x] **不跳實機驗證** — 明確標示實機錄音 + 拔 Ollama 為 CLI blocker，委交實驗者，不偽稱通過
- [x] **自測失敗先內部修** — 112 tests 全過、import smoke 通，無內部失敗遺留
- [x] **devlog 已寫** — 本檔
- [x] **scope 只動本任務相關檔案** — 僅 [main.py](app/main.py) + 新增 [test_main_pipeline_lifecycle.py](tests/test_main_pipeline_lifecycle.py)；未附帶修復其他區域

---

## 待大統領裁決

- 交棒大統領派工實驗者做 5-10 分鐘實機錄音 + 拔 Ollama 模擬（依上述遞交清單）
- 若實驗者重驗通過 → 連帶掃完 S2/S4/S5/S9 → 可送甲方最終簽核
- 若重驗發現問題 → 回到本人繼續修

---

> 碼農 A 簽核：A1/A2/A3/B1/C1 已依 bug report §「修復方向建議」實作；單元層綠燈；實機驗證交棒。
