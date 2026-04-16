---
title: 開發日誌 2026-04-16 — 研究者 Pipeline Lifecycle 架構 Review
date: 2026-04-16
type: devlog
status: active
author: 研究者（Researcher）
tags:
  - devlog
  - researcher
  - architecture
  - pipeline
  - bug-10
  - bug-11
related:
  - "[[pipeline_lifecycle_architecture_20260416]]"
  - "[[bug_report_flet_api_20260406]]"
  - "[[devlog_20260416_verifier_vphase4]]"
  - "[[devlog_20260416_builderA_bug9]]"
---

# 研究者 — Pipeline Lifecycle 架構 Review — 2026-04-16

> 前一棒：[[devlog_20260416_verifier_vphase4]]（實驗者 V4 實機撞 Bug #10 資料遺失 + Bug #11 UI 凍結；判斷「繼續打補丁會爆 Bug #13」，請大統領先派研究者做架構 review 再動手）

---

## 任務脈絡

V Phase 第四輪實機出三連爆（#10/#11/#12）。實驗者明確反思：
- 「單元測試綠燈 ≠ 符合 spec」（碼農 A 的 test 驗 implementation pattern，不驗 spec 語意）
- 「修 Bug 變出新 Bug」警訊 — 繼續一個 bug 一個 bug 打補丁風險高

大統領同意，派研究者做架構 review。不寫 code，只給 invariants + spec gap 清單 + 修復指引。Bug #12 不列入範圍。

---

## 執行紀錄

### Step 1 — 蒐集 input（全數讀完）

- [[CLAUDE.md]]（專案規範、角色）
- [[system_overview]] §3-§4（Pipeline 架構、週期摘要）
- [[data_schema]] §5（Session 生命週期 + status/mode 欄位）
- [[ui_spec]] §2.3 + §2.4（會中 / 會後模式）
- [[team_roster]]（確認研究者不改 code 的角色邊界）
- [[bug_report_flet_api_20260406]] §Bug #9/#10/#11/#12
- [[devlog_20260416_verifier_vphase4]]（實驗者反思整段）
- [[devlog_20260416_builderA_bug9]]（碼農 A B1 的 intent）
- [main.py](app/main.py)（on_start/on_import/on_stop/_run/_on_pipeline_done）
- [stream_processor.py](app/core/stream_processor.py)（L38-L88 主迴圈 + 收尾）
- [audio_recorder.py](app/core/audio_recorder.py)（async gen lifecycle，僅為理解 Bug #10 的 drain 路徑）
- [session_manager.py](app/core/session_manager.py)（save / end_recording / mark_ready）
- [summarizer.py](app/core/summarizer.py)（generate / _call_ollama 的 httpx 路徑）
- [audio_importer.py](app/core/audio_importer.py)（對稱理解兩條 _run 的差異）

### Step 2 — 拆出兩個 bug 的架構根因

