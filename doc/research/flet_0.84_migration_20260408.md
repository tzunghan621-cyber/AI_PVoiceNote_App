---
title: Flet 0.84.0 Migration — 完整不相容清單與本專案受影響盤點
date: 2026-04-08
type: research
agent: 研究者（Researcher）
status: 完成
tags: [research, flet, migration, breaking-change, v-phase]
related:
  - "[[bug_report_flet_api_20260406]]"
  - "[[devlog_20260406_v_phase]]"
---

# Flet 0.84.0 Migration — 完整不相容清單與本專案受影響盤點

> 對應 Bug Report：[[bug_report_flet_api_20260406]]
> 目的：碼農據此**一次修完**所有不相容處，避免逐個踩雷重來驗證循環。

## 背景

- 本專案 `pip show flet` 確認版本 = **0.84.0**
- Flet 自 **0.70.0 起**（aka Flet 1.0 Alpha）→ **0.80.0**（Flet 1.0 Beta）→ **0.84.0** 連續釋出 **大量 V1 breaking changes**
- 官方原文：「0.80.0 is not a drop-in upgrade — it includes breaking changes」
- **單一權威來源**：[flet-dev/flet#5238 — V1 breaking changes](https://github.com/flet-dev/flet/issues/5238)
- V Phase 已踩到的 4 顆雷（Page setter、OutlinedButton.color、FilePicker.on_result、Tab.text/content）只是冰山一角

---

## A. Flet 1.0 / 0.84 Breaking Change 完整清單

### A1. App 啟動 / 全域 API

| 舊 | 新 |
|---|---|
| `ft.app(target=main)` | `ft.run(main)` 或 `ft.run(main=main)` |
| `ft.alignment.center` | `ft.Alignment.CENTER`（改為 Enum 常數） |
| `ft.animation.Animation(...)` | `ft.Animation(...)` |
| `ft.padding.symmetric(...)` / `ft.padding.only(...)` | `ft.Padding(vertical=, horizontal=, top=, ...)`（**只接受具名參數**） |

### A2. Page

| 舊 | 新 |
|---|---|
| `page.on_resized` | `page.on_resize` |
| `page.client_storage` | `page.shared_preferences` |
| `page.snack_bar = SnackBar(...)` + `.open = True` | `page.show_dialog(snack_bar)`（SnackBar 走 dialog 機制） |
| `page.dialog = dlg` + `dlg.open = True` | `page.show_dialog(dlg)` / `page.pop_dialog()` |
| `page.overlay.append(file_picker)` | `page.services.append(file_picker)`（FilePicker 變 service） |
| `page.drawer` / `page.end_drawer` | `NavigationDrawer(position=...)` |
| **`page` 是 Container 子類別的唯讀 property** | 自訂 attr 必須改名（如 `_page_ref`） |

### A3. Buttons（ElevatedButton / OutlinedButton / TextButton / FilledButton 等）

| 舊 | 新 |
|---|---|
| `Button("文字")` 的 `text=` 參數 | `content="文字"`（位置參數仍可用，但 `text=` 已移除） |
| `Button(color=...)`、`Button(bgcolor=...)` 直接設 | 必須包進 `style=ft.ButtonStyle(color=..., bgcolor=...)` |
| `Button(icon_color=...)` | 同上，移到 `ButtonStyle` |

> ⚠️ 本專案多處 `ElevatedButton(..., bgcolor=COLOR_RED, color=COLOR_TEXT)` / `OutlinedButton(icon_color=COLOR_RED)` 都會中招。

### A4. Tabs / Tab（最大架構變動）

| 舊 | 新 |
|---|---|
| `Tab(text="...", content=Panel)` | `Tab(label="...")`，**`content` 已移除** |
| `Tabs.is_secondary` | `Tabs.secondary` |

**架構變動**：Tab 只負責 header（label + icon）。實際內容必須由 `Tabs.on_change` + `selected_index` 切換外部 `Stack` / `Container.content`，**不能再把 panel 塞進 Tab**。

### A5. FilePicker

| 舊 | 新 |
|---|---|
| `FilePicker(on_result=cb)` + `page.overlay.append(picker)` + `picker.pick_files(...)` | `picker = FilePicker()`、`page.services.append(picker)`、`files = await picker.pick_files_async(...)` 直接回傳結果 |
| `picker.save_file(...)` | `await picker.save_file(...)` 直接回傳 `Optional[str]` |
| `on_result` callback | **已廢除** |

### A6. Icon / Badge / Checkbox / Card / Chip / Switch / Markdown / BoxDecoration / Canvas Text

| 控制項 | 舊 | 新 |
|---|---|---|
| Icon | `Icon(name=...)` | `Icon(icon=...)` |
| Badge | `text=` | `label=` |
| Checkbox | `is_error=` | `error=` |
| Card | `color=` | `bgcolor=` |
| Card | `is_semantic_container=` | `semantic_container=` |
| Chip | `click_elevation=` | `press_elevation=` |
| Switch | `label_style=` | `label_text_style=` |
| Markdown | `img_error_content=` | `image_error_content=` |
| BoxDecoration | `shadow=` | `shadows=` |
| canvas.Text | `text=` | `value=` |

### A7. Dropdown / SegmentedButton

- Dropdown：`on_change` 只在「可編輯模式輸入文字」觸發；列表選擇要用新事件 `on_select`
- SegmentedButton：`selected: Set[str]` → `selected: List[str]`（傳 list 而非 set）

### A8. Cupertino 系列

- `is_default_action` → `default`
- `is_destructive_action` → `destructive`

### A9. NavigationRailDestination / SafeArea / Pagelet

- `NavigationRailDestination.label_content` → 改用 `label`
- `SafeArea.left/top/right/bottom` → `avoid_intrusions_left/top/right/bottom`
- `Pagelet.bottom_app_bar` → `bottom_appbar`

### A10. Drag & Drop

- `DragTarget.on_will_accept`：用 `e.accept`（不再是 `e.data`）
- `DragTarget.on_leave`：用 `e.src_id`

### A11. ScrollableControl / scroll_to

- `scroll_to(key=)` → `scroll_to(scroll_key=)`
- 控制項 key 要包成 `key=ft.ScrollKey(<value>)`
- `on_scroll_interval` → `scroll_interval`

### A12. Theme

從 `Theme` 移除（必須改用 `ColorScheme` / `DividerTheme`）：
- `primary_swatch` → `color_scheme_seed`
- `primary_color` → `ColorScheme.primary`
- `primary_color_dark` / `primary_color_light`
- `shadow_color` → `ColorScheme.shadow`
- `divider_color` → `DividerTheme.color`

### A13. Async 命名

- 所有方法移除 `_async` 後綴（async 是預設）
- 同時移除 fire-and-forget 對應方法

---

## B. 本專案受影響檔案 / 行號清單

以下盤點是針對 `app/ui/*.py` + `app/main.py` 全檔掃描的結果。**包含已知 4 顆雷 + Researcher 新發現的潛在雷**。

### B1. 🔴 高危 — 啟動就崩 / 阻塞 V Phase

| # | 檔案:行號 | 問題 | 對應 §|
|---|---|---|---|
| 1 | [main.py:177](app/main.py#L177) | `ft.app(target=main)` → `ft.run(main)` | A1 |
| 2 | [dashboard_view.py:354](app/ui/dashboard_view.py#L354) | `page.on_resized = ...` → `page.on_resize` | A2 |
| 3 | [dashboard_view.py:653](app/ui/dashboard_view.py#L653) | `Tab(text=, content=)` × 2（兩欄佈局） | A4 |
| 4 | [dashboard_view.py:669-671](app/ui/dashboard_view.py#L669-L671) | `Tab(text=, content=)` × 3（單欄佈局） | A4 |
| 5 | [dashboard_view.py:650](app/ui/dashboard_view.py#L650) | `ft.Tabs(...)` 整個架構需重構（content 移到外部 Stack） | A4 |
| 6 | [main_view.py:94, 107](app/ui/main_view.py#L94) | `MainView` 繼承（疑似）Container 但 `self.page = page` → 需改 `_page_ref` | A2 |

### B2. 🟠 中危 — 進入特定流程才崩

#### Dialog 開關（`dlg.open = True/False` 模式已廢除）→ A2

| 檔案:行號 | 用途 |
|---|---|
| [dashboard_view.py:447, 452, 466](app/ui/dashboard_view.py#L447) | 會議資訊輸入對話框 |
| [dashboard_view.py:722, 726, 738](app/ui/dashboard_view.py#L722) | 匯出後刪檔確認 |
| [dashboard_view.py:764, 777](app/ui/dashboard_view.py#L764) | 刪除會議確認 |
| [dashboard_view.py:772](app/ui/dashboard_view.py#L772) | `setattr(dlg, 'open', False)` lambda |
| [terms_view.py:205, 212, 234](app/ui/terms_view.py#L205) | 詞條 CRUD 對話框 |

→ 統一改用 `page.show_dialog(dlg)` / `page.pop_dialog()`。

#### SnackBar（`page.snack_bar = ...` + `.open = True` 模式已廢除）→ A2

| 檔案:行號 |
|---|
| [dashboard_view.py:793-794](app/ui/dashboard_view.py#L793) |
| [terms_view.py:158](app/ui/terms_view.py#L158)（含上一行 `snack_bar = ...`） |
| [settings_view.py:117-118](app/ui/settings_view.py#L117) |
| [main.py:73-74, 98-99](app/main.py#L73) |

→ 改 `page.show_dialog(ft.SnackBar(...))`。

#### Padding（`ft.padding.symmetric(...)` / `ft.padding.only(...)` 改具名 `ft.Padding`）→ A1

| 檔案:行號 |
|---|
| [dashboard_view.py:73, 99, 275, 290, 534, 585, 600](app/ui/dashboard_view.py#L73) |
| [main_view.py:53, 135](app/ui/main_view.py#L53) |
| [terms_view.py:69, 125](app/ui/terms_view.py#L69) |
| [settings_view.py:63](app/ui/settings_view.py#L63) |

> ⚠️ 注意：實測 0.84 是否仍保留 `ft.padding.symmetric` 為 alias 不確定，但官方 V1 文件已宣告移除。建議全部改 `ft.Padding(horizontal=..., vertical=...)` / `ft.Padding(top=..., bottom=...)`。

#### Alignment（`ft.alignment.center` → `ft.Alignment.CENTER`）→ A1

| 檔案:行號 |
|---|
| [feedback_view.py:79](app/ui/feedback_view.py#L79) |
| [main_view.py:204](app/ui/main_view.py#L204) |

#### Button 樣式（color / bgcolor / icon_color 直接傳已移除）→ A3

| 檔案:行號 | 內容 |
|---|---|
| [dashboard_view.py:596](app/ui/dashboard_view.py#L596) | `OutlinedButton("刪除", icon_color=COLOR_RED, ...)` → `style=ButtonStyle(...)` |
| [dashboard_view.py:734](app/ui/dashboard_view.py#L734) | `ElevatedButton("刪除", bgcolor=COLOR_RED, color=COLOR_TEXT)` → 同上 |
| [dashboard_view.py:773](app/ui/dashboard_view.py#L773) | 同上 |

> Bug #2 在 [dashboard_view.py:391-393](app/ui/dashboard_view.py#L391) 已修，但其他殘餘還沒修。

### B3. 🟡 低危 — 目前未直接呼叫，但要確認

- `ft.IconButton(ft.Icons.X, icon_color=...)` 多處（[dashboard_view.py:80, 85, 208, 282](app/ui/dashboard_view.py#L80) 等）
  → IconButton 與一般 Button 不同，`icon_color` 仍是頂層 property，**理論上 OK**，但建議測試後確認。
- `ft.Animation(1000, ft.AnimationCurve.EASE_IN_OUT)` 在 [dashboard_view.py:518](app/ui/dashboard_view.py#L518) — 已是新 API，OK。
- `ft.Icons.XXX`（大寫複數）— 0.84 仍支援，OK。
- `ft.Icon(ft.Icons.RECORD_VOICE_OVER, ...)` 在 [main_view.py:120](app/ui/main_view.py#L120) — 第一個位置參數對應 `icon=`，OK。

---

## C. 修正優先順序（建議施工順序）

| 優先 | 範圍 | 理由 |
|---|---|---|
| **P0** | §B1 全部（6 項） | 阻塞 App 啟動 / live 模式 / 響應式佈局 |
| **P1** | Dialog `open=` 改 `page.show_dialog` | 對話框是核心互動，遲早會踩 |
| **P1** | SnackBar 改 `page.show_dialog(SnackBar)` | 任何錯誤訊息會直接 crash |
| **P2** | Button 殘餘 `bgcolor/color/icon_color` 改 `ButtonStyle` | 進入 review/詞條 CRUD 才會踩 |
| **P2** | `ft.padding.symmetric` 全改 `ft.Padding(...)` | 0.84 可能還有 alias，但官方已宣告移除 |
| **P3** | `ft.alignment.center` → `ft.Alignment.CENTER` | 同上，alias 風險 |
| **P3** | 全檔 grep 確認 `ft.app(target=)`、`page.client_storage`、`page.drawer` 等本專案目前未使用 | 防呆 |

---

## D. Tabs 重構建議（Bug #4 解法骨架）

新 Tabs API 用法（label-only）：

```python
# 兩欄佈局（兩個 tab）
self._right_content = ft.Container(content=self.summary_panel, expand=True)
right_tabs = ft.Tabs(
    selected_index=0,
    on_change=lambda e: self._switch_right_tab(e.control.selected_index),
    tabs=[
        ft.Tab(label="💡 重點"),
        ft.Tab(label="✅ Actions"),
    ],
)
right_column = ft.Column([right_tabs, self._right_content], expand=True, spacing=0)

def _switch_right_tab(self, idx: int):
    self._right_content.content = self.summary_panel if idx == 0 else self.actions_panel
    self._right_content.update()
```

單欄佈局類推（一個外部 content slot + 三個 Tab label，on_change 切換）。

---

## E. 引用來源

- [flet-dev/flet#5238 — V1 breaking changes（權威清單）](https://github.com/flet-dev/flet/issues/5238)
- [Flet 1.0 Beta 公告](https://flet.dev/blog/flet-1-0-beta/)
- [Flet 1.0 Alpha 公告](https://flet.dev/blog/introducing-flet-1-0-alpha/)
- [Flet 0.84.0 Release Announcement](https://flet.dev/blog/flet-v-0-84-release-announcement/)
- [flet-dev/flet#6172 — Improve version migrations](https://github.com/flet-dev/flet/issues/6172)
- [flet/CHANGELOG.md](https://github.com/flet-dev/flet/blob/main/CHANGELOG.md)
- [Flet Tabs 文件](https://flet.dev/docs/controls/tabs/)
- 本機驗證：`pip show flet` → 0.84.0；`inspect.signature(ft.Tab.__init__)` 確認 `text`/`content` 已移除

---

## G. 補強研究（2026-04-09）— Lifecycle + Constructor 二輪掃描

> ⚠️ **SSoT Redirect（2026-04-17）：** 本節部分結論在 V Phase 第五輪實機驗證後發現不完整（`if self.page:` 守衛實為假守衛、`page.run_task` 回傳型別未驗）。**lifecycle 議題以 [[flet_0.84_async_lifecycle_20260417]] 為單一權威來源**；本節保留供歷史脈絡。

> 對應 V Phase 第三輪發現：Bug #6（Dropdown.on_change 不接受）+ Bug #7（Control must be added to the page first）。
> 第一輪報告（§A~§F）漏掉這兩類問題，本節補齊。

### G1. Lifecycle 變動（最重要的新發現）

Flet 1.0 / 0.84 把控制項生命週期改為**嚴格 mount-aware**：

| 階段 | 是否可呼叫 `.update()` |
|---|---|
| `__init__()` 內 | ❌ 會丟 `AssertionError: Control must be added to the page first` |
| 控制項建立後、加入 page tree 前 | ❌ 同上 |
| `did_mount()` 觸發後 | ✅ |
| 任何使用者事件 callback（`on_click` 等） | ✅（事件觸發時控制項一定已 mount） |
| `before_update()` 內 | ⚠️ 不可呼叫 `update()`（會無限遞迴） |

**正確生命週期模式**：
```python
class MyView(ft.Container):
    def __init__(self, ...):
        self._content = ft.Column()
        super().__init__(content=self._content)
        # ❌ 不要在這裡呼叫 self._content.update() 或 self.refresh()
        # 只能準備資料、組裝 controls，不能 update

    def did_mount(self):
        # ✅ 在這裡做首次資料載入 + update
        self.refresh()

    def refresh(self):
        # 重組 controls...
        if self.page:  # 防呆：確認已 mount
            self._content.update()
```

舊版 Flet 在 `__init__` 呼叫 `update()` 會被靜默忽略或延遲，所以舊 codebase 大量這樣寫。0.84 之後一律炸。

### G2. 本專案受影響的 `.update()` 呼叫盤點

#### 🔴 P0 — `__init__` 階段直接呼叫 update（保證炸）

| 檔案:行號 | 問題 | 修法 |
|---|---|---|
| [feedback_view.py:19, 35](app/ui/feedback_view.py#L19) | `__init__` 末尾呼叫 `self.refresh()`，refresh 內 `self._content.update()` | 移除 `__init__` 內的 `self.refresh()`，改在 `did_mount()` 呼叫 |

#### 🟠 P1 — refresh / build helper 在掛載前可能被呼叫

這些方法本身 OK，但需確認所有呼叫點都在 mount 之後：

| 檔案:行號 | 方法 |
|---|---|
| [main_view.py:64, 68, 78, 86](app/ui/main_view.py#L64) | StatusBar `update_*` 系列（會被定時器/事件呼叫，mount 後 OK） |
| [main_view.py:209, 210](app/ui/main_view.py#L209) | `content_area.update()` / `nav_rail.update()`（在 `select_view` 內，事件觸發 OK） |
| [terms_view.py:103, 104](app/ui/terms_view.py#L103) | `_terms_list.update()` / `_footer.update()`（refresh 內，需確認首次呼叫時機） |
| [dashboard_view.py:170, 176, 185, 249](app/ui/dashboard_view.py#L170) | summary/actions panel 的 set_* 方法 |
| [dashboard_view.py:103, 124](app/ui/dashboard_view.py#L103) | `_segments_list.update()`（add_segment 流程，事件觸發 OK） |
| [dashboard_view.py:373](app/ui/dashboard_view.py#L373) | `set_mode` 內的 `self._content.update()`（會在 mount 後呼叫 OK） |
| [dashboard_view.py:632](app/ui/dashboard_view.py#L632) | `_apply_responsive_layout` 內 update |
| [settings_view.py:130](app/ui/settings_view.py#L130) | `_reset` 內 update（事件觸發 OK） |
| [main.py:149, 158](app/main.py#L149) | `LazyTermsView.did_mount` 風格的 lazy load → 確認改用 `did_mount()` hook |

**通用防呆模式**：所有 helper 內的 `xxx.update()` 之前加 `if self.page:` 守衛，避免 unmount 後/mount 前呼叫。

#### 🟢 page.update() 呼叫（mount 前後都安全，但要確認 page 不為 None）

[main.py:109, 115, 124](app/main.py#L109) — Pipeline callback 內，執行時 page 必定存在 OK。

### G3. Constructor 變動補強

> 第一輪報告 §A 已列 Tab/Tabs/FilePicker/Buttons/Icon 等。本節補上 V Phase 新踩到的 + 推測會踩的。

#### Dropdown（Bug #6 確認）

| 舊 | 新 |
|---|---|
| `Dropdown(on_change=cb)` 用來監聽列表選擇 | `Dropdown(on_select=cb)` |
| `on_change` | 只在「editable 模式輸入文字」時觸發 |
| `Dropdown(label_style=...)` | 仍可用，**但要確認 0.84 是否改名**（部分元件 `label_style` → `label_text_style`，見 §A6 Switch） |
| `ft.dropdown.Option(o)` | 建議改 `ft.DropdownOption(o)`（V1 命名空間扁平化） |

**本專案受影響**：
- [settings_view.py:80-87](app/ui/settings_view.py#L80) — `_dropdown()` helper，需確認 `label_style` 是否要改 `label_text_style`，並確認沒有依賴 `on_change` 取選擇結果（目前是 `_save` 主動讀 `.value`，**OK**，但若未來加 `on_change` 要記得用 `on_select`）。
- [terms_view.py:38](app/ui/terms_view.py#L38) — `filter_dd = ft.Dropdown(...)` 同理。

#### Checkbox

| 舊 | 新 |
|---|---|
| `Checkbox(is_error=True)` | `Checkbox(error=True)` |
| `Checkbox(label_style=...)` | **應改為 `label_text_style=`**（與 Switch 同步）|

**本專案受影響**：
- [settings_view.py:93-96](app/ui/settings_view.py#L93) — `label_style=` 須改 `label_text_style=`
- [dashboard_view.py:252](app/ui/dashboard_view.py#L252) — Action item checkbox，無 label_style 風險，但要看完整參數

#### Switch

- `Switch(label_style=...)` → `label_text_style=`（§A6 已列；本專案目前未使用 Switch）

#### Slider / Radio / DatePicker

- 本專案目前未使用 Slider、Radio、DatePicker，無受影響行號。
- 推測同類風險：屬性扁平化（`thumb_color`/`active_color` 可能搬到 `SliderTheme` 或 style 子物件），未來引入時需重查。

#### TextField

- 大致 API 穩定。`TextField(label=, value=, hint_text=, password=, multiline=, max_lines=)` 在 0.84 仍可用。
- 本專案 TextField 用法（[settings_view.py:68](app/ui/settings_view.py#L68)、[dashboard_view.py:142, 434, 439](app/ui/dashboard_view.py#L142)、[terms_view.py:32, 162-171](app/ui/terms_view.py#L32)）目前未發現破壞性參數，但建議第二輪驗證時實際測試。

### G4. GUI Smoke Test Checklist

> 給碼農修完後自測、給 Verifier 跑 V Phase 第三/四輪用。每項標 ✅/❌/⏭️。

#### S1. 啟動 + 首屏
- [ ] App 啟動無 exception
- [ ] StatusBar 顯示（Ollama 狀態 / 模型 / 詞條數 / 暫存）
- [ ] NavigationRail 四個分頁圖示顯示
- [ ] 首屏 = Dashboard idle 模式

#### S2. Dashboard idle
- [ ] 「開始錄音」按鈕渲染（含 style）
- [ ] 「匯入音檔」按鈕渲染
- [ ] 歷史紀錄列表渲染（即使為空也不能崩）
- [ ] 點「歷史紀錄」項目可進入 review 模式

#### S3. Dashboard live（兩欄 / 單欄都要測）
- [ ] 視窗寬度 1400 → 三欄佈局，無 Tab，三 panel 並排
- [ ] 視窗寬度 1000 → 兩欄佈局，右側 Tabs（label-only）切換 summary/actions
- [ ] 視窗寬度 600 → 單欄佈局，三個 Tab 切換
- [ ] Tab 切換時 content slot 正確替換
- [ ] 計時器每秒更新

#### S4. 對話框
- [ ] 「匯入音檔」→ FilePicker 開啟 → 選檔成功
- [ ] 選檔後彈出「會議資訊」對話框（title/participants 兩個 TextField）
- [ ] 點「跳過」/「開始」對話框關閉
- [ ] 進入 live → 結束會議 → 進 review 模式
- [ ] review 底部「匯出 Markdown」按鈕 → FilePicker 儲存 → 彈出「是否刪除原始音檔」對話框
- [ ] 點「刪除」確認對話框關閉

#### S5. SnackBar
- [ ] 任何錯誤訊息（`page.show_dialog(SnackBar(...))`）顯示後自動消失
- [ ] settings 儲存成功 → SnackBar 顯示「設定已儲存」

#### S6. Terms 分頁
- [ ] 切到 Terms 分頁無 exception（**這是 lifecycle 雷區**）
- [ ] 詞條列表渲染
- [ ] 搜尋 TextField 過濾
- [ ] 分類 Dropdown 過濾
- [ ] 點「新增」→ 對話框 → 5 個 TextField → 儲存
- [ ] 點「編輯」→ 對話框 → 修改 → 儲存
- [ ] 點「刪除」→ 確認對話框 → 刪除
- [ ] 「匯入 YAML」FilePicker 流程

#### S7. Feedback 分頁（**Bug #7 主戰場**）
- [ ] 切到 Feedback 分頁**無 `Control must be added to the page first`**
- [ ] 整體統計卡片渲染
- [ ] 「需要關注」區渲染
- [ ] 「最近 Session」區渲染

#### S8. Settings 分頁
- [ ] 切到 Settings 無 exception
- [ ] TextField / Dropdown / Checkbox 都渲染（**Checkbox label_style 雷**）
- [ ] 改值 → 「儲存」→ SnackBar 提示
- [ ] 「重設」→ 所有控制項回預設值（**update() 雷**）

#### S9. 響應式
- [ ] 拖動視窗寬度 → 三欄/兩欄/單欄即時切換（`on_resize` 不能寫成 `on_resized`）

---

## H. 引用來源（補）

- [Flet Discussion #705 — Control must be added to the page first](https://github.com/flet-dev/flet/discussions/705)
- [Flet Discussion #2567 — AssertionError: Control must be added to the page first](https://github.com/flet-dev/flet/discussions/2567)
- [Flet Discussion #4693 — User control assertion error](https://github.com/flet-dev/flet/discussions/4693)
- [Flet Custom Controls 文件（did_mount / will_unmount / before_update）](https://flet.dev/docs/getting-started/custom-controls/)
- [Flet FastAPI and async API improvements（async lifecycle 棄用 _async 後綴）](https://flet.dev/blog/flet-fastapi-and-async-api-improvements/)

---

## F. Researcher 結語

Bug Report 列的 4 顆雷只是 V Phase 第一輪踩到的部分。本報告盤點出**至少 28 個行號**需要碼農處理，分散在 6 個檔案。

建議施工方式：碼農按 §C 優先序開一條 fix branch，**§B1 + Dialog + SnackBar + Button 殘餘**一次處理完，再讓 Verifier 跑 V Phase 第二輪。否則每修一顆雷重跑一輪，會無限循環。

Tab 架構變動是這次最痛的點（§D 已給骨架），其他大多是參數改名/搬位置，機械式替換即可。
