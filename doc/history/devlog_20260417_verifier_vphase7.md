---
title: 開發日誌 2026-04-17 — 實驗者 V Phase 第七輪（Bug #13/#14/#15 實機全驗 + 發現 Bug #16/#17）
date: 2026-04-17
type: devlog
status: complete
author: 實驗者（Verifier）
tags:
  - devlog
  - verifier
  - v-phase
  - v-phase-7
  - bug-13
  - bug-14
  - bug-15
  - bug-16
  - bug-17
  - invariants
related:
  - "[[verification_report_20260405]]"
  - "[[devlog_20260417_builderA_bug13]]"
  - "[[devlog_20260417_builderB_bug14_miclive]]"
  - "[[devlog_20260417_builderB_bug15]]"
  - "[[devlog_20260417_verifier_vphase6]]"
  - "[[bug_report_flet_api_20260406]]"
---

# 實驗者 V Phase 第七輪 — Bug #13/#14/#15 實機全驗 + 發現 Bug #16/#17 — 2026-04-17

> 前一棒：
> - 碼農 A (f6dc568) Bug #13 輪詢方案 + 碼農 B (481b36e/458ae75/edcb35a) Bug #14 _mounted + Mic Live
> - 碼農 B (8362c69+9cff34e) Bug #15 方案 A setter + A1 Mic Test fallback + `tests/integration/` 建立（回應 V6 反思）
> - 146 fast tests 全綠
>
> 完整結果：[[verification_report_20260405#十一、V Phase 第七輪]]
> 完整 raw log：`doc/reports/vphase7_raw.log`

---

## 第七輪結果總表

| Step | 任務 | 結果 | 關鍵摘要 |
|---|---|---|---|
| 1 | Regression | ✅ 146 passed | V6 baseline 140 → +6 integration + fallback tests |
| 2 | 靜態複核 Bug #15 setter + A1 fallback + integration tests | ✅ | 全對齊研究者 §6.3 Pattern A + A1 方案 |
| 3 | Bug #15 實機 Mic Test A1 fallback | ✅ **PASS** | 甲方「音量條有動、麥克風要選對」— ui_spec §2.5 設計目標達成 |
| 3 | Bug #13 實機 停止按鈕反應 | ✅ **PASS** | `transition: recording → processing → ready` 順暢、log 無 `TypeError: ...asyncio.Future` / 無 `drain exceeded` |
| 3 | Bug #14 實機 review 轉場 + 分頁切換 | ✅ **PASS** | `_build_review` 內 `update_highlights/decisions/set_items` 不炸；切詞條/回饋/設定/會議全 OK；log 無 `Control must be added to the page first` |
| 3 | Bug #12 回歸確認 | ✅ **PASS** | `grep "async generator ignored GeneratorExit"` = 0 |
| 3 | I1-I7 實機覆蓋 | ✅ **全 PASS** | session 42KB 落盤 + 180 segments + summary_history[1,2,3] + Whisper/Ollama 並行 |
| 4 | S2/S9 響應式佈局 | ✅ PASS | 三段式拖動切換正常 |
| 4 | S4 會議資訊對話框 | ✅ PASS | T1 開始錄音流程 |
| 4 | **S4 匯出 Markdown FilePicker** | 🔴 **FAIL** | **Bug #17 candidates — `Session closed`** |
| - | **Gemma V2/V3 summary** | 🔴 **發現 Bug #16** | V1 有內容、V2/V3 空 `fallback_reason=None` — 甲方實機報告「重點和 action 不見了變空白」|

## 核心意義

**Desktop 版本的 pipeline lifecycle 鋼骨完整**：
- 資料保全（Bug #10/#11/#12 → V5 驗完）
- 停止按鈕 + UI 轉場（Bug #13/#14 → V7 驗完）
- Mic Live 診斷（Bug #15 → V7 驗完）
- 7 條 invariants 實機全閉環

**剩下 Bug #16/#17 屬於功能層 bugs**（摘要解析穩定、FilePicker Flet API 使用）— 不動 pipeline 架構可修完。

---

## 實機協同詳記

### 啟動 + Mic Test（Bug #15 A1 fallback）

- Monitor 啟動：`python -u -m app.main | tee doc/reports/vphase7_raw.log | grep -E "..."`（V5 驗證有效的寬 filter + tee 完整 log 策略）
- 甲方點 idle「🎤 測試麥克風」→ 音量條有動 + peak dBFS 顯示 + 倒數正常結束
- 甲方自述：**「有動，麥克風要選對」** — 這是 ui_spec §2.5 Mic Live 設計目標的教科書案例：甲方透過 Mic Test 即時診斷 Windows 麥克風 device 選擇（V5 那次 peak -52 dBFS 全靜音的症狀當場解決）

### T1 5-6 分鐘錄音 + 停止

調好麥克風後按「開始錄音」，log 首個關鍵事件：

```
INFO:faster_whisper:Processing audio with duration 00:10.010
INFO:faster_whisper:VAD filter removed 00:00.000 of audio   ← V5 是 removed 10.010 全靜音
```

對比 V5，這次 VAD 幾乎不過濾，代表真實人聲完整進入 Whisper transcribe。

逐字稿每 10 秒產出；跨 180 秒 Gemma 第一次週期 summary 觸發：

```
INFO:faster_whisper:Processing audio with duration 00:10.010
INFO:faster_whisper:VAD filter removed 00:00.560 of audio
INFO:httpx:HTTP Request: POST http://localhost:11434/api/generate "HTTP/1.1 200 OK"   ← V1 summary 200 OK
INFO:faster_whisper:Processing audio with duration 00:10.010                             ← Whisper 並行 ✅ I4
```

**I4 實機驗證 PASS**：Ollama POST 和 Whisper Processing log 同期間交錯出現 → summary task 跑時主迴圈不阻塞。

甲方 04:17 截圖（錄音中）看到 V1 summary 已填入「會議重點 / 決議事項 / Action Items」（真實 AI 產出，非 V5 placeholder）。

6 分鐘按停止：

```
INFO:httpx:HTTP Request: POST http://localhost:11434/api/generate "HTTP/1.1 200 OK"    ← V2 週期
INFO:app.core.session_manager:Session fc46d26b-... transition: recording → processing ← 停止觸發 I6
INFO:httpx:HTTP Request: POST http://localhost:11434/api/generate "HTTP/1.1 200 OK"    ← V3 final
INFO:app.core.session_manager:Session fc46d26b-... transition: processing → ready      ← I2
```

**無 RuntimeError / TypeError / async gen warning**。

Session disk 驗證：42KB，180 segments，`status: ready`、`mode: review`、`summary.is_final: True`。

**Bug #13/#14/#15 + I1-I7 全實機 PASS** ✅

### Bug #16 發現（甲方反饋驅動）

甲方按停止後 UI 進 review，但截圖顯示重點 / action_items / 決議事項**變空白**。對比錄音中 04:17 截圖有完整 V1 內容。Disk 側驗證：

```
summary_history:
  V1 (180s 週期, is_final=False, fallback=None): highlights 103 字, action=2, decision=3, keywords=3, gen=97s
  V2 (360s 週期, is_final=False, fallback=None): highlights 0 字, action=0, decision=0, keywords=0, gen=83s
  V3 (final,     is_final=True,  fallback=None): highlights 0 字, action=0, decision=0, keywords=0, gen=23s
session.summary = V3 （空）
```

V2 + V3 Gemma 有回應（83s / 23s 非 timeout 非 exception）、fallback_reason=None、但 parse 後的 SummaryResult 全空。UI `on_summary(V2)` + `on_summary(V3)` 覆蓋 V1 顯示 → 甲方看到空白。

**這不是 pipeline lifecycle bug**，是 **summarizer/Gemma parse 層 bug**（見 §11.7）。

### Bug #17 發現（甲方實機反饋驅動）

甲方在 review 模式按「匯出 Markdown」按鈕 → UI 無任何反應（按鈕無 hover 效果、無彈窗、工作列無變化）。相對「提交回饋」按鈕有反應。

**差別**：`_handle_export` 是 async method + 用 `ft.FilePicker().save_file(...)`；`_handle_submit_feedback` 是同步。

甲方多次嘗試後 Monitor 抓到完整 Traceback：

```
File "app/ui/dashboard_view.py:995", _handle_export
  await picker.save_file(...)
File "flet/controls/services/file_picker.py:290", save_file
File "flet/controls/base_control.py:398", _invoke_method
File "flet/messaging/session.py:392", invoke_method
RuntimeError: Session closed
```

**根因**：`picker = ft.FilePicker()` 建立後**沒加到 `page.overlay`**。Flet 0.84 的 `save_file` 透過 session message channel dispatch 到 client，picker 未 mount → `RuntimeError: Session closed`。

**同類殘留**：`_handle_import_audio`（pick_files 路徑，V4 曾 PASS 但 V7 未重測）+ terms_view `_on_import`。

## 反思 — V7 暴露第四層 gap (L4)

| 層 | V 輪 | Gap 發現 | 對應補的測試層 |
|---|---|---|---|
| L1 | V4 | 單元綠燈 ≠ spec | V5 spec-level invariants tests（+14 個）|
| L2 | V5 | spec 綠燈 ≠ framework runtime | V6 contract tests T-F1~F8（+10 個）|
| L3 | V6 | contract 綠燈 ≠ 跨模組 wiring | V7 integration smoke tests（+6 個）|
| **L4** | **V7** | **wiring 綠燈 ≠ 框架服務使用契約（L4a）+ 外部模型輸出穩定（L4b）** | **V8 建議 a) Flet services contract test b) Gemma 輸出穩定性 regression** |

