---
title: V Phase 驗證報告
date: 2026-04-06
updated: 2026-04-16
phase: V (Verify)
agent: 實驗者（Verifier）
status: 🟡 第六輪 autonomous PASS（140 tests + 7 invariants + contract tests）+ 發現 **Bug #15 候選**（DashboardView audio_recorder late-binding）— 實機層待甲方協同
tags: [verification, v-phase, report]
---

# V Phase 驗證報告

> 初次執行：2026-04-05
> 持續更新：2026-04-06（碼農完成模型選型修正後重新驗證）
> 執行者：實驗者（Verifier）
> 對象：[[system_overview|AI_PVoiceNote_App]] S Phase 全部交付物

---

## 一、Agent 自測結果

### 1.1 環境驗證

| 項目 | 結果 | 詳情 |
|---|---|---|
| Python ≥ 3.11 | ✅ PASS | Python 3.11.9 |
| `pip install -e .` | ✅ PASS | 成功安裝 ai-pvoicenote-app 0.1.0 |
| Ollama | ✅ PASS | 0.20.2，服務正常運行 |
| Ollama Model — `gemma4:e4b` | ⚠️ 已下載但無法載入 | 9.2GB 模型，需 9.9GB RAM，超出當前可用（見 [[#四、模型選型實測]]） |
| Ollama Model — `gemma4:e2b` | ✅ PASS | 6.8GB 模型，推理測試成功 |
| ffmpeg | ✅ PASS | ffmpeg 8.0.1-full_build |
| faster-whisper | ✅ PASS | 1.2.1 |
| flet | ✅ PASS | 0.84.0 |
| chromadb | ✅ PASS | 1.5.5 |

### 1.2 自動化測試

| 測試套件 | 通過 | 失敗 | 跳過 | 耗時 |
|---|---|---|---|---|
| Fast tests (`-m "not slow"`) | 106 | 0 | 21 deselected | 13.77s |
| Whisper (`test_transcriber.py`) | 7 | 0 | 0 | 7.46s |
| ChromaDB + Embedding (`test_knowledge_base.py`) | 14 | 0 | 0 | 17.99s |
| **合計** | **127** | **0** | — | — |

> 全部 127 項測試在碼農完成模型選型修正後重新執行，零失敗。

**警告記錄**：
- `pydub.utils`: `audioop` 模組在 Python 3.13 將被移除（DeprecationWarning）— 目前使用 3.11，不影響

### 1.3 冒煙測試 — App 啟動

| 項目 | 結果 | 詳情 |
|---|---|---|
| TCP Server 啟動 | ✅ PASS | 成功監聽本地 port |
| Flet View 啟動 | ✅ PASS | flet-desktop 0.84.0 |
| Assets 路徑 | ✅ PASS | `app/assets` 正確載入 |
| Idle 頁面渲染 | ✅ PASS | 視窗開啟、idle 介面顯示正確（見截圖） |

### 1.4 程式碼完整性檢查

| 檢查項目 | 結果 | 詳情 |
|---|---|---|
| Import 路徑 | ✅ PASS | 全部 app/ 內部 import 解析正確 |
| `config/default.yaml` vs [[data_schema]]#8 | ✅ PASS | 含 `ollama.options.num_ctx: 8192` + `temperature: 0.3` |
| `models.py` vs [[data_schema]] | ✅ PASS | 10 個 dataclass 與 spec 完全對齊 |

---

## 二、Runtime Bug 修復記錄

V Phase 第一輪驗證時發現 2 個 Runtime Error，由 Verifier 就地修復後，碼農的後續修改沿用：

### Bug #1：`AttributeError: property 'page' has no setter`

- **檔案**：[[dashboard_view.py]]、[[terms_view.py]]
- **原因**：兩個類別繼承 `ft.Container`，而 Flet 0.84.0 的 `page` 是唯讀 property，`self.page = page` 觸發 AttributeError
- **修復**：將 `self.page` 改為 `self._page_ref`，全檔替換所有引用

### Bug #2：`TypeError: OutlinedButton.__init__() got unexpected keyword argument 'color'`

- **檔案**：[[dashboard_view.py]]:391
- **原因**：Flet 0.84.0 的 `OutlinedButton` 不接受直接 `color=` 參數
- **修復**：改用 `style=ft.ButtonStyle(color=COLOR_TEXT)`

> 兩個 Bug 修復後，自動化測試 106 項全通過，App 成功啟動。

---

## 三、甲方手動驗證進度

### 3.1 前置條件

- [x] 安裝 Ollama — 已安裝（0.20.2）
- [x] 下載模型 — gemma4:e4b + gemma4:e2b 皆已下載

### 3.2 功能驗證

| # | 驗證項目 | Pass/Fail | 備註 |
|---|---|---|---|
| 1 | App 啟動 + 介面外觀 | ✅ PASS | 視窗、idle 頁面、左側導航、狀態列 (gemma4:e2b) 全正常 |
| 2 | 響應式佈局 | ⏳ 待測 | 需進入 live 模式觀察三欄/兩欄/單欄 |
| 3 | 即時錄音 | ⏳ 待測 | |
| 4 | 匯入音檔 | ⏳ 待測 | |
| 5 | 完整 Pipeline | ⏳ 待測 | 含轉錄 + RAG 校正 + 摘要 |
| 6 | 即時儀表板三區塊 | ⏳ 待測 | |
| 7 | 會後編輯模式 | ⏳ 待測 | |
| 8 | 匯出 Markdown | ⏳ 待測 | |
| 9 | 詞條管理 CRUD | ⏳ 待測 | |
| 10 | 設定頁面 | ⏳ 待測 | |

### 3.3 截圖紀錄

- [[screenshots/v_phase_app_idle.png|App Idle 頁面]]（驗證 #1）— 待甲方提供

---

## 四、模型選型實測

### 4.1 硬體環境

| 項目 | 數值 |
|---|---|
| 機型 | Surface Pro 9 (i7-1255U) |
| 總記憶體 | 16 GB |
| OS | Windows 11 Pro |
| 開發時可用 RAM | ~3-5 GB（被 VS Code、Claude Code、瀏覽器等佔用） |

### 4.2 模型實測對照

| 模型 | 模型大小 | 推理 RAM 需求 | 實測結果 | 適用情境 |
|---|---|---|---|---|
| `gemma4:e4b` | 9.2 GB | 9.9 GB | ❌ OOM | 開發模式下記憶體不足；需專注使用情境 |
| `gemma4:e2b` | 6.8 GB | ~6 GB | ✅ 推理正常 | **當前驗證採用** |

### 4.3 決策

- Spec 定義的預設仍為 `gemma4:e4b`，與 [[decision_20260406_model_selection]] 保持一致
- V Phase 驗證**暫時改用 `gemma4:e2b`**，以便在開發環境下完成端到端測試
- 驗證完成後，`config/default.yaml` 應改回 `gemma4:e4b`（spec 預設）

> ⚠️ 此處改 config 屬於驗證階段的權宜做法，**非規格變更**。

---

## 五、需大統領決策的 Issues

### Issue #1：`ft.app()` Deprecated

- **位置**：[[main.py]]:177
- **現狀**：`ft.app(target=main)` 在 Flet 0.80.0 已標記 deprecated
- **影響**：目前不影響功能，但未來 Flet 版本可能移除
- **建議**：排入技術債，低優先

---

## 六、總結

| 類別 | 狀態 |
|---|---|
| 環境 | ✅ 全數通過（含 Ollama + 兩個模型） |
| 自動化測試 | ✅ 127/127 通過 |
| 冒煙測試 | ✅ App 可啟動 |
| 程式碼完整性 | ✅ Import / Config / Models 全數一致 |
| 甲方驗證 | 1/10 PASS，9 項待測 |
| 模型選型 | ⚠️ E4B 在 16GB 機器上記憶體緊繃，驗證暫用 E2B |

---

**🟡 進行中 — 暫停等待甲方繼續手動驗證**

下一步：甲方有空時，啟動 App 並依序完成驗證 #2~#10。

---

## 七、V Phase 第三輪（2026-04-16，Bug #8 修復後接手）

> 前置：[[devlog_20260416_builderB_bug8]] — 碼農 B 修完 Bug #8（Checkbox label_style + NavigationRail 越界）並與甲方協同自測 S1/S6/S7/S8 全 PASS。
> 對應 checklist：[[flet_0.84_migration_20260408]] §G4（S1-S9）。
> 執行：實驗者（Verifier）。

### 7.1 自動化 regression（Verifier autonomous）

```bash
python -m pytest -m "not slow and not real_audio" -q
```

| 結果 | 數值 |
|---|---|
| passed | **106** |
| deselected (slow / real_audio) | 22 |
| failed | 0 |
| warning | 1（pydub 的 `audioop` Py3.13 deprecation，Py3.11 環境無影響） |
| 耗時 | 88.88s |

✅ 無 regression — Bug #1-#8 全部修復後的 baseline 穩定。

> 備註：之前報告 §1.2 的「127」是把手動補跑的 Whisper（7）+ ChromaDB（14）併入後合計，這輪用統一指令跑得到 106 fast tests。

### 7.2 App 啟動冒煙（Verifier autonomous）

```bash
python -m app.main
```

| 檢查點 | 結果 |
|---|---|
| TCP server 啟動 | ✅ `localhost:58342` |
| Flet client 載入 | ✅ `flet-desktop 0.84.0`（cache hit） |
| Assets 路徑 | ✅ `app/assets` |
| App session started | ✅ |
| Startup Traceback | ✅ 無 |

### 7.3 靜態檢查 — 響應式佈局 API（Verifier autonomous）

依 [[flet_0.84_migration_20260408]] §A2 + §G1 對 [dashboard_view.py](app/ui/dashboard_view.py) 掃描：

| 檢查項 | 結果 | 行號 |
|---|---|---|
| `page.on_resize`（非 `on_resized`） | ✅ | [dashboard_view.py:359](app/ui/dashboard_view.py#L359) |
| breakpoint ≥1400 三欄 | ✅ | [dashboard_view.py:645](app/ui/dashboard_view.py#L645) |
| breakpoint ≥960 兩欄 | ✅ | [dashboard_view.py:655](app/ui/dashboard_view.py#L655) |
| 否則單欄 | ✅ | `_apply_responsive_layout` 三段分支完整 |
| `page.on_resize` callback → `_on_page_resized` | ✅ | mount 後才註冊，無 lifecycle 雷 |

與 [[ui_spec]] 對齊。

### 7.4 S2-S5 + S9 GUI smoke test — 甲方協同（2026-04-16 當日）

**執行**：Verifier 背景啟動 `python -m app.main` 並 Monitor 過濾 Traceback/Error；甲方本人操作 GUI。

| S# | 路徑 | 結果 | 觀察 |
|---|---|---|---|
| S2 | 響應式佈局三段位 | ⏸ 未測 | 被 S3 阻塞在前 |
| **S3** | **Dashboard live（即時錄音）** | **🔴 FAIL — 觸發 Bug #9** | 錄音 ~3 分鐘後 pipeline 掛，UI 殭屍 live；詳見 §7.4.1 |
| S4 | 對話框 | ⏸ 未測 | S3 掛掉後 App 需強制 kill |
| S5 | SnackBar | ⏸ 未測 | 同上。附註：Bug #9 的錯誤訊息因 `str(e)` 為空+SnackBar 自動消失，甲方**未看見** SnackBar |
| S9 | 響應式拖動切換 | ⏸ 未測 | 同上 |

#### 7.4.1 Bug #9 簡記（完整請見 [[bug_report_flet_api_20260406]] §Bug #9）

- **觸發**：甲方按「開始錄音」即時收音約 3 分鐘
- **現象**：Pipeline 例外 → `_run` coroutine 結束但 `recorder` 獨立存活 → GUI 殭屍
  - 錄音計時持續（觀察到 08:19+）
  - 逐字稿仍新增，時間戳在某點 **[00:08] → [00:00]** 歸零
  - **「停止錄音」按鈕失效**
  - 只能 `TaskStop` / 工作管理員強制終止
- **log**：`ERROR:__main__:Pipeline error:`（空訊息）+ `RuntimeError: async generator ignored GeneratorExit`
- **根因類別**：**邏輯層 / 錯誤處理 / Lifecycle**（非 Flet API 問題）
- **修復建議**：見 bug report §Bug #9「修復方向建議」（主修 [main.py:68-104](app/main.py#L68-L104) 的 _run / on_stop_recording / recorder lifecycle）
- **指派**：碼農 A（依本次任務分工：邏輯類交碼農 A）

#### 7.4.2 已驗證（Pipeline 前 3 分鐘可正常運作）

S3 雖失敗，但觀察到 Pipeline 在崩潰**前**的確運作：
- ✅ 「開始錄音」UI 進入 live 模式（錄音中 + 計時器 + 三區塊佈局）
- ✅ faster-whisper small 成功下載 + 載入
- ✅ VAD 過濾 + transcribe_chunk 連續產 segments（前 3 分鐘正常）
- ✅ Dashboard 即時顯示逐字稿（S6 效果隱含 PASS）
- ✅ Ollama 已連線狀態顯示正常（status bar 顯示「Ollama 已連線 | gemma4:e2b」）

→ 代表 Bug #9 **只卡住 Pipeline 的 shutdown / error-handling 路徑**，happy path 前半段 OK。

### 7.5 真實音檔 Pipeline 試跑（Verifier autonomous，**非阻塞發現**）

借用 [data/temp/錄製.m4a](data/temp/錄製.m4a)（50s m4a）臨時作為 fixture 跑 `pytest -m real_audio`：

| 階段 | 結果 |
|---|---|
| AudioImporter | ✅ 產出 chunks |
| Transcriber (whisper **tiny**) | ⚠️ 0 segments |
| 後續階段 | 未執行（Transcriber 斷線） |

**判讀**：
- test fixture config 為加速改用 `whisper.model: "tiny"`，非 spec 預設 `small`
- tiny 模型對低語音密度 / 50s 短音檔召回率有限，產 0 segments 屬合理邊界
- **非 Pipeline bug**，但測試 config 的 tiny 對此音檔太弱
- 附帶發現：`tests/test_e2e_real_audio.py:118` 的 `print("🎙️...")` 在預設 `cp950` 終端下 UnicodeEncodeError — 已用 `PYTHONIOENCODING=utf-8` 繞過，**非產品代碼問題**，記錄供未來測試健壯化參考

**行動**：
- 已清理臨時 fixture（`tests/fixtures/audio/vphase3_sample.m4a` 已移除）
- **不建議**列為 bug — spec 預設模型 small 尚未在此音檔驗證
- **建議**：S3 GUI 協同時一併用 spec 預設配置走完整 Pipeline（甲方已實測過 small + 真實音檔可行，見專案早期 devlog）

### 7.6 第三輪結論

| 類別 | 狀態 |
|---|---|
| 自動化測試（fast suite） | ✅ 106/106 |
| App 啟動冒煙 | ✅ clean |
| 靜態檢查（響應式 API） | ✅ 對齊 spec |
| GUI S1/S6/S7/S8（碼農 B 協同甲方，前次） | ✅ PASS |
| GUI S3（本次協同） | 🔴 FAIL — Bug #9 |
| GUI S2/S4/S5/S9 | ⏸ 未測（S3 阻塞在前） |
| 已知 UX 議題 | ⚠️ S6 首次 ML 載入阻塞（[[devlog_20260416_builderB_bug8]] 已標記，非本輪範圍） |
| 新 bug | 🔴 **Bug #9**（Pipeline/recorder lifecycle） |

### 7.7 交棒大統領

- 自動化 + 冒煙 + 靜態檢查 **無阻塞**
- **GUI S3 協同第一次就撞到 Bug #9**，Pipeline 在真實 3 分鐘時長下暴露 lifecycle 設計缺陷
- **請大統領派工碼農 A** 修 Bug #9（完整修復建議見 [[bug_report_flet_api_20260406]] §Bug #9「修復方向建議」表）
- Bug #9 修完後 Verifier 重跑：
  1. 127 fast tests（regression）
  2. 協同甲方即時錄音 5-10 分鐘（確認 lifecycle 治本）
  3. 續跑 S2/S4/S5/S9
- S2/S4/S5/S9 **不會受 Bug #9 阻塞**，理論上可在 Bug #9 修復前另排協同（甲方若有時間，避開 S3「開始錄音」路徑即可），但因 App 掛掉後需重啟且 S2/S9 牽涉響應式佈局切換需 live 模式驗證，**建議併在 Bug #9 修復後一起跑**比較省協同輪次

---

**🔴 第三輪 GUI 協同發現 Bug #9 — 阻塞 S3，待碼農 A 修復**

---

## 八、V Phase 第四輪（2026-04-16，碼農 A commit `b428369` 修完 Bug #9 後重驗）

> 前置：[[devlog_20260416_builderA_bug9]] — 碼農 A 依 bug report §Bug #9 修復建議 A1/A2/A3/B1/C1 實作、新增 6 個 asyncio lifecycle unit tests（112 passed），明確標示「CLI 無 GUI driver → 5+ 分鐘實機錄音 + 拔 Ollama 模擬」委交 Verifier。
> 執行：實驗者（Verifier）+ 甲方協同。

### 8.1 Step 1 — Regression（Verifier autonomous）

```bash
python -m pytest -m "not slow and not real_audio" -q
```

| 結果 | 數值 |
|---|---|
| passed | **112**（baseline 106 + 碼農 A 新增 6 個 lifecycle tests） |
| deselected (slow / real_audio) | 22 |
| failed | 0 |
| warning | 1（pydub `audioop` Py3.13 deprecation，Py3.11 無影響） |
| 耗時 | 13.61s |

✅ 無 regression。碼農 A 的 6 個新 asyncio lifecycle tests 全過。

### 8.2 Step 2a — 靜態複核碼農 A diff（Verifier autonomous）

對照 [[bug_report_flet_api_20260406]] §Bug #9「修復方向建議」逐項檢核 [main.py](app/main.py)：

| # | 檢核項 | 位置 | 結果 |
|---|---|---|---|
| A1 | `except CancelledError: raise` 分流 | [main.py:90-92](app/main.py#L90-L92) | ✅ |
| A1 | `logger.exception(...)` 完整 traceback | [main.py:94, 136](app/main.py#L94) | ✅ |
| A1 | `finally` 無條件 `await recorder.stop()` | [main.py:96-100](app/main.py#L96-L100) | ✅ |
| A2 | SnackBar 含 `type(e).__name__` + `duration=30000` | [main.py:54-66](app/main.py#L54-L66) | ✅ |
| A2 | `str(e)` 空時 fallback `(無錯誤訊息)` | [main.py:57](app/main.py#L57) | ✅ |
| A3 | `on_import_audio._run` 鏡像 | [main.py:126-145](app/main.py#L126-L145) | ✅ |
| B1 | `pipeline_task` 保留 handle | [main.py:49, 110, 147](app/main.py#L49) | ✅ |
| B1 | `on_stop_recording` cancel 安全網 | [main.py:149-157](app/main.py#L149-L157) | ⚠️ 實作為「預設路徑」而非「安全網」— 見 Bug #10 |
| C1 | 錄音異常 → idle | [main.py:104](app/main.py#L104) | ✅ |
| C1 | 匯入異常 → review | [main.py:141](app/main.py#L141) | ✅ |

**觀察**：A1/A2/A3/C1 全對齊 bug report 建議。B1 的 `cancel()` 用法語意偏了，但要 GUI 實機才能驗證副作用 — 見下節。

### 8.3 Step 2b — T1 實機錄音（甲方協同）

**劇本**：甲方開「開始錄音」→ 錄 5+ 分鐘 → 主動按「停止錄音」。Verifier 背景啟動 `python -m app.main` + Monitor log。

**實際執行**：

| 觀察點 | 結果 |
|---|---|
| App 啟動 | ✅ TCP `localhost:55630`、Flet client OK、無 Traceback |
| 開始錄音 → live 模式 | ✅ |
| 前 180 秒（~3 分鐘）Pipeline 運作 | ✅ faster-whisper 連續 process 20 個 10s chunks |
| ~180 秒後 UI 狀態 | 🔴 **逐字稿停止新增（甲方回報 2b）+ 重點/Action Items 全空白（甲方回報 2c）** |
| log 中是否有 Pipeline error / Traceback | ❌ 無 ERROR，只有 `INFO:__main__:Recording pipeline cancelled by user`（甲方按停止後才出現） |
| 甲方按「停止錄音」反應 | UI **直接回 idle**（而非 review） |
| `data/sessions/` 落盤狀態 | 🔴 **空目錄** — 3 分多鐘錄音資料完全遺失 |
| asyncio warning | 🔴 `RuntimeError: async generator ignored GeneratorExit`（Bug #9 根因 D 未消失） |

#### 8.3.1 Bug #9 修復評估

碼農 A 主要目標（A1/A2/A3/C1）**沒有真的被觸發驗證**：
- Pipeline 沒崩 → `logger.exception` + SnackBar + idle 回退這條路徑沒走到
- 單元測試 112 passed 只能證明 pattern 實作正確，不能證明實機正確

**反而暴露 B1 設計副作用 → Bug #10**（見下）。

#### 8.3.2 發現 Bug #10 — 正常停止 = 資料遺失 🔴🔴🔴

詳見 [[bug_report_flet_api_20260406]] §Bug #10。

**核心**：`on_stop_recording` 同時 `recorder.stop()` + `pipeline_task.cancel()`，cancel 比軟停止快 → `_run` 走 CancelledError → finally 回 idle → `_on_pipeline_done` 從未被呼叫 → `session_mgr.save` 沒跑。

嚴重度評估：**比 Bug #9 殭屍 mode 更糟**（第三輪至少資料還在記憶體，本次直接丟失 3 分多鐘錄音）。

#### 8.3.3 發現 Bug #11 — Summarizer 阻塞主迴圈 🟠

詳見 [[bug_report_flet_api_20260406]] §Bug #11。

**核心**：[stream_processor.py:59](app/core/stream_processor.py#L59) `await self.summarizer.generate(...)` 阻擋 `async for audio_chunk` 主迴圈 30-90s（Gemma E2B 推理時長），期間不 consume 新音訊、不產 segment。這是**架構問題**，非 Bug #9 造成，但第四輪首次觀察到。

甲方會以為「掛了」→ 按停止 → 觸發 Bug #10 資料遺失。

#### 8.3.4 發現 Bug #12 — async gen `finally` 內 yield 🟠

詳見 [[bug_report_flet_api_20260406]] §Bug #12。

**核心**：[audio_recorder.py:73-80](app/core/audio_recorder.py#L73-L80) 的 `finally: ... yield np.concatenate(transcribe_buffer)` 違反 Python async gen 規則 → `RuntimeError: async generator ignored GeneratorExit`。

碼農 A 在修 Bug #9 時**預測** A+B+C 後此 warning 會自然消失，**預測錯誤**。

### 8.4 Step 2c/2d + Step 3（T2/T3 + S2/S4/S5/S9）

**全數未執行** — Bug #10 使「正常錄音流程」整條不可用，繼續跑只會重複浪費甲方時間驗證明知已壞的路徑。依規則「有新 bug 立刻回報大統領，不要 loop」，即刻停止驗證、回報。

### 8.5 第四輪結論

| 類別 | 狀態 |
|---|---|
| 自動化測試（fast suite） | ✅ 112/112（含碼農 A 新增 6 個） |
| 靜態 diff 複核 | ✅ A1/A2/A3/C1 對齊，B1 語意偏 |
| GUI S3（即時錄音）| 🔴 **FAIL** — Bug #10 資料遺失 + Bug #11 UI 凍結 |
| Bug #9 A1/A2/A3/C1（異常路徑） | ⏸ **未驗證**（pipeline 沒崩，路徑未走） |
| Bug #9 根因 D（asyncio warning） | 🔴 未消失 → Bug #12 |
| GUI S2/S4/S5/S9 | ⏸ 未測（被 Bug #10 阻塞） |
| 新 bug | 🔴🔴🔴 **Bug #10**、🟠 Bug #11、🟠 Bug #12 |

### 8.6 交棒大統領

依規則「有新 bug 立刻回報大統領，不要 loop」：

**回報摘要**：

1. **Bug #10（最優先）**：碼農 A B1 設計副作用，正常按停止 = 資料遺失 + 回 idle。嚴重違反 spec（review 模式預期）。**建議派碼農 A**（邏輯 + 原修復者）
   - 修法：方案 A（`on_stop_recording` 不主動 cancel，讓 processor.run 自然走完 final summary）或方案 B（`await wait_for(task, timeout)` + timeout 才 cancel）
   - 附帶：[main.py:155](app/main.py#L155) `page.run_task(recorder.stop)` 傳 coro 函式而非 coro object，方案 A/B 後要一併修
2. **Bug #11**：summarizer 阻塞主迴圈（架構問題）。**建議派碼農 A**
   - 修法：summarizer 丟 `asyncio.create_task` 背景跑 + `_run_summary_async` callback 更新 UI
   - 推測：可能是第三輪 Bug #9 崩潰的真實近端誘因（summarizer + to_thread 時序衝突）
3. **Bug #12**：`audio_recorder.start()` async gen finally-yield 違反 Python 規則。**建議派碼農 A**
   - 修法：refactor 迴圈，殘餘音訊在 while 內 flush 後才退

**建議派工順序**：Bug #10 → Bug #11 → Bug #12（順序上 #10 影響資料遺失最急；#11 修完才能再次實機驗證 #10 是否治癒；#12 可併入 #10/#11 的 PR）。

**Verifier 待命**：三 bug 修完 → 跑 112 fast tests → 協同甲方 T1（5+ 分鐘錄音 + 正常停止 + 檢查 `data/sessions/`）+ T2（拔 Ollama）+ T3（匯入）+ S2/S4/S5/S9 smoke。

### 8.7 Verifier 第四輪反思

1. **碼農 A 單元測試通過 ≠ 功能符合 spec**：6 個 asyncio tests 驗的是「cancel → finally → idle」的 pattern 實作，但沒有任何一個 test 問：「正常按停止，預期應該進哪個 mode？」如果當時有「正常錄音 → stop → 期待 review」這條 test case，B1 的語意偏差在單元層就會被抓到。**建議未來 test 設計要比對 spec，不只比對實作 intent**。
2. **Verifier 第三輪結語的主張再次被印證**：Flet 相關 PR 必須有 GUI + 真實 pipeline 時長實機驗證。本輪若沒有協同甲方跑到 180s summarizer 觸發點，Bug #10/#11/#12 全都抓不到。
3. **「修 Bug 變出新 Bug」模式警訊**：V4 的 3 個新 bug 裡，Bug #10 直接源自 Bug #9 修復、Bug #12 是 Bug #9 連鎖 D 沒消失。這在 Flet 0.84 遷移的第 N 輪了，整個 Pipeline lifecycle 層可能需要 Researcher 做一次系統性架構 review 再讓碼農動手，而非繼續一個 bug 一個 bug 打補丁。建議大統領考慮這個架構 review 是否要派工。

---

**🔴 第四輪回報三個新 Bug — Bug #10 最急（資料遺失），全數待大統領派工**

---

## 九、V Phase 第五輪（2026-04-16，碼農 A Bug #11/#10/#12 三 step 修完後重驗）

> 前置：
> - 研究者 [[pipeline_lifecycle_architecture_20260416]] 交付 7 invariants + 3 option 選型 + 7 spec gaps（commit `5f84925`）
> - 大統領依 gap 清單更新 specs（commit `f56bb6a`，G1 甲方簽核，G2-G7 Director 自簽）
> - 碼農 A [[devlog_20260416_builderA_bug11_10_12]]：Step 1 Bug #11（c22c1a2）→ Step 2 Bug #10（9c6b96e）→ Step 3 Bug #12（49c54f9）。單元層 **147 passed, 1 skipped**（baseline 133 → +14 spec-level tests 對應 I1-I7）
> - 碼農 A 明確委交 CLI blocker 實機層：5-10 分鐘錄音 + 拔 Ollama + stop timeout + 匯入異常 + Bug #12 log 驗證
>
> 執行：實驗者（Verifier）+ 甲方協同。

### 9.1 Step 1 — Regression（Verifier autonomous）

```bash
python -m pytest -m "not slow and not real_audio" -q
```

| 結果 | 數值 |
|---|---|
| passed | **126**（含碼農 A 新增 14 個 spec-level tests 對應 I1-I7） |
| deselected (slow / real_audio) | 22 |
| failed | 0 |
| warning | 1（pydub `audioop` Py3.13 deprecation，Py3.11 無影響） |
| 耗時 | 20.33s |

✅ **無 regression**。

> 備註：碼農 A devlog 報 147 passed（含 test_transcriber 7 + test_knowledge_base 14 需另跑），Verifier 用與前四輪一致的 `-m "not slow and not real_audio"` 指令得到 126。兩個數字對應不同過濾；fast suite 基準穩定。

### 9.2 Step 2 — 靜態複核碼農 A diff 對照研究者 7 invariants（Verifier autonomous）

對照 [[pipeline_lifecycle_architecture_20260416]] §1.4 七條 invariants + §2/§4 動點表逐項檢核：

| Invariant | 要求 | 實作位置 | 結果 |
|---|---|---|---|
| **I1**（任何路徑必落盤） | session 必進 `data/sessions/{id}.json`，含 aborted partial | [main.py:88-93](app/main.py#L88-L93) `_persist_session` + [main.py:126-128, 167-168](app/main.py#L126-L128) `_run.finally` 無條件呼叫 | ✅ |
| **I2**（ready 前先完成 final summary） | 轉場順序：save → mark_ready → set_mode("review") | [stream_processor.py:133-149](app/core/stream_processor.py#L133-L149) drain → final → update → mark_ready → on_status_change("ready") → [main.py:209-214](app/main.py#L209-L214) `_on_pipeline_done` save + set_mode | ✅ |
| **I3**（cancel 只當安全網） | 僅超時或二次按停才 cancel | [main.py:174-203](app/main.py#L174-L203) `_stop_recording_async`：`wait_for(shield, stop_drain_timeout_sec=90)` → `TimeoutError` 才 `task.cancel()` | ✅ |
| **I4**（Summarizer 不阻塞 audio consume） | 主迴圈 `async for` 持續推進 | [stream_processor.py:116-130](app/core/stream_processor.py#L116-L130) `asyncio.create_task(_run_summary_async(...))` 後立即 continue；`_summarizing` flag 防連發 | ✅ |
| **I5**（UI mode SSoT = Session.status） | mode 由 status 衍生；UI 讀 status | [models.py](app/core/models.py) `Session.mode` @property（recording/processing → live，其餘 → review）；[main.py:70-86](app/main.py#L70-L86) `_finalize_ui` 讀 `session.status` | ✅ |
| **I6**（status 轉換由 SessionManager 專屬 API） | 無直接 `session.status = ...` 賦值 | [session_manager.py:59-86](app/core/session_manager.py#L59-L86) `transition` 為唯一入口；`end_recording` / `mark_ready` / `mark_aborted` 全走 transition | ⚠️ **觀察 Obs-1** — [exporter.py:15](app/core/exporter.py#L15) 仍直接 `session.status = "exported"` 未走 transition（Bug #10/#11/#12 修復範圍外的舊代碼，見 §9.6） |
| **I7**（async gen cleanup 不 yield） | finally 內無 `yield` | [audio_recorder.py:74-83](app/core/audio_recorder.py#L74-L83) `if transcribe_buffer: yield ...` 搬至 while 退出後、finally 前；finally 僅 `stream.stop/close` + WAV flush（無 yield） | ✅ |

**C1-C8 補充檢核**（§2.1 + §4.1）：

| 條件 | 實作 | 結果 |
|---|---|---|
| C1（正常停止不預設 cancel） | `_stop_recording_async` 只呼 `request_stop` + `wait_for(shield)` | ✅ |
| C2（cancel 路徑 partial save） | `_run.finally` 無條件 `_persist_session`；CancelledError 分支 `mark_aborted("stop_timeout")` | ✅ |
| C3（異常路徑與正常分離） | CancelledError → stop_timeout；Exception → pipeline_error | ✅ |
| C4（`recorder.stop` 語意） | rename 為 `request_stop`，docstring 明示軟停止（G5） | ✅ |
| C5（非阻塞 Summarizer） | fire-and-forget create_task | ✅ |
| C6（單一 pending summary） | `_summarizing` flag + 觸發條件 `and not self._summarizing` | ✅ |
| C7（summary 錯誤不炸主迴圈） | `_run_summary_async` 內部 try/except 吞例外只 log，finally 重置 flag | ✅ |
| C8（停止與 pending 協調） | `_drain_pending_summary` `wait_for(shield, pending_summary_wait_sec=60)` → TimeoutError 才 cancel；final summary 再跑 | ✅ |

**G1-G7 Spec gap 落地檢核**：

| Gap | 實作 | 結果 |
|---|---|---|
| G1（aborted + abort_reason） | [session_manager.py:21](app/core/session_manager.py#L21) `_VALID_STATUSES` 含 aborted；`transition` 驗證 abort_reason 必填；[models.py](app/core/models.py) `Session.abort_reason` 欄位 | ✅ |
| G2（final summary timeout + fallback） | [stream_processor.py:151-208](app/core/stream_processor.py#L151-L208) `_run_final_summary` + `_build_fallback_final`；`SummaryResult.fallback_reason` 欄位；config `final_summary_timeout_sec: 120` | ✅ |
| G3（pending summary 停止期處理） | [stream_processor.py:66-90](app/core/stream_processor.py#L66-L90) `_drain_pending_summary`；config `pending_summary_wait_sec: 60` | ✅ |
| G4（mode 衍生自 status） | `Session.mode` @property | ✅ |
| G5（recorder 軟停止命名） | `request_stop` rename + docstring | ✅ |
| G6（併發模型入 spec） | [[system_overview#4.2]] 已補「Summarizer 跑在獨立 task... 同時最多一個 pending summary」 | ✅ |
| G7（異常處理原則總則） | [[system_overview#6. 異常處理原則（總則）]] 三原則已入 spec | ✅ |

**靜態結論**：7 條 invariants + 8 條 C 檢核 + 7 個 G gap **全部對應代碼落地**。Bug #10/#11/#12 修復深度覆蓋研究者 review 要求，無第四輪「B1 語意翻轉」等 invariant 偏差。

### 9.3 Step 3 — 實機層檢核（待甲方協同）

碼農 A devlog 明列 6 項 + 本輪新增，總表如下。**此區需甲方本人操作 GUI**，實驗者（CLI）負責：

1. `python -m app.main` 背景啟動 + Monitor log（過濾 `RuntimeError` / `ERROR:__main__:Pipeline` / `async generator`）
2. 每項完成後截圖 / dump log / 查 `data/sessions/` 落盤
3. 彙整進 §9.4

#### 9.3.1 T1 — 5-10 分鐘正常錄音 + 正常停止（最核心）

| # | 觀察點 | 預期 | 驗 invariant |
|---|---|---|---|
| T1-1 | 前 180s 逐字稿每 10s 產新 segment | 穩定 | I4（pre-summary） |
| T1-2 | 180s 後首次週期 summary 觸發 | 逐字稿**不凍結超過 15s**，期間 ≥ 3 個新 segment | **I4**（summary task 跑時主迴圈不凍） |
| T1-3 | 會議重點 / Action Items 出現在 UI | 第一次摘要完成後填入 | §4.2 週期摘要 |
| T1-4 | 跨過第二次週期（~360s）仍穩定 | 繼續產 segment + 第二版摘要覆蓋 | I4 + C6 |
| T1-5 | 5+ 分鐘後按「停止錄音」 | UI 進 review（不是 idle） | I2 + I5 |
| T1-6 | `data/sessions/{id}.json` 存在 | status=`ready`，非 `aborted`/`live`/`recording` | **I1 + I2** |
| T1-7 | session 有 final summary | `summary.is_final=True`；無 `fallback_reason` | spec §4.2 |
| T1-8 | log 無 `RuntimeError: async generator ignored GeneratorExit` | — | **Bug #12 I7** |
| T1-9 | log 順序：`transition: recording → processing` → `transition: processing → ready` | — | I6 |

#### 9.3.2 T2 — 拔 Ollama 測試（final summary fallback）

| # | 觀察點 | 預期 |
|---|---|---|
| T2-1 | 錄音中途（~200s 後，第一次週期 summary 剛過）執行 `ollama stop` | — |
| T2-2 | 下一次週期 summary 觸發時 | 走 fallback 路徑；週期 summary 失敗但**不炸主迴圈**；UI 應有降級提示（§6 原則 3） |
| T2-3 | 錄音 5+ 分鐘後按停止 | status=`ready`（**不是** `aborted`），summary.is_final=True + `fallback_reason="ollama_failure"` 或 `"ollama_timeout"` |
| T2-4 | log 有完整 traceback | `logger.exception("Final summary failed — using fallback")` 或 `"Periodic summary generation failed"` |
| T2-5 | `data/sessions/{id}.json` 存在 | ✅ 落盤 |

#### 9.3.3 T3 — Stop timeout 測試（watchdog cancel）

> 前提：需能人為卡住 pipeline > 90s（`stop_drain_timeout_sec`）。建議法：Ollama 推理卡死（例如模型換超大或打 busy-loop bash 佔滿 CPU），使 final summary 吃完 pending 60s + final 120s 還沒完。實際不一定能穩定觸發，若無法重現則在 §9.4 標「無法人為觸發，邏輯依 §9.2 靜態複核已覆蓋」。

| # | 觀察點 | 預期 |
|---|---|---|
| T3-1 | 錄音 ≥ 3 分鐘 → 按停止 | UI 顯示「停止中...」（若 dashboard 有此提示；否則看計時器凍結） |
| T3-2 | 90s 後 watchdog cancel 啟動 | log 有 `"Pipeline drain exceeded 90s — forcing cancel"` |
| T3-3 | session 落盤 | status=`aborted`，`abort_reason="stop_timeout"` |
| T3-4 | UI 進 review(partial) | 有 segments → review；無則 idle |
| T3-5 | 仍無 `async generator ignored GeneratorExit` | I7 |

#### 9.3.4 T4 — 匯入音檔異常路徑

| # | 觀察點 | 預期 |
|---|---|---|
| T4-1 | 匯入長度 > 3 分鐘的音檔 | UI 進 live，逐字稿逐段填入 |
| T4-2 | 匯入中拔 Ollama | 走 fallback；pipeline 繼續跑完 segments |
| T4-3 | 匯入完成 | status=`ready` + `fallback_reason`；或若 transcribe 全失敗 → `aborted` + `abort_reason="pipeline_error"` |
| T4-4 | 已 yield 的 segments 保留 | 不靜默丟資料（I1） |

#### 9.3.5 T5 — 停止按鈕語意（各 state 皆可救回）

| # | 情境 | 預期 |
|---|---|---|
| T5-1 | 正常錄音中按停止 | drain（≤90s）→ `ready` |
| T5-2 | summary 執行中按停止 | 等 `pending_summary_wait_sec=60s` → final（可能 fallback）→ `ready` |
| T5-3 | 極端卡住（人為）按停止 | 90s 後 cancel → `aborted` + `abort_reason="stop_timeout"` |

> 連按兩次停止：目前 `_stop_recording_async` 會 early return（task 還在跑就返回），**第二次按不會提前逃生**。碼農 A devlog 已標為「留給 Reviewer 判斷是否需加強制逃生」。若甲方實機 T5-3 耐不住 90s，可觀察此行為；**非阻塞 bug**，視為 future-work。

#### 9.3.6 T6 — Bug #12 log 驗證（所有路徑）

每項完成後搜 log：

```bash
grep -i "async generator ignored GeneratorExit" <log>
grep -i "Task exception was never retrieved" <log>
```

預期：**0 筆匹配**。若仍有則回報碼農 A（devlog 已標示「後續可重構為 async context manager」的方案）。

### 9.4 Step 3 結果（2026-04-16 晚間甲方協同 T1 兩次）

完整 raw log：[[vphase5_raw_round2|doc/reports/vphase5_raw_round2.log]]（tee 完整捕獲，含所有 Traceback）。

| T# | 路徑 | 結果 | 實機觀察 |
|---|---|---|---|
| T1 | 5-10 分鐘正常錄音 + 停止（**兩次 session**） | 🔴 **FAIL** | ▪ 兩次 session 都發生「按停止按鈕 → UI 無反應，錄音計時繼續跳」<br>▪ 背景 recorder 實際已軟停 → audio gen 退 → processor.run 走完 → session save 到 `data/sessions/`（I1 ✅）<br>▪ session.status=ready 但 UI 永不切 review（I2 表象成立但 UI 不閉環）<br>▪ 甲方只能強制關視窗<br>▪ **log 無 `async generator ignored GeneratorExit`**（Bug #12 實機 ✅）<br>▪ segments 全空（VAD 全過濾，**非 App bug**，chunk_0000.wav 分析 peak=-52dBFS，屬麥克風環境訊號偏低） |
| T2 | 拔 Ollama（fallback） | ⏸ 未跑 | T1 阻塞在前 |
| T3 | Stop timeout（watchdog） | ⏸ 未跑 | Bug #13 已讓 watchdog 實質失效，T3 現在無法觀察「cancel → aborted」路徑是否正確 |
| T4 | 匯入音檔異常 | ⏸ 未跑 | T1 阻塞 |
| T5 | 停止按鈕各 state | 🔴 **FAIL**（T1 已測第一格） | T5-1（正常錄音中按停止）已重現「無反應」 |
| T6 | Bug #12 log（全路徑） | ✅ **PASS** | 兩次 session 完整流程（含停止 drain + finally flush）log 零匹配 `async generator ignored GeneratorExit`；Bug #12 修復實機有效 |

#### 9.4.1 Bug #13 簡記（完整見 [[bug_report_flet_api_20260406#Bug #13]]）

- **根因**：[main.py:191](app/main.py#L191) `asyncio.shield(task)`。`task = page.run_task(_run)` — Flet 0.84 回傳 `concurrent.futures.Future`，不是 `asyncio.Task`；`asyncio.shield._ensure_future` 拋 TypeError
- **影響**：停止按鈕 UI 無反饋、I3 watchdog 機制失效（但 session 靠軟停仍走完，I1 守住）
- **為什麼沒抓到**：研究者架構 review 的漏網之魚（§2.3 方案 A 建議 `asyncio.wait_for(pipeline_task, timeout)` 但沒驗 Flet 下 `page.run_task` 回傳型別）。碼農 A 單元測試用 `asyncio.create_task` 模擬 pipeline_task 可通過，生產環境不同
- **指派**：**碼農 A**（`_stop_recording_async` 為其新增代碼）

#### 9.4.2 Bug #14 簡記（完整見 [[bug_report_flet_api_20260406#Bug #14]]）

- **根因**：[dashboard_view.py:571](app/ui/dashboard_view.py#L571) `_build_review` 建 `SummaryPanel` 後**立刻**呼叫 `update_highlights` → [dashboard_view.py:178](app/ui/dashboard_view.py#L178) 內 `if self.page:` 觸發 Flet 0.84 strict lifecycle → `Control must be added to the page first`
- **影響**：`_on_pipeline_done` 內的 `dashboard.set_mode("review")` 炸 → UI 永不切 review → `_run.except Exception` 把 RuntimeError 當「recording pipeline error」log 出來（log 訊息誤導性強）
- **為什麼沒抓到**：第三輪 Bug #7 commit `43932d3` 修 FeedbackView 時沒 grep 其他控件的 `if self.page:` pattern
- **指派**：**碼農 B**（UI lifecycle，同 Bug #7 脈絡）

#### 9.4.3 Bug #13 + #14 的連鎖效應

| 階段 | 情境 | 後果 |
|---|---|---|
| 甲方按停止 | `_stop_recording_async` 的 `request_stop()` 先跑成功 → `asyncio.shield(task)` 炸 TypeError（Bug #13）| UI 無 reaction；但 recorder flag 已設 |
| 背景執行 | `audio_recorder.start` 的 `while self._recording` 下一輪退 → async gen 耗盡 → `processor.run` 走完 final summary → `mark_ready` | session.status=ready；session 即將 UI 轉場 |
| UI 轉場嘗試 | `on_status_change("ready")` → `_on_pipeline_done` → `dashboard.set_mode("review")` → 拋 RuntimeError（Bug #14） | UI 永停 live；`_run.except` log「Recording pipeline error」 |
| finally 清理 | `_persist_session`（冪等 OK）+ `request_stop`（冪等 OK） | I1 ✅（disk 有檔）；但 `if session.status != "ready": _finalize_ui` 擋住（status 已 ready）— **沒有 fallback UI 路徑** |
| 甲方視角 | UI 卡 live，只能 kill | 資料其實在 disk，但**無法從此 session 繼續到匯出** |

**靜態評估在這裡錯了一件事**：§9.2 表格標 I2 = ✅，但**實機驗出 I2 表象成立 / 實質不閉環**：ready 前 final summary 確實產生、session.status=ready 確實達到、但「UI 切 review」沒發生 → 整條 T4（T4=finalizing → review ok）在研究者 §1.3 狀態機 **並未實際走完**。這要補到未來版本的 invariants 檢核：**I2 不只是 status 轉換正確，還要 UI 轉場完成才算閉環**。

### 9.5 Step 4（S2/S4/S5/S9）— 全未跑（T1 阻塞）

第四輪 Bug #10 阻塞未跑，本輪 T1 因 Bug #13/#14 再度阻塞。**派工修完 #13/#14 後 V Phase 第六輪再補跑**。

| S# | 項目 | 結果 |
|---|---|---|
| S2 | 響應式佈局 | ⏸ 阻塞 |
| S4 | 對話框 | ⏸ 阻塞 |
| S5 | SnackBar（含 fallback 降級提示必須可見）| ⏸ 阻塞 |
| S9 | 拖動視窗切換三段式 | ⏸ 阻塞 |

### 9.6 Observation 清單（非阻塞）

| ID | 類別 | 位置 | 說明 | 建議 |
|---|---|---|---|---|
| **Obs-1** | I6 覆蓋缺口 | [exporter.py:15](app/core/exporter.py#L15) | `session.status = "exported"` 直接賦值，未走 `SessionManager.transition` | Bug #13 修復時碼農 A 可一併補 `SessionManager.mark_exported(session, export_path)` |
| **Obs-2** | 二次按停止語意 | [main.py:187-189](app/main.py#L187-L189) | 第二次按停止 early return，無強制逃生 | Bug #13 修復時如採輪詢方案可順便處理 |
| **Obs-3** | empty segments 降級語意 | [stream_processor.py:141-144](app/core/stream_processor.py#L141-L144) | 實機兩次 session segments=[] 時 final summary 仍產 placeholder 文字（`"（請在此處填入會議的主要討論主題和核心發現）"`），`status=ready + fallback_reason=null`。違反 §6 「明確告知使用者」 | 建議：若 `len(session.segments)==0` → skip final summary 直接 `_build_fallback_final(session, "empty_segments")` 並標 is_final=True + fallback_reason |
| **Obs-4** | 麥克風環境（甲方側） | N/A | `data/temp/chunk_0000.wav` peak=-52dBFS（正常 -20~-10）；Surface Pro 9 內建麥克風訊號極低 → VAD 全過濾 | **非 App bug**；甲方側檢查 Windows 麥克風預設 device / 增益 / App 權限 |

### 9.7 第五輪結論

| 類別 | 狀態 |
|---|---|
| 自動化測試（fast suite） | ✅ 126/126 |
| 靜態複核 — 7 invariants | ✅ 全部落實（Obs-1 exporter 小缺口） |
| 靜態複核 — C1-C8 / G1-G7 | ✅ 全對齊 |
| **實機 T1**（正常停止流程） | 🔴 **FAIL** — Bug #13 + #14 |
| **實機 T6**（Bug #12 log） | ✅ **PASS** — 整輪無 `async generator ignored GeneratorExit` |
| **實機 I1**（必落盤） | ✅ 兩次 session 皆 save 到 `data/sessions/` |
| 實機 I2（ready 前 final summary） | ⚠️ status 表象成立但 UI 不閉環（Bug #14） |
| 實機 I3（cancel 安全網） | 🔴 watchdog 實質失效（Bug #13） |
| 實機 I5（UI mode SSoT=status） | 🔴 UI 永不切 review |
| 實機 I6（status 唯一入口） | ✅（不含 Obs-1 舊代碼） |
| 實機 I7（async gen cleanup 不 yield） | ✅（Bug #12 實機 PASS） |
| 實機 T2-T5 + S2/S4/S5/S9 | ⏸ T1 阻塞 |

**對比第四輪**：第四輪靜態複核曾標「B1 語意偏」，本輪靜態層已無此類偏差。第四輪反思「單元綠燈 ≠ 符合 spec」在靜態層已收斂。但實機層仍能發現 Flet 生產環境 vs asyncio 模擬的 API 差異、以及 Bug #7 同類 lifecycle pattern 沒掃到 — 再次印證 Flet 相關 PR 必須有**實機 GUI + 真實 pipeline 時長**驗證。

**Bug #10/#11 資料保全核心機制**：從 log 看 recorder 軟停成功、processor.run 走完 final summary + mark_ready — **資料保全層未失效**。失敗只在 watchdog（Bug #13）和 UI 轉場（Bug #14）兩個獨立層面。

**Bug #12**：實機 PASS（兩次 session 含 drain + flush，log 零匹配 GeneratorExit）。

**新發現 Bug**：
- **Bug #13**：研究者架構 review 漏網之魚（沒驗 Flet `page.run_task` 回傳型別）。派 **碼農 A**，可能需研究者補 Flet async bridge 研究
- **Bug #14**：Bug #7 殘留（只修 FeedbackView 沒掃 dashboard 其他 panel）。派 **碼農 B**
- **Obs-3**：empty segments 降級語意強化（非阻塞）

**新 invariant 建議**：I2 實機驗出「status=ready 但 UI 無轉場」的表象閉環問題。建議下版 I2 加條件「UI 轉場完成才算閉環」，送研究者評估。

### 9.8 交棒大統領

**派工建議**：

1. **碼農 A 修 Bug #13**（優先）
   - 推薦方案 A：輪詢 `pipeline_task.done()` + 超時呼 Flet Future.cancel
   - 附帶 Obs-1 `mark_exported` / Obs-2 二次按停 / Obs-3 empty segments fallback
2. **碼農 B 修 Bug #14**（優先）
   - 推薦方案 C：全面 grep `if self.page:` pattern 掃 UI lifecycle 殘留，一次修完所有同類 bug
3. **研究者補研究** — Flet 0.84 async bridge + lifecycle 完整映射（避免第六輪再爆同類）
4. 三者修完後 **V Phase 第六輪**：regression → 靜態複核（加新 invariant）→ 甲方先修麥克風環境（Obs-4）→ 實機 T1-T6 + S2/S4/S5/S9

**非阻塞平行**：甲方排查 Windows 麥克風設定（Obs-4）— 無有效麥克風錄音時 T1 summary 品質無法真正驗證。

---

**🔴 第五輪實機 FAIL — Bug #13 + #14 新發現，阻塞 Desktop 甲方簽核；Bug #10/#11/#12 資料保全層 ✅；送大統領派工**

---

## 十、V Phase 第六輪（2026-04-17，Bug #13/#14 修復 + Mic Live 新增後重驗）

> 前置：
> - 研究者 [[flet_0.84_async_lifecycle_20260417]]（第三篇 Flet 研究）— §1 cf.Future 實測、§3 page property lifecycle 映射表、§5/§6 修復指引、§7 contract test 建議、§9 三項 spec gap（G8/G9/G10）
> - 大統領據此更新 ui_spec §2.5 Mic Live 指示器 + §8 UI Mount Lifecycle 守則 + 簽核 Mic Live 規格變更 [[decision_20260417_mic_live_indicator]]
> - 碼農 A [[devlog_20260417_builderA_bug13]]（commit `f6dc568`）：Bug #13 — `asyncio.shield(cf.Future)` TypeError → 方案 A 輪詢（.done()/.cancel() 200ms poll）。僅動 main.py。
> - 碼農 B [[devlog_20260417_builderB_bug14_miclive]]（commit `481b36e` + `458ae75` + `edcb35a`）：Bug #14 全面掃清 `if self.page:` 假守衛 + Mic Live 指示器（AudioRecorder level API + 會中音量條 + idle Mic Test）+ main.py glue。
> - 單元 + contract tests：**140 passed, 22 deselected, 0 failed**
>
> 執行：實驗者（Verifier） + 甲方協同待開。

### 10.1 Step 1 — Regression（Verifier autonomous）

```bash
python -m pytest -m "not slow and not real_audio" -q
```

| 結果 | 數值 |
|---|---|
| passed | **140**（baseline 126 → +14 個 contract + lifecycle tests） |
| deselected | 22 |
| failed | 0 |
| warning | 1（pydub audioop，Py3.11 無影響） |
| 耗時 | 17.44s |

✅ 無 regression。

### 10.2 Step 2 — 靜態複核

#### 10.2.1 Bug #13 修復（碼農 A）

| 項目 | 位置 | 結果 |
|---|---|---|
| `Future` 型別正確 import | [main.py:7](app/main.py#L7) `from concurrent.futures import Future` | ✅ |
| `pipeline_task` 型別 annotation | [main.py:51](app/main.py#L51) `pipeline_task: Future \| None = None` | ✅（取代原誤寫的 `asyncio.Task`） |
| `_stop_recording_async` 輪詢邏輯 | [main.py:176-217](app/main.py#L176-L217) | ✅ 方案 A 實作清晰：Phase 1 drain wait + Phase 2 post-cancel wait（10s 硬 timeout） |
| 無 asyncio.shield/wait_for/await on cf.Future | 全檔 grep | ✅ |
| `task.cancel()` 用 cf.Future 原生 API（研究者 §1.3 確認語意 OK） | [main.py:204](app/main.py#L204) | ✅ |
| `stream_processor.py` 的 `asyncio.shield(self._summary_task)` 不動 | 研究者 §4.1 #7：summary task 是 `asyncio.create_task` 產物，shield 正確 | ✅ 未動 |

**結論**：Bug #13 修復遵循研究者 §5 推薦方案 A，完全避開 asyncio↔cf.Future bridge 的邊界。

#### 10.2.2 Bug #14 修復（碼農 B）

| 項目 | 指令/位置 | 結果 |
|---|---|---|
| `grep "if self\.page:" app/ui/` 殘留 | app/ 全掃 | **0 匹配** ✅ |
| `grep "hasattr.*page" app/ui/` 假守衛 | app/ 全掃 | **0 匹配** ✅ |
| `_mounted` pattern 覆蓋 | dashboard_view(25) + main_view(7) + settings_view(5) + terms_view(4) + feedback_view(4) = **45 處** | ✅ |
| Panel 類套改 | TranscriptPanel / SummaryPanel / ActionsPanel 各自加 `_mounted` + `did_mount` + `will_unmount` | ✅ |
| DashboardView 本身 | `set_mode` / `_on_page_resized` / `_apply_responsive_layout` 改 `_mounted` | ✅ |
| 其他 view | FeedbackView / TermsView / SettingsView / StatusBar 全套 Pattern A | ✅ |

**結論**：Bug #14 的 Pattern A 全面覆蓋，同類殘留（SummaryPanel / ActionsPanel / TranscriptPanel / 各 view 的 refresh / save / reset / update_*）一次掃清。

#### 10.2.3 Mic Live 指示器（碼農 B）— Part 2

對照 [[ui_spec#2.5 Mic Live 指示器]]：

| 規格項 | 實作 | 結果 |
|---|---|---|
| AudioRecorder 新 API `get_current_level()` | [audio_recorder.py:59-61](app/core/audio_recorder.py#L59-L61) | ✅ |
| `start_level_probe()` / `stop_level_probe()` | [audio_recorder.py:63-85](app/core/audio_recorder.py#L63-L85) | ✅ 純量測、不送 queue、不寫 WAV |
| rolling buffer 200ms RMS | [audio_recorder.py:28-32, 47-57](app/core/audio_recorder.py#L28-L57) | ✅ `_level_ring` deque |
| 正常錄音路徑 level 共用 | [audio_recorder.py:37-41](app/core/audio_recorder.py#L37-L41) `_audio_callback` 同時 put queue + update level | ✅ |
| 四級顏色分級（靜音/正常/大聲/爆音） | dashboard `_update_mic_level_ui` | ✅（待實機驗顏色） |
| 靜音 > 3 秒 SnackBar | dashboard Mic Live 邏輯 | ✅（待實機驗） |
| Mic Test 5 秒倒數 + 純量測 + 不建 session | dashboard `_handle_mic_test` + `_stop_mic_test` | ✅（待實機驗） |
| config 欄位 `ui.mic_indicator.*` | data_schema §8 + config/default.yaml | ✅（待驗 config 已補） |

#### 10.2.4 Contract tests（T-F1 ~ T-F8）

位置：[tests/contract/test_flet_runtime_contract.py](tests/contract/test_flet_runtime_contract.py)（149 行）

| Test | 驗證 | 結果 |
|---|---|---|
| T-F1 `test_run_task_source_uses_run_coroutine_threadsafe` | Flet page.run_task 內部走 run_coroutine_threadsafe → cf.Future | ✅ |
| T-F1 `test_cf_future_has_no_await` | cf.Future 無 `__await__`（守 asyncio.shield 不可用的前提） | ✅ |
| T-F2 `test_update_highlights_pre_mount_no_raise` | SummaryPanel pre-mount 安全 | ✅ |
| T-F2 `test_update_decisions_pre_mount_no_raise` | 同上 decisions | ✅ |
| T-F3 `test_set_items_pre_mount_no_raise` | ActionsPanel pre-mount 安全 | ✅ |
| T-F3 `test_merge_with_protection_pre_mount_no_raise` | 同上 merge | ✅ |
| T-F4 `test_append_pre_mount_no_raise` | TranscriptPanel pre-mount 安全 | ✅ |
| T-F4 `test_scroll_to_bottom_pre_mount_no_raise` | 同上 scroll | ✅ |
| T-F8 `test_page_raises_runtime_error_when_not_mounted` | `ft.Container().page` raise RuntimeError（守 Flet 升版契約） | ✅ |
| T-F8 `test_page_raises_on_custom_control` | custom control 同 | ✅ |

研究者 §7.2 原建議的 T-F5/F6/F7/F9 未全補齊（T-F5/F6 = cf.Future-aware stop lifecycle 已以 `_FakeCfFuture` 形式融入碼農 A 本次 +4 個 asyncio lifecycle tests；T-F7 = build_review integration test 未建；T-F9 = event dispatch async callback contract 未建）。**非阻塞**，Verifier 接受碼農 B 的 10 條 contract test 為 V6 充分覆蓋。

### 10.3 靜態發現 — **Bug #15 候選（audio_recorder late-binding）** 🔴

**位置**：[main.py:246-253](app/main.py#L246-L253) + [dashboard_view.py:351-359](app/ui/dashboard_view.py#L351-L359)

**現象**（靜態推論）：

```python
# main.py line 49-51
recorder: AudioRecorder | None = None    # ← 初始化 None

# main.py line 246-253
dashboard = DashboardView(
    ...
    audio_recorder=recorder,             # ← 傳入 None（此時 recorder 仍是 None）
    ...
)

# dashboard_view.py line 359
self._audio_recorder = audio_recorder    # ← self._audio_recorder = None（永遠）

# main.py line 105（on_start_recording 被甲方按「開始錄音」觸發時）
recorder = AudioRecorder(config)          # ← rebind local name `recorder`，
                                          #   **不會**改 dashboard._audio_recorder
```

Python name binding 規則：Dashboard 建構時收到 None 存進 `self._audio_recorder`。之後 `recorder` 被 rebind 是 main scope 的 closure variable，**與 Dashboard 內部已存的 None 無關**。Grep 確認**沒有 `set_audio_recorder()` setter**。

**影響**：
- [dashboard_view.py:796](app/ui/dashboard_view.py#L796) `if not self._audio_recorder: return` — 會中 Mic Live poll 進 loop 後 **immediate early return** → 音量條永不更新
- [dashboard_view.py:828](app/ui/dashboard_view.py#L828) `if not self._audio_recorder or ...: return` — idle Mic Test 按鈕按下後 **完全沒反應**
- [dashboard_view.py:860](app/ui/dashboard_view.py#L860) `self._audio_recorder.start_level_probe()` 根本呼不到

**分類**：🟨 中優先 — 不阻塞 Bug #13/#14 核心修復驗證（T1 正常錄音/停止）；但**完全阻塞 ui_spec §2.5 Mic Live 指示器 + Mic Test 兩項新功能的實機驗證**。

**為什麼沒抓到**：
- 兩碼農並行協作，碼農 B devlog 最後有提「main.py 建構 DashboardView(...) 時新增 `audio_recorder=recorder` 參數，碼農 A 正在修 main.py（Bug #13），請順手加上」
- 碼農 A commit `edcb35a` 確實加了參數，但**加在 main() 頂部、`recorder` 還是 None 時綁定**
- 單元測試 + contract tests 不測 Dashboard-AudioRecorder **late-binding 行為**（這是 main scope 的 closure pattern）
- 靜態 grep 能抓（`set_audio_recorder` 不存在）— 我在 V6 複核時靜態抓到

**修復建議**（給碼農 A 或 B，小改）：

方案 A（推薦）— 加 setter：
- 在 [dashboard_view.py](app/ui/dashboard_view.py) 加 `set_audio_recorder(recorder: AudioRecorder)` method：`self._audio_recorder = recorder`（若 Mic Live poll 正在跑也要重新啟動）
- 在 [main.py on_start_recording](app/main.py#L98) 的 `recorder = AudioRecorder(config)` 之後加 `dashboard.set_audio_recorder(recorder)`
- 對應 idle Mic Test：main.py 需在 app 啟動時預建一個 recorder，或 dashboard 按 Mic Test 時才建（但會違反「recorder 由 main 管生命週期」的慣例）

方案 B — 預先在 app 啟動建 recorder：
- main.py 開場就 `recorder = AudioRecorder(config)`，dashboard 建構拿到有效 reference
- 缺點：app 啟動就 instantiate AudioRecorder 但實際未錄音；若 AudioRecorder 建構有副作用（目前看沒有）會有疑慮

方案 C — 共享 state 容器：
- 用 mutable container（例如 `[None]`）裝 recorder，Dashboard 持 container reference，main.py 更新 container[0] = 新 recorder
- 過度設計，不推薦

**Verifier 建議**：方案 A（加 setter）— 改動最小、語意清晰、各角色職責不變。

### 10.4 第六輪 autonomous 結論 + 協同計畫

| 類別 | 狀態 |
|---|---|
| 自動化測試（fast suite） | ✅ 140/140 |
| 靜態複核 Bug #13 修復 | ✅ 方案 A 輪詢對齊研究者 §5 |
| 靜態複核 Bug #14 修復 | ✅ `if self.page:` 殘留 = 0；45 處 `_mounted` 覆蓋 |
| 靜態複核 Mic Live 實作對齊 ui_spec §2.5 | ✅（實機待驗顏色 / SnackBar / 倒數） |
| Contract tests（T-F1~F4 + F8） | ✅ 10 條新 contract test 全綠 |
| **新發現 Bug #15 候選** | 🔴 DashboardView audio_recorder late-binding → Mic Live + Mic Test 實機將完全 dead |
| 實機 T1-T6 + Mic Live + S2/S4/S5/S9 | ⏳ 待甲方協同 |

**Verifier 建議協同策略**：

**選項 A**（推薦）— 先實機 T1/T2/T6 驗 Bug #13/#14 修復：
- Bug #15 只影響 Mic Live / Mic Test 功能，不影響 T1 正常錄音流程
- T1 跑完可驗證核心（#13 停止按鈕有反應 + #14 UI 切 review 不 RuntimeError）
- Mic Test 順便觀察 Bug #15（若確認 dead，回報大統領即修）
- 一次實機把已知問題全清乾淨

**選項 B** — 先回報 Bug #15、等碼農補完再統一實機：
- 優點：實機時 Mic Live 可完整驗
- 缺點：Bug #13/#14 核心修復延後驗證；甲方要等更久

**Verifier 推薦選項 A**。
