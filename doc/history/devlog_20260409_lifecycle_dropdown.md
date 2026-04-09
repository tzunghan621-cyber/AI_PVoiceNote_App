---
title: 開發日誌 2026-04-09 — Bug #6 + #7 + lifecycle 守衛全面修補
date: 2026-04-09
type: devlog
status: active
author: 碼農 B
tags:
  - devlog
  - hotfix
  - flet
  - lifecycle
  - v-phase
---

# 開發日誌 — 2026-04-09 lifecycle + Dropdown 全面修補

> 依研究者 [[flet_0.84_migration_20260408]] §G 補強指引，一次修完 V Phase 第三輪所有 lifecycle + constructor 雷區。
> 前次日誌：[[devlog_20260408_filepicker_api]]

---

## 修補範圍

### Bug #7 — Lifecycle（`Control must be added to the page first`）

Flet 0.84 把生命週期改嚴：`__init__()` 階段呼叫 `update()` 直接 `AssertionError`。

| 檔案 | 修法 |
|---|---|
| `feedback_view.py` | 移除 `__init__` 末尾 `self.refresh()`，改在新增的 `did_mount()` 觸發 |
| `terms_view.py` | 同上 — `__init__` → `did_mount` |

### Bug #6 — Dropdown.on_change 不支援

Flet 0.84 把 Dropdown 列表選擇事件搬到 `on_select`；`on_change` 只在 editable 輸入時觸發。

| 檔案 | 修法 |
|---|---|
| `terms_view.py:46` | `filter_dd` `on_change=self._on_filter` → `on_select=self._on_filter` |
| `settings_view.py` `_dropdown` | 無 on_change handler，無需動 |

### Checkbox `label_style` → `label_text_style`

| 檔案 | 修法 |
|---|---|
| `settings_view.py` `_checkbox` | `label_style=` → `label_text_style=` |
| `dashboard_view.py:252` Action item checkbox | 無 label_style，安全 |

### 保留決定（依研究者 §G3 「需確認」項）

- **`ft.dropdown.Option` 不改 `ft.DropdownOption`**：研究者僅標「建議」，現行 API 仍可用，最小變更原則
- **Dropdown `label_style` 不改 `label_text_style`**：研究者標「需確認」，未確認 0.84 是否改名，保守不動

---

## P1 預防性 lifecycle 守衛

依 §G2 表格，所有 helper / refresh 內的 `xxx.update()` 前加 `if self.page:` 守衛，避免 unmount/mount-前呼叫炸鍋。

| 檔案 | 函式 / 行為 |
|---|---|
| `feedback_view.py` | `refresh()` 末尾 `self._content.update()` |
| `terms_view.py` | `refresh()` 末尾 `_terms_list.update()` / `_footer.update()` |
| `settings_view.py` | `_reset()` 內 `control.update()` |
| `main_view.py` `StatusBar` | `update_ollama` / `update_term_count` / `update_temp_usage` / `set_meeting_mode` 四個 setter |
| `dashboard_view.py` `TranscriptPanel` | `append()` auto_scroll 路徑、`_scroll_to_bottom()` |
| `dashboard_view.py` `SummaryPanel` | `_on_highlights_changed()`、`update_highlights()`、`update_decisions()` |
| `dashboard_view.py` `ActionsPanel` | `_refresh_ui()` |
| `dashboard_view.py` `DashboardView` | `set_mode()` 內 `self._content.update()`、`_on_page_resized()` 內 `_layout_container.update()` |

`MainView._navigate` 已有 `self._page_ref` 守衛，無需重複。

通用模式：
```python
def some_setter(self, ...):
    self._field.value = ...
    if self.page:        # ← 守衛：mount 後才存在
        self._field.update()
```

---

## 驗證

### 自動化測試
- `pytest -m "not real_audio and not slow"`：**106 passed, 22 deselected, 1 warning**（全綠，無回歸）

### GUI Smoke Test（§G4）⚠️ 待甲方/實驗者執行
**碼農 B 無法在 sandbox 環境啟動 Flet GUI 視窗 / 截圖**。修補完成後請實驗者依 §G4 checklist 跑：

- **S1** 啟動 + 首屏無 exception
- **S2** Dashboard idle（兩按鈕 + 歷史列表）
- **S3** Dashboard live 三斷點（1400/1000/600）
- **S6** Terms 分頁（**lifecycle 雷區，本次 Bug #7 主修點之一**）
  - 切過去無 `Control must be added to the page first`
  - 分類 Dropdown 過濾運作（Bug #6 主修點）
  - 詞條列表渲染
- **S7** Feedback 分頁（**Bug #7 主戰場**）
  - 切過去無 assertion error
  - 統計卡片渲染
- **S8** Settings 分頁
  - Checkbox 渲染（label_text_style 修正點）
  - 「重設」按鈕運作

**請務必至少手點 Feedback + Terms 兩個之前炸的分頁，截圖回貼**。Bug #5 那次只跑 import smoke 漏抓的教訓不能再犯。

---

## 變更檔案總覽

| 檔案 | 變更類型 |
|---|---|
| `app/ui/feedback_view.py` | lifecycle 改 did_mount + 守衛 |
| `app/ui/terms_view.py` | lifecycle 改 did_mount + Dropdown on_select + 守衛 |
| `app/ui/settings_view.py` | Checkbox label_text_style + reset 守衛 |
| `app/ui/main_view.py` | StatusBar 四個 setter 守衛 |
| `app/ui/dashboard_view.py` | 8 處 update() 守衛（TranscriptPanel/SummaryPanel/ActionsPanel/DashboardView） |

---

## 經驗教訓

- **Flet 0.84 lifecycle 不再寬容**：舊版 `__init__` 內 `update()` 被靜默忽略，新版直接 assert。所有 `ft.Container` 子類自繪 view 必須走 `did_mount` 模式。
- **預防性守衛 >> 事後追 bug**：每個 helper 加 `if self.page:` 兩行成本，省下 V Phase 一輪驗證。
- **研究者 §G + §H 的價值**：第一輪報告漏的兩類問題在第二輪補齊後一次清光，減少多輪迭代。
- **GUI 測試自動化的缺口**：sandbox/CI 跑不起 Flet 視窗，必須靠實驗者人眼。應思考是否能跑 headless smoke（import 模組 + 構造 view 不報錯）作為 pytest 補充。

---

## 相關文件

- [[flet_0.84_migration_20260408]] §G1-G4 — 本次修補的權威依據
- [[devlog_20260408_filepicker_api]] — 前次 FilePicker 修補
- [[bug_report_flet_api_20260406]] — 原始 bug 紀錄
