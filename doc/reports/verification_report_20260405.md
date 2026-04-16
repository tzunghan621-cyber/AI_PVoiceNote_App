---
title: V Phase 驗證報告
date: 2026-04-06
updated: 2026-04-16
phase: V (Verify)
agent: 實驗者（Verifier）
status: 🔴 第四輪 GUI 協同發現 Bug #10/#11/#12（Bug #9 修復回歸 + UI 凍結 + async gen），持續阻塞 S3/S4/S5/S9
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
