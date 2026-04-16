---
title: 開發日誌 2026-04-16 — Bug #8 Checkbox label_style 修正 + NavigationRail 越界守衛
date: 2026-04-16
type: devlog
status: active
author: 碼農 B
tags:
  - devlog
  - hotfix
  - flet
  - v-phase
  - bug-8
---

# 開發日誌 — 2026-04-16 Bug #8 Checkbox + NavigationRail 越界

> 前次日誌：[[devlog_20260409_lifecycle_dropdown]]
> 對應 Bug：[[bug_report_flet_api_20260406]] Bug #8
> 依研究：[[flet_0.84_migration_20260408]] §G

---

## 修補範圍

### Bug #8 — `Checkbox.__init__() got an unexpected keyword argument 'label_text_style'`

#### 真實根因：前次 devlog 的修法方向反了

前次 [[devlog_20260409_lifecycle_dropdown]] 把 `settings_view._checkbox` 從 `label_style=` 改成 `label_text_style=`。這個方向**剛好反了**：

Flet 0.84 對 label 樣式參數命名**不一致**，各控件必須分開記：

| 控件 | label 樣式參數 |
|---|---|
| `Checkbox` | **`label_style`** ✅ |
| `Dropdown` | `label_style` ✅ |
| `Radio` | `label_style` ✅ |
| `TextField` | `label_style` ✅ |
| `Switch` | **`label_text_style`** ⚠️（獨樹一格） |
| `Slider` | 無 label_*_style |

> **踩雷點**：前次 devlog 推測「Checkbox 應該跟 Switch 一樣」，實際 0.84 只有 Switch 是 `label_text_style`，其他全部都 `label_style`。

#### 修法

