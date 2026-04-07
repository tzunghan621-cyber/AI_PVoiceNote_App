---
title: Flet 0.84.0 API Breaking Changes — Bug Report
date: 2026-04-06
updated: 2026-04-08
type: bug-report
phase: V (Verify)
agent: 實驗者（Verifier）
status: 🔴 阻塞中（Bug #5 待修復）
severity: high
tags: [bug, flet, api-breakage, v-phase]
---

# Flet 0.84.0 API Breaking Changes — Bug Report

> 對應驗證：[[verification_report_20260405]]
> 對應日誌：[[devlog_20260406_v_phase]]

## 摘要

V Phase 驗證期間，連續發現 **5 個** Flet 0.84.0 API 不相容問題：
- Bug #1~#3：已修復
- Bug #4：碼農 B 在 commit `46dc141` 全面 migration 中宣稱已處理 Tabs，但實測仍報錯
- Bug #5：Tabs constructor `tabs=` 參數消失，與 Bug #4 為同一架構重設計的兩個面向

> ⚠️ **建議**：請 Researcher 系統性掃過 Flet 0.84.0 升級指南，一次找齊所有不相容處，避免逐個踩雷。

---

## Bug #1：`AttributeError: property 'page' has no setter`

| 項目 | 內容 |
|---|---|
| 狀態 | ✅ 已修復（V Phase 第一輪） |
| 觸發 | App 啟動 → 建立 `DashboardView` 時 |
| 檔案 | [[dashboard_view.py]]、[[terms_view.py]] |

### 原因
繼承 `ft.Container` 的子類別不能再用 `self.page = page`，因為 Flet 0.84.0 的 `page` 是唯讀 property。

### 修復
將 `self.page` 改名為 `self._page_ref`，全檔替換所有引用。

---

## Bug #2：`OutlinedButton(color=...)` 不接受

| 項目 | 內容 |
|---|---|
| 狀態 | ✅ 已修復 |
| 觸發 | 進入 idle 頁面 → 渲染按鈕 |
| 檔案 | [[dashboard_view.py]]:391 |

### 原因
Flet 0.84.0 的 `OutlinedButton` 不再直接接受 `color=` 參數。

### 修復
```python
# Before
ft.OutlinedButton("📁 匯入音檔", color=COLOR_TEXT, ...)

# After
ft.OutlinedButton("📁 匯入音檔", style=ft.ButtonStyle(color=COLOR_TEXT), ...)
```

---

## Bug #3：`FilePicker(on_result=...)` 不接受

| 項目 | 內容 |
|---|---|
| 狀態 | ✅ 已修復（commit `d8186ba`） |
| 觸發 | 點「匯入音檔」/「匯出 Markdown」/「匯入詞條 YAML」 |
| 檔案 | [[dashboard_view.py]]:484, 717、[[terms_view.py]]:159 |

### 原因
Flet 0.84.0 的 `FilePicker` 改為直接呼叫模式：
- `pick_files()` 改為 `await` 直接回傳 `list[FilePickerFile]`
- `save_file()` 改為 `await` 直接回傳 `Optional[str]`
- 不再用 `on_result` callback、不需要 `picker.overlay.append()`

### 修復
```python
# Before
def on_result(result):
    if result.files:
        path = result.files[0].path
        # ...
picker = ft.FilePicker(on_result=on_result)
self._page_ref.overlay.append(picker)
self._page_ref.update()
picker.pick_files(dialog_title="...", allowed_extensions=[...])

# After (async)
picker = ft.FilePicker()
files = await picker.pick_files(dialog_title="...", allowed_extensions=[...])
if files:
    path = files[0].path
    # ...
```

---

## Bug #4：`Tab(text=..., content=...)` 不接受 🔴

| 項目 | 內容 |
|---|---|
| 狀態 | 🔴 待修復 |
| 觸發 | 進入 live 模式（兩欄/單欄佈局） |
| 檔案 | [[dashboard_view.py]]:653~654, 669~671 |
| 阻塞 | #2 響應式佈局、#5/#6/#7/#8 Pipeline 整合 |

### 錯誤訊息
```
TypeError: Tab.__init__() got an unexpected keyword argument 'text'
```

### 完整 traceback
```
File "app/ui/dashboard_view.py", line 484, in <lambda>
  on_confirm=lambda title, parts: self._start(title, parts, "import", path),
File "app/ui/dashboard_view.py", line 493, in _start
  self._on_import_audio(title, participants, file_path)
File "app/main.py", line 84, in on_import_audio
  dashboard.set_mode("live", session)
File "app/ui/dashboard_view.py", line 370, in set_mode
  self._build_live()
File "app/ui/dashboard_view.py", line 541, in _build_live
  self._apply_responsive_layout()
File "app/ui/dashboard_view.py", line 653, in _apply_responsive_layout
  ft.Tab(text="💡 重點", content=self.summary_panel),
TypeError: Tab.__init__() got an unexpected keyword argument 'text'
```

### 新 API（由 `inspect.signature(ft.Tab.__init__)` 確認）

```python
Tab.__init__(
    self,
    label: str | Control | None = None,        # 取代 text
    icon: IconData | Control | None = None,
    height: int | float | None = None,
    icon_margin: ... = None,
    *,
    # ... 其他 metadata 參數
)
```

**關鍵變動**：
1. `text` → 改為 `label`
2. **`content` 參數被移除** — Tab 現在只負責 tab header（label/icon），實際內容必須由其他機制管理（架構變動，不只是改參數名）

### 影響範圍

| 佈局 | 寬度 | 是否使用 Tabs | 受影響 |
|---|---|---|---|
| 三欄 | ≥1200 | 否（用 Row） | ❌ |
| 兩欄 | 800~1199 | 是 | ✅ |
| 單欄 | <800 | 是 | ✅ |

