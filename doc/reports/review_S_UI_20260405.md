---
title: Review Report — S Phase (Phase 4+5 UI)
date: 2026-04-05
type: report
status: active
author: 審察者
phase: S (Code — UI)
target: Phase 4 (main.py, main_view, dashboard_view, settings_view) + Phase 5 (terms_view, feedback_view)
verdict: ✅ Pass（第 2 輪）
tags:
  - review
  - s-phase
  - ui-review
---

# Review Report — S Phase (Phase 4+5 UI)

> 審察者獨立審查。對照 [[ui_spec]]、[[system_overview]]、[[data_schema]]。
> 審查範圍：6 個 UI 檔案（app/main.py、5 個 view 模組）

---

## 判定：❌ Fail

**理由：** 2 項 Major 級問題 — (1) 響應式佈局完全缺失（specs 明確定義三段式斷點），實作只有固定三欄；(2) 會中計時器（錄音時長）未實作（頂部列有 `_timer_text` 但從未啟動更新）。其餘實作品質良好，修正後可 Re-review 通過。

---

## 1. ui_spec 逐項審查（25 項 spec check）

### 1.1 整體佈局（ui_spec#1）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| 左側導航列 | `main_view.py:140-162` NavigationRail | ✅ | 會議/詞條/回饋 三分頁 |
| 主內容區（依導航切換） | `main_view.py:186-209` _navigate() | ✅ | |
| 頂部標題列（App 名稱 + 設定 ⚙） | `main_view.py:117-137` | ✅ | 設定用 IconButton 導航至第 4 個 view |
| 底部狀態列 | `main_view.py:24-86` StatusBar | ✅ | Ollama 狀態/模型/詞條數/暫存用量/摘要時間 |
| 最小視窗 800×600 | `main_view.py:111-112` | ✅ | `page.window.min_width=800, min_height=600` |

### 1.2 會議頁 — idle 狀態（ui_spec#2.1）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| [開始錄音] 按鈕 | `dashboard_view.py:376-379` | ✅ | |
| [匯入音檔] + 檔案選擇器（WAV/MP3/M4A） | `dashboard_view.py:382-385`, `465-480` | ✅ | `allowed_extensions=["wav", "mp3", "m4a"]` |
| 歷史紀錄列表 + 點擊進入 review | `dashboard_view.py:397-413`, `415-418` | ✅ | |

### 1.3 會議資訊對話框（ui_spec#2.2）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| 名稱（預設日期+時間） | `dashboard_view.py:423-426` | ✅ | |
| 與會人員（逗號分隔） | `dashboard_view.py:428-431` | ✅ | |
| [開始] / [跳過] 按鈕 | `dashboard_view.py:450-453` | ✅ | |
| 錄音和匯入都先彈此對話框 | `dashboard_view.py:459-463`, `465-472` | ✅ | |

### 1.4 即時儀表板（ui_spec#2.3）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| 三區塊（逐字稿/重點+決議/Actions） | `dashboard_view.py:532-538` | ✅ | |
| 逐字稿唯讀 | `dashboard_view.py:492` `TranscriptPanel(editable=False)` | ✅ | |
| 逐字稿自動捲動 | `dashboard_view.py:34` `ListView auto_scroll=True` | ✅ | |
| 「回到最新」按鈕 | `dashboard_view.py:37-41` | ✅ | |
| 校正標記即時顯示（琥珀色） | `dashboard_view.py:66-74` | ✅ | `COLOR_AMBER` + tooltip |
| 會議重點可編輯 | `dashboard_view.py:493` `SummaryPanel(editable=True)` | ✅ | |
| 決議事項獨立區塊 | `dashboard_view.py:150-160` SummaryPanel 內分離 highlights + decisions | ✅ | |
| Action Items 可編輯/新增 | `dashboard_view.py:494` `ActionsPanel(editable=True)` + `_on_add_item` | ✅ | |
| AI 更新不覆蓋已編輯（重點） | `dashboard_view.py:172-176` `_user_edited_highlights` 保護 | ✅ | |
| AI 更新不覆蓋已編輯（決議） | `dashboard_view.py:178-185` `_user_edited_decisions` 保護 | ✅ | |
| AI 更新不覆蓋已編輯（Actions） | `dashboard_view.py:225-236` `merge_with_protection` + `user_edited` | ✅ | |
| 頂部列（錄音指示燈+時長+名稱+人員+停止） | `dashboard_view.py:508-529` | ⚠️ 見 M-2 | 時長顯示未更新 |
| **響應式三段式佈局** | `dashboard_view.py:532-538` | ❌ 見 M-1 | **只有固定三欄** |
| 欄寬可拖曳 | — | ❌ 見 M-1 附帶 | |