[settings_view.py:95](app/ui/settings_view.py#L95)
```python
# Before（前次 devlog 改錯方向）
cb = ft.Checkbox(label=label, value=bool(val),
                 label_text_style=ft.TextStyle(color=COLOR_TEXT))

# After（本次修正，回到 label_style）
cb = ft.Checkbox(label=label, value=bool(val),
                 label_style=ft.TextStyle(color=COLOR_TEXT))
```

---

### 連帶發現：S8 點齒輪後 body 整塊變灰

#### 現象

甲方第一輪自測 S8 點右上角齒輪後，整個 body（nav_rail + content_area）變成淺灰色 placeholder，status_bar 和 title_bar 還在。**log 無任何 Traceback**（純渲染層失敗，不丟 Python 例外）。

#### 根因

[main_view.py:132](app/ui/main_view.py#L132) 齒輪 `on_click=lambda _: self._navigate(3)` 會把 `nav_rail.selected_index = 3` 設給 NavigationRail，但 `destinations` 只有 3 項（index 0~2）。

Flet 0.84 對 NavigationRail 範圍校驗變嚴格：**selected_index 超出 destinations 範圍時整個 Row body render tree 會被替換為灰色 placeholder**（舊版可能容忍）。

#### 修法

[main_view.py:198-201](app/ui/main_view.py#L198-L201)
```python
if hasattr(self, 'nav_rail'):
    self.nav_rail.selected_index = (
        index if index < len(self.nav_rail.destinations) else None
    )
```

超出 destinations 範圍時設 `None`（取消選中）而非硬塞超範圍整數。

---

### 預防性修正（一併保留在本次 commit）

本次接手時本地已有兩處非 Bug #8 但相關的預防修改，一併保留：

| 檔案:行號 | 改動 | 理由 |
|---|---|---|
| [app/main.py:103-104](app/main.py#L103-L104) | `asyncio.ensure_future(recorder.stop())` → `page.run_task(recorder.stop)` | 確保停錄音流程跑在 Flet event loop 上 |
| [app/ui/main_view.py:170-182](app/ui/main_view.py#L170-L182) | body 包進 expand Container | Flet 0.84 Column 對中間 expand 子元素高度分配變嚴格 |

---

## Constructor inspect 掃描結果（研究者建議補強）

完整 `inspect.signature(...)` 掃 0.84 真實 API：

### `ft.Checkbox.__init__`
- ✅ `label_style: Optional[TextStyle]`
- ❌ **無** `label_text_style`
- ✅ `on_change` callable
- ✅ `label_position`, `value`, `fill_color`, `check_color`, `shape`, `border_side` 等

### `ft.Dropdown.__init__`
- ✅ `label_style: Optional[TextStyle]`
- ❌ **無** `on_change`（只有 `on_select` / `on_text_change` / `on_focus` / `on_blur`）
- ✅ `options` 為 list、`border_color`, `color`, `dense`, `width` 都存在

### `ft.Switch.__init__`
- ✅ **`label_text_style`**（與 Checkbox 相反！）
- ❌ 無 `label_style`
- ✅ `on_change`
- ⚠️ 本專案目前未使用 Switch，若未來要加需留意命名雷

### `ft.Radio.__init__`
- ✅ `label_style`
- ❌ **無** `on_change`（Radio 事件由 `RadioGroup.on_change` 統一觸發）
- ✅ `label`, `value`, `fill_color`, `active_color`
- ⚠️ 本專案目前未使用 Radio

### `ft.Slider.__init__`
- ❌ 無任何 `label_*_style`（label 只是字串顯示）
- ✅ `on_change`, `on_change_start`, `on_change_end`
- ⚠️ 本專案目前未使用 Slider

### `ft.TextField.__init__`
- ✅ `label_style`、`border_color`、`color`、`dense`、`keyboard_type`
- ❌ 無 `label_text_style`

### `ft.ElevatedButton.__init__` / `ft.OutlinedButton.__init__`
- ElevatedButton：`icon`, `bgcolor`, `color`, `on_click`, `style` 全部保留
- OutlinedButton：`icon`, `on_click`, `style` 保留；**`bgcolor` / `color` 已移除**（Bug #2 前次已處理）

---

## 甲方協同自測紀錄

### 第一輪（修 Bug #8 + 預防性改動後）

| 路徑 | 結果 | 備註 |
|---|---|---|
| S1 啟動首屏 | ✅ PASS | StatusBar + NavigationRail + 錄音/匯入按鈕 |
| S6 詞條 | ❌ | 左側詞條 icon 選中，內容區未切換 |
| S7 回饋 | ✅ PASS | 回饋統計頁完整顯示 |
| S8 設定 | ❌ | body 整塊變灰，NavigationRail 消失 |

→ 依 S8 現象鎖定 `selected_index` 越界，修 [main_view.py:198-201](app/ui/main_view.py#L198-L201)。

### 第二輪（修 S8 越界後）

| 路徑 | 結果 | 備註 |
|---|---|---|
| S1 啟動首屏 | ✅ PASS | 同上 |
| S6 詞條（首次點擊） | ⚠️ 內容未切換 | 首次點擊觸發 `_ensure_ml_modules()` 同步載入 ML 模型（sentence_transformer + KnowledgeBase），阻塞 event loop 數十秒 |
| S7 回饋 | ✅ PASS | ML 已載入完，切換順暢 |
| S8 設定 | ✅ PASS | 完整顯示所有設定項（Whisper 模型、語言、Ollama 位址、模型、串流處理、App 知識庫…）**灰掉問題已消除** |
| S6 詞條（再點一次） | ✅ PASS | ML 已載入，詞條頁正常顯示「知識詞條管理」標題、搜尋框、篩選 Dropdown、共 0 筆詞條 |

甲方回報：「好了」— 四條路徑全通過。

執行人：甲方本人操作 GUI；碼農 B 背景監控 log 過濾 Error/Traceback，全程 **0 例外**。

---

## 既有 127 tests 狀態

```
127 passed, 1 skipped, 1 warning in 68.81s
```

✅ 無 regression。

---

## 已知 UX 議題（非本次 Bug #8 範圍）

### S6 首次點擊 ML 載入阻塞

`LazyTermsView.did_mount()` 同步呼叫 `_ensure_ml_modules()` 載入 sentence_transformer + whisper + KnowledgeBase，耗時數十秒，期間 Flet event loop 被阻塞，畫面凍在前一頁。

這**不是 Bug #8**（是設計層級的 UX 問題），已另行標記，建議後續處理方案：
1. App 啟動時背景預載 ML 模型，或
2. LazyTermsView 先顯示「載入中⋯」placeholder，再 `page.run_task` 非同步載入並 rebuild content

留待後續 P-S-C 循環決定，本次 commit 不處理。

---

## 本次異動檔案清單

| 檔案 | 行數 | 改動性質 |
|---|---|---|
| `app/ui/settings_view.py` | L95 | **Bug #8 主修** — `label_text_style` → `label_style` |
| `app/ui/main_view.py` | L170-182、L198-201 | **S8 灰掉修復**（selected_index 越界守衛） + body expand Container |
| `app/main.py` | L103-104 | 預防性 — `run_task(recorder.stop)` |

---

## 下一步交棒

V Phase 第三輪已知阻塞全部解除。實驗者（Verifier）可接手跑完整 S1-S9 GUI smoke test。

- ✅ S1 啟動首屏
- ✅ S6 詞條分頁
- ✅ S7 回饋分頁
- ✅ S8 設定分頁
- ⏳ S2 響應式佈局 / S3-S5 完整 Pipeline / S9 CRUD 編輯 — 實驗者繼續驗證

---

> 碼農 B 簽核：Bug #8 已修復並經甲方實機驗證通過，交棒給實驗者。