> 三欄理論上不受 Bug #4 影響，但目前因 `_apply_responsive_layout()` 一進入即崩潰，連三欄都無法測試。

### 建議修復策略

碼農需研讀 Flet 0.84.0 Tabs 新 API 範例（例如查 `ft.Tabs` 的 `selected_index` + `on_change` + 用 `Stack` 切換 content 等模式），可能要重構 `_apply_responsive_layout()` 中 Tabs 的組裝方式。

---

## Bug #5：`Tabs(tabs=...)` 不接受 🔴

| 項目 | 內容 |
|---|---|
| 狀態 | 🔴 待修復（V Phase 第二輪發現） |
| 觸發 | 點「匯入音檔」→ 選音檔 → 填會議資訊 → 進入 live 模式 |
| 檔案 | [[dashboard_view.py]]:657（兩欄）、:680（單欄） |
| 阻塞 | #2 響應式佈局、#5/#6/#7/#8 Pipeline 整合 |

### 錯誤訊息
```
TypeError: Tabs.__init__() got an unexpected keyword argument 'tabs'
```

### 完整 traceback
```
File "app/ui/dashboard_view.py", line 481, in <lambda>
  on_confirm=lambda title, parts: self._start(title, parts, "import", path),
File "app/ui/dashboard_view.py", line 490, in _start
  self._on_import_audio(title, participants, file_path)
File "app/main.py", line 82, in on_import_audio
  dashboard.set_mode("live", session)
File "app/ui/dashboard_view.py", line 370, in set_mode
  self._build_live()
File "app/ui/dashboard_view.py", line 539, in _build_live
  self._apply_responsive_layout()
File "app/ui/dashboard_view.py", line 657, in _apply_responsive_layout
  right_tabs = ft.Tabs(
TypeError: Tabs.__init__() got an unexpected keyword argument 'tabs'
```

### 新 API（由 `inspect.signature(ft.Tabs.__init__)` 確認）

```python
Tabs.__init__(
    self,
    content: Control,           # 必填：單一 content（不是 list）
    length: int,                # 必填：tab 數量
    selected_index: int = 0,
    animation_duration: ... = None,
    on_change: Callable | None = None,
    ...
)
```

**重大架構變動**：
1. **`tabs=[Tab(...), Tab(...)]` 完全消失**
2. Tabs 變成「純 selector」：你只給它 `length`（幾個 tab）、`content`（一個會根據 `selected_index` 自己切換的 widget）、`on_change` callback
3. **tab 標籤（label/icon）和內容切換邏輯需要使用者自己組合** — 例如用 Stack 疊放多個 panel，或在 `on_change` 時重建 content

### 與 Bug #4 的關係

Bug #4（`Tab(text=...)`）和 Bug #5（`Tabs(tabs=...)`）是 Flet 0.84.0 對整個 Tabs/Tab 系統重設計的兩個面向：
- 舊：`Tabs(tabs=[Tab(text=..., content=...), ...])`
- 新：`Tabs(content=<widget that switches by selected_index>, length=N, on_change=...)` + 自己處理 tab header

碼農 B 在 commit `46dc141` 中**整個 Tabs/Tab 區塊看起來沒動過** — 5 個 `Tab(text=...)` + 2 個 `Tabs(tabs=...)` 都還是舊 API。

### 影響

| 佈局 | 寬度 | 受影響 |
|---|---|---|
| 三欄 | ≥1200 | ⚠️ 雖然三欄用 Row，但任何寬度進 live 模式都會崩潰（程式碼路徑可能在條件分支前先評估 Tabs 構造） |
| 兩欄 | 960~1199 | 🔴 |
| 單欄 | <960 | 🔴 |

### 建議掃描指令

下次 migration 應補強 grep 範圍：

```bash
ft.Tab(    # 應抓到 5 處
ft.Tabs(   # 應抓到 2 處
```

---

## V Phase 驗證進度

| # | 項目 | 狀態 |
|---|---|---|
| 1 | App 啟動 + 介面外觀 | ✅ PASS |
| 2 | 響應式佈局 | 🔴 BLOCKED by Bug #4 |
| 3 | 即時錄音 | ⏳ |
| 4 | 匯入音檔（對話框） | ✅ PASS（檔案選擇 + 會議資訊填寫 OK） |
| 5 | 完整 Pipeline | 🔴 BLOCKED by Bug #4 |
| 6 | 即時儀表板三區塊 | 🔴 BLOCKED by Bug #4 |
| 7 | 會後編輯模式 | ⏳ 依賴 #5 |
| 8 | 匯出 Markdown | ⏳ 依賴 #5 |
| 9 | 詞條管理 CRUD | ⏳ |
| 10 | 設定頁面 | ⏳ |

---

## Verifier 結語

**第一輪結語（驗證 Bug #4 時）**：強烈建議大統領在派碼農修 Bug #4 前，先請 Researcher 整理一份 Flet 0.84.0 完整不相容清單，否則我們會繼續一個一個踩雷。

**第二輪結語（驗證 Bug #5 時）**：碼農 B 在 commit `46dc141` 雖宣稱完成 28+ 處全面 migration，但 Tabs/Tab 區塊（共 7 處用法）整塊被 grep 漏掉。建議下次 migration：

1. 派 Researcher 先整理新舊 API mapping table（含 Tabs 等架構重設計類）
2. 碼農修改後，**先在本機開 GUI 點過所有功能路徑**，而非只跑 import smoke test 和單元測試
3. Verifier 在執行 GUI 驗證前，先用 grep 對照 Researcher 的 mapping table 做一次 sanity check

待命中，等 Bug #5 修復後繼續驗證 #2、#5~#10。