### 1.5 會後編輯模式（ui_spec#2.4）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| 停止後自動切換 review | `main.py:109-113` `_on_pipeline_done` | ✅ | |
| 逐字稿：校正回饋（正確/錯誤） | `dashboard_view.py:76-90` feedback buttons | ✅ | |
| AI 原文灰色 / 使用者白色 | `dashboard_view.py:20-21` + `146`, `169-170` | ✅ | COLOR_AI_DIM / COLOR_USER_BRIGHT |
| Action Items 表單（checkbox/owner/deadline/priority） | `dashboard_view.py:251-291` | ✅ | |
| [匯出 Markdown] + 匯出後詢問刪音檔 | `dashboard_view.py:627-669` | ✅ | |
| [提交回饋] | `dashboard_view.py:671-683` | ✅ | |
| [刪除]（二次確認） | `dashboard_view.py:685-708` | ✅ | |

### 1.6 詞條管理頁（ui_spec#3）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| 搜尋即時過濾 | `terms_view.py:130-132` | ✅ | |
| 篩選（來源） | `terms_view.py:134-137` | ✅ | |
| [新增] / [匯入] | `terms_view.py:54-56` | ✅ | |
| 詞條列表（詞條/別名/來源/命中/成功） | `terms_view.py:106-128` | ✅ | |
| 點擊展開編輯 | `terms_view.py:142-145` | ✅ | |
| 編輯表單（6 欄位 + 統計 + 儲存/取消/刪除） | `terms_view.py:164-237` | ✅ | |
| 來源圖示 | `terms_view.py:15` ORIGIN_ICONS | ✅ | |
| 底部統計（筆數 + 平均成功率） | `terms_view.py:97-101` | ✅ | |

### 1.7 回饋統計頁（ui_spec#4）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| 整體統計（成功率/回饋數/Session 數） | `feedback_view.py:37-64` | ✅ | 含進度條 |
| 低成功率詞條（< 50%） | `feedback_view.py:91-112` | ✅ | |
| 零命中詞條 | `feedback_view.py:114-127` | ✅ | |
| 高頻遺漏 | `feedback_view.py:129-142` | ✅ | |
| 最近 Session 回饋 | `feedback_view.py:146-166` | ✅ | |

### 1.8 設定頁（ui_spec#5）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| Whisper 設定（模型/語言） | `settings_view.py:22-26` | ✅ | |
| Ollama 設定（位址/模型） | `settings_view.py:27-30` | ✅ | |
| 串流設定（週期/段落數） | `settings_view.py:31-34` | ✅ | |
| 知識庫設定 | `settings_view.py:35-38` | ✅ | |
| 匯出設定（目錄/含逐字稿/含校正） | `settings_view.py:39-43` | ✅ | |
| 音訊設定（取樣率） | `settings_view.py:44-46` | ✅ | 缺輸入裝置選擇（Minor，見 §3） |
| [儲存設定] / [恢復預設] | `settings_view.py:48-53` | ✅ | |

### 1.9 狀態列（ui_spec#6）

| Spec 項目 | 實作位置 | 狀態 | 備註 |
|-----------|---------|------|------|
| Ollama 狀態（🟢/🔴/🟡） | `main_view.py:57-64` | ✅ | |
| 模型名稱 | `main_view.py:30-32` | ✅ | |
| 詞條數量 | `main_view.py:66-68` | ✅ | |
| 暫存用量 | `main_view.py:70-78` | ✅ | |
| 會中摘要時間（上次/下次） | `main_view.py:80-86` | ✅ | |