### L4a — 框架服務使用契約

Bug #17 暴露：FilePicker 必須先 `page.overlay.append(picker)` 才能用。這是 Flet 框架的**使用慣例契約**，不屬於 API 簽章（contract test T-F1 只驗 `page.run_task` 回傳型別），也不屬於 cross-module wiring（integration smoke test 只驗 main.py glue）。

建議 V8 契約測試擴充：用 `inspect` + grep pattern 驗專案裡**所有** `ft.FilePicker()` 創建處，其前後必定有 `overlay.append`。類似 spec：
```python
def test_all_filepicker_usages_mount_to_overlay():
    sources = [Path("app").rglob("*.py")]
    for f in sources:
        content = f.read_text()
        if "ft.FilePicker()" in content:
            assert "overlay.append" in content, f"{f} has FilePicker without overlay mount"
```

### L4b — 外部模型輸出穩定性

Bug #16 暴露：Gemma E2B 在 V2+ 增量 summary（含前次 summary 當 context）下輸出結構化內容失敗。**目前 summarizer unit test 用 fake Ollama 固定 response，無法 catch 真實 Gemma 輸出失控**。

建議 V8 新類測試：
- 用真實 segments（測試 fixture）跑 summarizer → assert `summary.highlights` 不為空字串、`action_items` 不為空 list
- 作為 `-m real_audio` 類的 slow test，手動觸發 CI 跑
- 或者 pure unit：mock Gemma 回不同類別的壞輸出（空字串、只有 whitespace、非 JSON、format 壞）驗 summarizer parser **要嘛正確 parse 要嘛 fallback**，絕不 silent 回 empty SummaryResult

