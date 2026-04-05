---
title: 開發日誌 2026-04-05 — S Phase UI Review 修正（M-1 響應式佈局 + M-2 計時器）
date: 2026-04-05
type: devlog
status: active
author: 碼農
tags:
  - devlog
  - s-phase
  - ui
  - review-fix
---

# 開發日誌 — 2026-04-05 S Phase UI 修正

> 碼農修正 [[review_S_UI_20260405]] 的 2 項 Major。
> 前次日誌：[[devlog_20260405_s_phase4]]

---

## 修正項目

### M-1：響應式三段式佈局 ✅

**問題：** `dashboard_view.py` 只有固定三欄 `ft.Row`，不符合 [[ui_spec#2.3]] 定義的三段式斷點。窄螢幕/半邊螢幕場景無法使用。

**修正內容：**

新增 `_apply_responsive_layout()` 方法 + `page.on_resized` 監聽：

| 斷點 | 佈局 | 實作方式 |
|------|------|---------|
| ≥ 1400px | 三欄並排 | `ft.Row` 三個 `expand=1` Container |
| 960 ~ 1399px | 兩欄（逐字稿 + 右側分頁） | `ft.Row`（逐字稿 + `ft.Tabs`（重點/Actions）） |
| < 960px | 單欄分頁 | `ft.Tabs`（逐字稿/重點/Actions 三分頁） |

- 同時套用於 live 和 review 模式
- 透過 `_layout_container` 中間容器，resize 時只替換佈局內容，不重建面板

**涉及程式碼：**

```python
# dashboard_view.py
def _on_page_resized(self, e):
    if self._mode in ("live", "review") and self.transcript_panel:
        self._apply_responsive_layout()
        self._layout_container.update()

def _apply_responsive_layout(self):
    width = self.page.window.width
    if width >= 1400:    # 三欄
    elif width >= 960:   # 兩欄 + Tabs
    else:                # 單欄 Tabs
```

### M-2：會中計時器 ✅

**問題：** `_timer_text` 永遠顯示 "00:00:00"，無定時更新機制。

**修正內容：**

新增 `_start_timer()` / `_stop_timer()` 方法：

- `_build_live()` 結尾呼叫 `_start_timer()`
- 以 `page.run_task()` 啟動 async 定時任務，每秒計算 `datetime.now() - _recording_start` 並更新顯示
- `set_mode()` 離開 live 時自動 `_stop_timer()`
- `_timer_running` 旗標控制迴圈生命週期

**涉及程式碼：**

```python
# dashboard_view.py
def _start_timer(self):
    self._timer_running = True
    async def _update_timer():
        while self._timer_running and self._recording_start:
            elapsed = (datetime.now() - self._recording_start).total_seconds()
            self._timer_text.value = self._format_duration(elapsed)
            self._timer_text.update()
            await asyncio.sleep(1)
    self.page.run_task(_update_timer)

def _stop_timer(self):
    self._timer_running = False
```

---

## 測試結果

```
既有核心模組測試：106 passed, 21 deselected in 98.72s ✅
（UI 修改不影響核心模組邏輯）
```

---

## 未修正的 Minor 項（審察者建議可延後）

| # | 說明 | 延後原因 |
|---|------|---------|
| m-1 | 逐字稿「遺漏回報」+ 一鍵新增詞條 | UI 互動複雜，需設計右鍵選單 |
| m-2 | 設定頁「輸入裝置」選擇 | 需 sounddevice.query_devices()，可在 UI 打磨階段補 |
| m-3 | 摘要更新閃爍提示 | 純視覺增強 |
| m-4 | `_ensure_ml_modules()` 改 async | 涉及 main.py 架構調整 |
| m-5 | ConfigManager.reload() | 需更新介面 |
| m-6 | dialog 關閉後移除 overlay | 記憶體優化 |