### 1.10 對話框與通知（ui_spec#7）

| Spec 項目 | 實作位置 | 狀態 |
|-----------|---------|------|
| 匯出成功 → 刪除音檔確認 | `dashboard_view.py:648-669` | ✅ |
| 刪除 Session → 二次確認 | `dashboard_view.py:685-708` | ✅ |
| Pipeline 錯誤 → SnackBar | `main.py:73-75` | ✅ |
| 摘要更新輕量提示 | — | ⏸️ 未實作（Minor） |

### 1.11 視覺風格（ui_spec#8）

| Spec 項目 | 實作位置 | 狀態 |
|-----------|---------|------|
| 深色模式 | `main_view.py:109` ThemeMode.DARK | ✅ |
| 藍灰色系 | `main_view.py:13-21` COLOR 常數 | ✅ |
| 校正高亮琥珀色 | `dashboard_view.py:69` COLOR_AMBER | ✅ |
| 成功綠色 / 錯誤紅色 | `main_view.py:20-21` | ✅ |
| AI 灰色 / 使用者白色 | `dashboard_view.py:20-21` | ✅ |

---

## 2. StreamProcessor 串接

| 檢查項 | 位置 | 狀態 |
|--------|------|------|
| on_segment → TranscriptPanel.append | `main.py:64`, `dashboard_view.py:614-616` | ✅ |
| on_summary → SummaryPanel + ActionsPanel | `main.py:65`, `dashboard_view.py:618-623` | ✅ |
| on_status_change → pipeline done → review mode | `main.py:66`, `109-113` | ✅ |
| Pipeline 在 page.run_task 中執行 | `main.py:77`, `102` | ✅ |
| ML 模組延遲初始化（不阻塞 UI 啟動） | `main.py:42-48`, `115-128` | ✅ |

---

## 3. 品質：邏輯與架構審查

### 🟡 Major-1：響應式佈局完全缺失

**位置：** `dashboard_view.py:532-538`（live）、`583-589`（review）

