---
title: 開發日誌 2026-04-08 — 修復 Flet 0.84.0 FilePicker API breaking change
date: 2026-04-08
type: devlog
status: active
author: 碼農
tags:
  - devlog
  - hotfix
  - flet
  - api-breaking
  - v-phase
---

# 開發日誌 — 2026-04-08 FilePicker API 修復

> 實驗者 V Phase 發現 Bug #3：Flet 0.84.0 之 `FilePicker.__init__()` 不再接受 `on_result` 參數，阻塞驗證 #4-#9。
> 前次日誌：[[devlog_20260407_default_e2b]]

---

## Bug 描述

升級至 Flet 0.84.0 後，舊式 FilePicker 寫法全部炸裂：

```python
# ❌ 舊（Flet < 0.84）
def on_result(result: ft.FilePickerResultEvent):
    if result.files:
        path = result.files[0].path
        ...

picker = ft.FilePicker(on_result=on_result)
self._page_ref.overlay.append(picker)
self._page_ref.update()
picker.pick_files(dialog_title="...", allowed_extensions=[...])
```

錯誤訊息：`FilePicker.__init__() got an unexpected keyword argument 'on_result'`

---

## Flet 0.84.0 新 API

| 變更 | 舊 | 新 |
|---|---|---|
| `FilePicker(on_result=...)` | callback 透過建構參數注入 | ❌ 移除，建構式不接受 `on_result` |
| `picker.pick_files(...)` | 觸發後 callback 收 `FilePickerResultEvent` | ✅ async，**直接回傳 `list[FilePickerFile]`** |
| `picker.save_file(...)` | 同上 | ✅ async，**直接回傳 `Optional[str]`** |
| `page.overlay.append(picker)` | 必須先掛上 overlay 才能呼叫 | ❌ 不需要 |

新寫法：

```python
# ✅ 新（Flet ≥ 0.84）
async def _handle_import_audio(self, e):
    picker = ft.FilePicker()
    files = await picker.pick_files(
        dialog_title="選擇音檔",
        allowed_extensions=["wav", "mp3", "m4a"],
    )
    if files:
        path = files[0].path
        ...
```

連帶影響：原 `_handle_*` 同步事件 handler 必須改為 `async def`，Flet 支援 async event handler 直接 await。

---

## 變更清單

| 檔案 | 函式 | 變更 |
|---|---|---|
| `app/ui/dashboard_view.py` | `_handle_import_audio` | 改 async + 直接 await `pick_files()` |
| `app/ui/dashboard_view.py` | `_handle_export` | 改 async + 直接 await `save_file()` |
| `app/ui/terms_view.py` | `_on_import` | 改 async + 直接 await `pick_files()` |

移除：所有 `on_result` 巢狀 callback、`overlay.append(picker)`、`page.update()` 預掛邏輯。

---

## 驗證

- `pytest -q`：**127 passed, 1 warning**（全綠，無回歸）
- IDE 診斷：僅剩既有的 `未存取 "e"` Hint（Flet event handler 簽名強制要求，與本修正無關）
- 解除阻塞：實驗者可繼續執行 V Phase 驗證 #4-#9

---

## 經驗教訓

- **Flet 升級必看 changelog**：0.84 是 breaking release，FilePicker 全面 async 化
- **callback → async/await** 是整個 Flet 0.84 的方向，未來新增 file/path 操作直接走 async
- 本次未動 picker 之外的程式碼，最小變更原則

---

## 相關文件

- [[devlog_20260407_default_e2b]] — 前次日誌
- [[ui_spec]] — 匯入/匯出操作規格
- Flet 0.84 release notes（甲方環境實測來源）