---

## 守本分

- ❌ 不改 code（V7 三次實機抓 observation 全交給碼農）
- ❌ 不改 spec（Bug #16/#17 是 bug 不是 spec gap）
- ✅ 產出報告 + devlog + 新增 Bug #16/#17 bug_report 章節
- ✅ 抓到 Bug #16/#17 根因（甲方反饋 + Monitor Traceback + disk JSON）

## 交棒

| 對象 | 請求 |
|---|---|
| **大統領** | 派工優先級：(1) 碼農 B 修 Bug #17 FilePicker overlay + 附帶 Obs-8 stopping indicator；(2) 碼農 A 或研究者查 Bug #16 Gemma 空摘要；(3) 碼農 A 查 Obs-5/6/7（非阻塞）|
| **甲方** | 靜候派工完畢；V Phase 第八輪時準備再跑一次完整 10 分鐘錄音 + 停止 + 匯出（驗 Bug #16/#17 修復） |
| **碼農 A** | 待命；可先查 summarizer.py 的 Gemma response parser + 為 V2/V3 加 debug log |
| **碼農 B** | 待命；Bug #17 修法明確（三處 FilePicker 加 overlay），Bug #17 + Obs-8 可併入一個 PR |
| **研究者** | 待命；若 Bug #16 根因在 Gemma E2B 本身穩定性而非 parser bug，可能需補 Gemma 模型調用 research（context window 管理、增量 prompt 策略） |

> 實驗者簽核：**V7 Bug #13/#14/#15 + I1-I7 實機全綠；Desktop pipeline lifecycle 鋼骨完整**。新發現 Bug #16（Gemma parse 空）+ Bug #17（FilePicker overlay）阻塞甲方最終簽核。已產出完整報告 + Bug #16/#17 章節。等修完再 V Phase 第八輪。