**問題：** [[ui_spec#2.3]] 明確定義三段式響應佈局：
- ≥ 1400px → 三欄並排
- 960~1399px → 兩欄（逐字稿 + 右側分頁切換）
- < 960px → 單欄分頁

實作中只有固定三欄 `ft.Row([...], expand=True)`。在 960px 以下的視窗中，三欄會被壓縮到不可用的程度。

**附帶缺失：** 「欄寬可拖曳調整，偏好值記憶」也未實現。

**影響：** 窄螢幕/半邊螢幕使用場景完全無法使用。specs 將此列為核心設計（會議進行中需要在筆電側邊顯示）。

**修正建議：**
1. 使用 `page.on_resized` 監聽視窗寬度變化
2. 依據斷點切換佈局：
   - 寬：三欄 Row
   - 中：左 Row（逐字稿）+ 右 Tabs（重點/Actions）
   - 窄：單一 Tabs（逐字稿/重點/Actions）
3. 欄寬可拖曳可延後（Flet 尚無原生 resizable splitter），但斷點切換必須實現

### 🟡 Major-2：會中計時器未啟動

**位置：** `dashboard_view.py:497-498`

**問題：** 頂部列建立了 `_timer_text = ft.Text("00:00:00")`，但沒有任何機制更新這個文字。使用者在會中看到的永遠是 "00:00:00"。

[[ui_spec#2.3]] 頂部列規格：「錄音指示燈 + **時長**」— 這是使用者判斷會議進度的關鍵資訊。

**修正建議：** 在 `_build_live()` 中啟動一個定時任務：
```python
async def _update_timer():
    while self._mode == "live" and self._recording_start:
        elapsed = (datetime.now() - self._recording_start).total_seconds()
        self._timer_text.value = self._format_duration(elapsed)
        self._timer_text.update()
        await asyncio.sleep(1)

self.page.run_task(_update_timer)
```

### 🔵 Minor-1：逐字稿「遺漏回報」功能缺失

**問題：** [[ui_spec#2.4]] 定義了「可回報『遺漏』：選取文字 → 右鍵 → 回報遺漏校正」和「一鍵新增詞條」。實作中只有正確/錯誤回饋按鈕，無遺漏回報入口。

**影響：** 中。遺漏回報是回饋閉環的重要環節（使用者發現 AI 漏校正時的回饋路徑）。

### 🔵 Minor-2：設定頁缺少「輸入裝置」選擇

**問題：** [[ui_spec#5]] 定義了「輸入裝置：[預設麥克風 ▼]」，但 SettingsView 中只有取樣率，無裝置選擇。

**影響：** 低。可延後至 UI 打磨階段。sounddevice 預設使用系統預設麥克風。

### 🔵 Minor-3：摘要更新輕量提示缺失

**問題：** [[ui_spec#7]] 定義「摘要更新（會中）→ 三區塊頂部短暫閃爍『已更新』」。未實作。

**影響：** 低。使用者仍可看到摘要內容變化，只是缺少視覺提示。

### 🔵 Minor-4：`_ensure_ml_modules()` 阻塞 UI 線程

**位置：** `main.py:115-128`

**問題：** KnowledgeBase/Transcriber/SentenceTransformer 初始化在 Flet 主線程中同步執行，載入 sentence-transformers 和 faster-whisper 模型可能耗時 10~30 秒，期間 UI 完全凍結。

狀態列雖然更新為「🟡 模型載入中」（第 118 行），但因為在同一個同步調用中，`page.update()` 可能無法在模型載入前實際渲染。

**建議：** 改為 `page.run_task(async def: await asyncio.to_thread(_ensure_ml_modules))`。

### 🔵 Minor-5：settings_view `_reset()` 使用 `__init__` 重新初始化

**位置：** `settings_view.py:123`

**問題：** `self.config.__init__(self.config._path)` 直接呼叫 `__init__` 重新初始化物件。雖然能運作，但違反 Python 慣例且脆弱。若 ConfigManager.__init__ 未來改變（如加入 singleton 或快取），此處會出現非預期行為。

**建議：** 在 ConfigManager 中加一個 `reload()` 方法。

---

## 4. 安全性

| 項目 | 狀態 | 說明 |
|------|------|------|
| FilePicker 檔案選擇 | ✅ | 使用 Flet 原生 FilePicker，不接受使用者手動輸入路徑 |
| Session ID 構造路徑 | ✅ | uuid4() 產生，無注入風險 |
| YAML 匯入 | ⚠️ | `terms_view.py:151-153` 直接讀取使用者選取的檔案並 `import_yaml_batch`。KnowledgeBase 使用 `yaml.safe_load`，安全。但 term_id 仍無格式驗證（S Phase 核心模組審查已記錄，s-1） |
| SettingsView 存檔路徑 | ✅ | 只寫入 config YAML，不涉及任意路徑寫入 |

---

## 5. 程式碼品質

### 正面評價

- **色彩常數集中管理**：`main_view.py` 統一定義，所有 view 引用，易於調色
- **面板元件化**：TranscriptPanel / SummaryPanel / ActionsPanel 各自獨立，職責清晰
- **ML 延遲載入**：main.py 中 ML 模組為 None 初始，首次使用時才載入，App 啟動快速
- **LazyTermsView / LazyFeedbackView**：依賴 KB 的頁面延遲建構，避免啟動時載入模型
- **on_segment / on_summary 回呼乾淨**：StreamProcessor → DashboardView 的連接簡潔明確
- **_save_user_edits()**：匯出前自動保存使用者編輯到 Session，流程完整
- **刪除 Session 二次確認**：正確實作，防止誤刪

### 需注意

| 項目 | 位置 | 說明 |
|------|------|------|
| dialog 累積在 overlay | 多處 `page.overlay.append(dialog)` | dialog 關閉後未從 overlay 移除。長期使用會累積大量已關閉的 dialog 物件。建議在 close 時 `page.overlay.remove(dialog)` |
| FeedbackView 重複載入 | `feedback_view.py:87-88` `_build_attention_section` 再次呼叫 `get_term_stats()` 和 `list_terms()` | 與 `_build_overview` 的呼叫重複。可接受（資料量小），但建議統一傳入 |

---

## 6. 總結

### 必須修正（Re-review 前）

| # | 等級 | 摘要 | 涉及檔案 |
|---|------|------|---------|
| M-1 | 🟡 Major | **響應式佈局缺失** — 需實現三段式斷點（≥1400px 三欄、960~1399px 兩欄+分頁、<960px 單欄分頁） | `dashboard_view.py` |
| M-2 | 🟡 Major | **會中計時器未啟動** — `_timer_text` 永遠顯示 "00:00:00"，需啟動定時更新 | `dashboard_view.py` |

### 建議改善（可延後）

| # | 等級 | 摘要 |
|---|------|------|
| m-1 | 🔵 Minor | 逐字稿「遺漏回報」+ 一鍵新增詞條功能 |
| m-2 | 🔵 Minor | 設定頁補充「輸入裝置」選擇 |
| m-3 | 🔵 Minor | 摘要更新輕量提示（閃爍「已更新」） |
| m-4 | 🔵 Minor | `_ensure_ml_modules()` 改為 async（避免 UI 凍結 10~30 秒） |
| m-5 | 🔵 Minor | ConfigManager 加 `reload()` 方法取代直接呼叫 `__init__` |
| m-6 | 🔵 Minor | dialog 關閉後從 overlay 移除，避免記憶體累積 |

### 整體評價

**UI 功能覆蓋度高** — 25 項 spec 項目中 22 項正確實現。三個核心面板（TranscriptPanel / SummaryPanel / ActionsPanel）的元件化設計良好。StreamProcessor 回呼串接正確。ML 延遲載入策略合理。視覺風格符合 specs 的深色主題 + 琥珀/綠/紅色系。

兩項 Major 修正範圍明確（響應式斷點 + 計時器），預估工作量適中。

---

## 審察者簽章

- **審察者**：CLI-2
- **日期**：2026-04-05
- **審查輪次**：第 1 次
- **判定**：❌ Fail — 修正 M-1 + M-2 後 Re-review

---
---

# 第 2 輪 Re-review（2026-04-05）

> 碼農已修正 M-1（響應式佈局）+ M-2（會中計時器）。
> 逐項驗證修正是否正確。

---

## 判定：✅ Pass

**理由：** 2 項必須修正全部正確處理。響應式三段斷點使用 `page.on_resized` + `_apply_responsive_layout()` 動態切換，涵蓋 live 和 review 兩種模態。計時器使用 `page.run_task` 啟動 async 定時更新，並在離開 live 模式時正確停止。

---

## 1. M-1 驗證：響應式佈局 — ✅ 通過

### 修正位置

- `dashboard_view.py:354` — `page.on_resized = self._on_page_resized`
- `dashboard_view.py:631-636` — `_on_page_resized()` 事件處理
- `dashboard_view.py:637-677` — `_apply_responsive_layout()` 三段斷點邏輯
- `dashboard_view.py:544` — live 模式呼叫 `_apply_responsive_layout()`
- `dashboard_view.py:608` — review 模式同樣呼叫

### 逐項驗證

| 檢查項 | 結果 | 說明 |
|--------|------|------|
| ≥1400px → 三欄並排 | ✅ | 第 641-649 行：`ft.Row` 三個 `expand=1` Container + VerticalDivider |
| 960~1399px → 兩欄（逐字稿 + 右側 Tabs） | ✅ | 第 651-665 行：左 transcript + 右 `ft.Tabs(重點/Actions)` |
| <960px → 單欄分頁 | ✅ | 第 667-677 行：`ft.Tabs(逐字稿/重點/Actions)` |
| 視窗縮放時動態切換 | ✅ | `page.on_resized` 觸發 `_apply_responsive_layout()` + `_layout_container.update()` |
| live 和 review 都使用響應式 | ✅ | `_build_live()` 第 544 行、`_build_review()` 第 608 行都呼叫 |
| 只在 live/review 模式響應 | ✅ | `_on_page_resized` 第 633 行檢查 `self._mode in ("live", "review")` |
| 面板元件不被重建 | ✅ | 三個 panel 在 `_build_live/_build_review` 建立一次，`_apply_responsive_layout` 只重新排列容器，不重新實例化 panel |

**審查意見：** 使用 `_layout_container` 作為中間容器、`_apply_responsive_layout()` 只更換其 `content`，是正確的策略 — 避免斷點切換時丟失面板狀態（已輸入的逐字稿、使用者編輯等）。Flet 的 `page.on_resized` 在每次視窗大小改變時觸發，可即時切換佈局。

### 與 spec 對照

| ui_spec 要求 | 實作 | 符合 |
|-------------|------|------|
| 三欄並排 | `ft.Row([transcript, summary, actions])` | ✅ |
| 兩欄：逐字稿 + 右側分頁切換 | `ft.Row([transcript, ft.Tabs([重點, Actions])])` | ✅ |
| 單欄分頁 | `ft.Tabs([逐字稿, 重點, Actions])` | ✅ |
| 欄寬可拖曳 | ⏸️ 未實作 | 可接受 — Flet 尚無原生 resizable splitter，斷點切換已滿足核心需求 |

---

## 2. M-2 驗證：會中計時器 — ✅ 通過

### 修正位置

- `dashboard_view.py:339` — `self._timer_running = False` 控制旗標
- `dashboard_view.py:681-696` — `_start_timer()` 啟動 async 定時任務
- `dashboard_view.py:698-700` — `_stop_timer()` 停止計時器
- `dashboard_view.py:552` — `_build_live()` 結尾呼叫 `_start_timer()`
- `dashboard_view.py:362-364` — `set_mode()` 離開 live 時呼叫 `_stop_timer()`

### 逐項驗證

| 檢查項 | 結果 | 說明 |
|--------|------|------|
| 開始錄音時啟動 | ✅ | `_build_live()` 最後一行（第 552 行）呼叫 `_start_timer()` |
| 每秒更新 | ✅ | `_update_timer` 迴圈：計算 elapsed → 格式化 → `_timer_text.update()` → `await asyncio.sleep(1)` |
| 停止錄音時停止 | ✅ | `set_mode()` 第 363 行：離開 live 時呼叫 `_stop_timer()` 設 `_timer_running = False` |
| 不阻塞 UI | ✅ | 使用 `page.run_task()` 在 Flet event loop 中執行 async task |
| 計時器 exception 安全 | ✅ | 第 690-693 行：`_timer_text.update()` 包裹在 `try/except` 中，元件被銷毀時優雅退出 |
| 使用 `_recording_start` 計算 | ✅ | 第 687 行：`elapsed = (datetime.now() - self._recording_start).total_seconds()` — 即使計時器有短暫延遲也不會累積誤差 |

**審查意見：** 計時器基於 `_recording_start` 的絕對時間差計算，而非累加秒數，這是正確做法 — 即使 `asyncio.sleep(1)` 有微小延遲，顯示的時間仍然精確。`try/except` 防護在 panel 被銷毀（如切換到 idle）時避免 crash。

---

## 3. 總結

| 類別 | 結果 |
|------|------|
| M-1（響應式佈局） | ✅ 三段斷點正確實現，live/review 雙模態支持，動態切換 |
| M-2（會中計時器） | ✅ 啟動/更新/停止生命週期完整，時間計算精確 |
| 新引入問題 | 無 |

**Phase 4+5 UI 品質確認：** 25 項 spec 項目中 24 項正確實現（欄寬可拖曳為 Flet 框架限制，可接受延後）。響應式佈局 + 計時器補全後，核心 UI 功能完整。可進入 V Phase（驗證）。

---

## 審察者簽章

- **審察者**：CLI-2
- **日期**：2026-04-05
- **審查輪次**：第 2 次
- **判定**：✅ Pass — Phase 4+5 UI 通過，可進入 V Phase