**Bug #10 根因**（邏輯 + 語意）：
- [main.py:149-157](app/main.py#L149-L157) `on_stop_recording` 同時觸發軟停止（recorder 旗標）+ 硬中斷（pipeline_task.cancel）
- cancel 比旗標快 → 走 `except CancelledError: raise` → finally 切 idle → `_on_pipeline_done` 從未跑 → session_mgr.save 未執行
- 碼農 A 的 B1 語意翻轉：把 cancel 從「卡死安全網」當成「預設停止路徑」
- 與 [[data_schema]] L184-204 + [[ui_spec]] L189-191 明確衝突

**Bug #11 根因**（架構）：
- [stream_processor.py:59](app/core/stream_processor.py#L59) 主迴圈 inline `await summarizer.generate(...)`
- Gemma E2B CPU 推理 30-90s → 這個 task 的執行點停在這行
- 上游 async gen 沒人 consume → 逐字稿凍結
- 治本：summarizer 丟 background task

**兩 bug 糾纏**：Bug #11 凍結 → 甲方誤判 → 按停 → 觸發 Bug #10 資料遺失。

### Step 3 — 產出 research 文件

[[pipeline_lifecycle_architecture_20260416]]，含：
- §1 狀態機設計（8 轉換 + 7 invariants）
- §2 Bug #10 修復指引（4 組檢核 + 7 個動點 + 2 個實作方案）
- §3 Summarizer 並發三選項比較表 + 推薦 Option A（fire-and-forget）
- §4 Bug #11 修復指引（4 組檢核 + 6 個動點）
- §5 Regression tests 建議（10 個 spec-level tests + 5 項實機 checklist）
- §6 Spec gap 清單（7 項，含優先級與建議文字）
- §7 交棒建議（含派工順序）

---

## Research 結論摘要

### 核心 Invariants（7 條，全項破壞目前都已出現 bug）

| ID | 條文 | 對應 Bug |
|----|-----|---------|
| I1 | 任何離開 recording/stopping/finalizing 的路徑，Session 都必須落盤 | Bug #10 |
| I2 | 正常停止必須先完成 final summary 才觸發 UI 轉場 | Bug #10 |
| I3 | `pipeline_task.cancel()` 只在真卡死時啟動 | Bug #10 |
| I4 | Summarizer 執行不得 block audio_source consume | Bug #11 |
| I5 | UI mode 單一 SSoT = Session.status | G4 gap |
| I6 | Session 狀態轉換由 SessionManager API 專屬 | G4 gap |
| I7 | async gen cleanup 不產生新 yield | Bug #12（本次不修，但與 I1 有關）|

### 修復順序建議（與實驗者略不同）

實驗者 devlog 建議「#10 → #11 → #12」；**研究者建議 #11 → #10 → #12**。

理由：
- 修 #11 才能讓甲方實機測試時真的能跑滿 5+ 分鐘（目前 180 秒就凍結，測不到 #10 的完整 drain 路徑）
- #11 改動小（只動 stream_processor.py）、風險低，可先落地驗證
- #10 需要 G1/G2 spec gap 先定案才能開工，時序上本來就在 #11 之後
- 若碼農有信心也可並行修（兩個檔案不同）

### Summarizer 並發選型結論

Option A（fire-and-forget + `_summarizing` flag）。

理由：與 spec「週期性觸發 + 最多一個 pending」最相容；現有 `_summarizing` flag 幾乎就為此設計；改動最小；Option B 的 queue 對本專案是過度設計（觸發週期 180s 天然防連發）；Option C 不治本。

---

## Spec 缺漏建議（送大統領決定是否轉甲方裁決）

送研究者判斷的 7 項 gap（詳見 research doc §6）：

| ID | 嚴重度 | 內容 | 裁決權 |
|----|-------|------|-------|
| **G1** | 🟥 | Session.status 缺 `aborted` + `abort_reason` 欄位 — 直接影響 Bug #10 異常路徑修復形式 | **建議送甲方**（資料結構變更，對應 v4.0 規格變更類別） |
| **G2** | 🟥 | final summary 超時 + fallback 規範 | **大統領裁決**（實作細節） |
| G3 | 🟧 | 停止當下 pending summary 的處理規則 | 大統領裁決 |
| G4 | 🟧 | Session.status vs UI mode 的 SSoT 規則 | 大統領裁決 |
| G5 | 🟨 | `recorder.stop()` 語意澄清（設旗標 vs 阻塞停止） | 大統領裁決（重構後自然明確） |
| G6 | 🟨 | Summarizer 併發模型寫進 system_overview §4.1 | 大統領裁決 |
| G7 | 🟩 | 系統級「異常處理原則」總則缺失 | 大統領裁決（或延後） |

**強烈建議**：G1 + G2 敲定前碼農**不要動手**，否則修完要二度改。

---

## 交棒大統領

### 建議下一步派工順序

1. **大統領裁決 G1/G2**（必要）+ G3~G7（選用）
   - G1 若送甲方：研究者可協助擬「為什麼需要加 aborted 狀態」的一頁說明（本 research doc §6.G1 可直接引用）
   - G2~G7：大統領內部裁決即可

2. **spec 更新**（由大統領或授權碼農）
   - `data_schema.md` 增補 status + abort_reason
   - `system_overview.md` §4.2 增補 summary 併發 + timeout 規則
   - `ui_spec.md` §2.4 可選補「停止中...」UI 狀態提示

3. **派碼農 A 修 Bug #11**（依 research §4）
   - 單一 commit，單元測試 + 實驗者協同短測
   - 驗收條件：[[pipeline_lifecycle_architecture_20260416#§5 新增 Regression Tests 建議|§5]] 的 test_summarizer_does_not_block_transcription 綠燈 + 實機 5 分鐘錄音逐字稿不凍結

4. **派碼農 A 修 Bug #10**（依 research §2）
   - 需 Bug #11 修完 + G1/G2 敲定後開工
   - 驗收條件：§5 的 test_stop_recording_* 系列全綠 + 實機 5 分鐘停止 → review + data/sessions 有檔

5. **Bug #12**（async gen finally-yield）可併入 Bug #10 的 PR，或單獨由碼農 A 處理

6. **Reviewer 審 PR**：對照本研究 §1.4 invariants 清單逐項勾選

7. **實驗者 V Phase 第五輪**：依 §5.2（單元）+ §5.3（實機）checklist 重驗

### 若架構 review 發現更深層問題

本次 review **未** 發現 Flet task model 與 spec 預期根本不相容的問題。Flet 0.84.0 的 `page.run_task` 行為本身 OK，問題純在於我方 Pipeline 邏輯對 stop 的語意寫錯。

唯一 Flet 層面的未決項：**Flet 事件 callback 是否支援 async**（研究者方案 A 需要）。若碼農動手時發現 Flet 不支援 async callback，請回報，研究者再補研究（可能退回方案 B 或用 `page.run_task(async_handler)` 包一層）。

---

## 規則遵守確認

- [x] **不寫 code** — research doc 與本 devlog 0 行 Python
- [x] **不直接改 spec** — 所有 spec 變更建議僅列入 §6 送大統領/甲方裁決
- [x] **不補 bug_report 章節** — 架構 review 是獨立 research 文件（`doc/research/`）
- [x] **引用 spec / code 用 wikilink 或行號連結**
- [x] **發現 spec 矛盾 / 漏寫列 §6，不腦補** — 7 項 gap 全寫明出處與建議文字
- [x] **devlog 已寫** — 本檔

---

> 研究者簽核：Pipeline Lifecycle 架構 Review 完成。7 invariants + 3 option 選型 + 7 spec gaps + 10 regression tests 已在 [[pipeline_lifecycle_architecture_20260416]] 列出。交棒大統領裁決 spec gap + 派工碼農 A。
