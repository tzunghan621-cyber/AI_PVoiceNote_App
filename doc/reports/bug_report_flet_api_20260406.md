---
title: Flet 0.84.0 API Breaking Changes — Bug Report
date: 2026-04-06
updated: 2026-04-16
type: bug-report
phase: V (Verify)
agent: 實驗者（Verifier）
status: 🔴 阻塞中（Bug #13 + #14 — V Phase 第五輪實機新發現：page.run_task 回傳型別不相容 + SummaryPanel mount-before-update）
severity: high
tags: [bug, flet, api-breakage, v-phase, pipeline-lifecycle, data-loss]
---

# Flet 0.84.0 API Breaking Changes — Bug Report

> 對應驗證：[[verification_report_20260405]]
> 對應日誌：[[devlog_20260406_v_phase]]

## 摘要

V Phase 驗證期間，連續發現 **12 個** 相關問題（Flet 0.84 + 非 Flet 衍生）：
- Bug #1~#3：已修復（V Phase 第一輪）
- Bug #4 + #5：Tabs/Tab 架構重設計，commit `43932d3` 全面重構修復
- Bug #6 + #7：第二輪驗證點分頁時觸發，已修
- Bug #8：Checkbox `label_style` 誤改 + NavigationRail 越界，commit `4831d7b` 修復
- Bug #9：Pipeline 崩潰未連帶停止 recorder，UI 殭屍 — commit `b428369` 碼農 A 修 A1/A2/A3/B1/C1
- **Bug #10（新，2026-04-16 V4）**：Bug #9 B1 副作用 — 正常按「停止錄音」走 cancel 路徑，session **完全不落盤**（資料遺失，比第三輪殭屍態更糟）
- **Bug #11（新，2026-04-16 V4）**：Summarizer 首次觸發（180s）時 `processor.run()` 主迴圈被整串 `await` 住，期間不 consume 音訊 / 不產新 segment / UI 逐字稿凍結 30-90 秒
- **Bug #12（新，2026-04-16 V4）**：`audio_recorder.start()` async generator 在 `finally` 區塊 `yield` — 違反 Python 規則，造成 Bug #9 根因 D（asyncio warning）未如碼農 A 預期自動消失

**問題類型彙整：**
1. **唯讀 property 衝突** — Bug #1
2. **參數名移除 / constructor 重設計** — Bug #2/#3/#4/#5/#6/#8
3. **Lifecycle 變嚴格**（unit test 與 import smoke test 都抓不到，只有 GUI 操作才會炸）— Bug #7、Bug #14
4. **Pipeline / recorder lifecycle 解耦失誤** — Bug #9（與 Flet 0.84 無關，屬 app 邏輯層）
5. **停止流程 cancel-over-drain 設計缺陷 → 資料遺失** — Bug #10（Bug #9 修復回歸）
6. **Pipeline 架構：summarizer 與 transcribe 無背景化** — Bug #11（長期架構問題，V4 首次可觀測）
7. **async generator `finally` 內 yield** — Bug #12（違反 Python async gen 規則）
8. **page.run_task 回傳 concurrent.futures.Future（非 asyncio.Task）→ asyncio.shield 不相容** — Bug #13（研究者架構 review 漏網，V5 實機首次可觀測）

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

## Bug #6：`Dropdown(on_change=...)` 不接受 🔴

| 項目 | 內容 |
|---|---|
| 狀態 | 🔴 待修復（V Phase 第二輪發現） |
| 觸發 | 點左側「詞條」分頁 → `LazyTermsView.build()` 建構 `TermsView` |
| 檔案 | [[terms_view.py]]:38 |
| 阻塞 | #9 詞條 CRUD |

### 錯誤訊息
```
TypeError: Dropdown.__init__() got an unexpected keyword argument 'on_change'
```

### 完整 traceback
```
File "app/main.py", line 144, in build
  return TermsView(page, kb)
File "app/ui/terms_view.py", line 27, in __init__
  content = self._build()
File "app/ui/terms_view.py", line 38, in _build
  filter_dd = ft.Dropdown(
TypeError: Dropdown.__init__() got an unexpected keyword argument 'on_change'
```

### 修復方向
Flet 0.84.0 的 `Dropdown` constructor 移除 `on_change`。需檢查新 API 並改用對應的事件 hook 模式（可能類似 `on_select` 或 listener 註冊）。

---

## Bug #7：`Column(102) Control must be added to the page first` 🔴

| 項目 | 內容 |
|---|---|
| 狀態 | 🔴 待修復（V Phase 第二輪發現） |
| 觸發 | 點左側「回饋」分頁 → `LazyFeedbackView.did_mount()` 建構 `FeedbackView` → `__init__` 內呼叫 `refresh()` → `self._content.update()` |
| 檔案 | [[feedback_view.py]]:19, 35 |
| 阻塞 | #9 回饋管理（如有）、影響任何 view 的初始化模式 |

### 錯誤訊息
```
RuntimeError: Column(102) Control must be added to the page first
```

### 完整 traceback
```
File "app/main.py", line 157, in did_mount
  self.content = FeedbackView(kb, feedback_store)
File "app/ui/feedback_view.py", line 19, in __init__
  self.refresh()
File "app/ui/feedback_view.py", line 35, in refresh
  self._content.update()
File ".../flet/controls/base_control.py", line 279, in page
  raise RuntimeError(
RuntimeError: Column(102) Control must be added to the page first
```

### 根本原因（重要）

Flet 0.84.0 對 control lifecycle 變嚴格：
- **舊版**：`__init__` 階段呼叫 `.update()` 會被忽略或延遲執行
- **新版**：控件未掛載到 page tree 之前呼叫 `.update()` 會拋 RuntimeError

`FeedbackView.__init__` → `self.refresh()` → `self._content.update()` 的流程在 Flet 0.84.0 下會炸。

### 修復方向
- 把 `__init__` 裡的 `self.refresh()` 移到 `did_mount()`，或
- `refresh()` 內部判斷 `if self.page is not None: self._content.update()`，或
- 改用「只設定屬性、不呼叫 `update()`」的方式建構初始狀態，等 mount 後再 update

### ⚠️ 此類 Bug 的特殊危險性

| 偵測手段 | 是否能抓到 |
|---|---|
| 單元測試 | ❌（測邏輯，不走 Flet event loop） |
| Import smoke test | ❌（不會實際 build UI） |
| GUI 啟動到 idle 頁面 | ❌（idle 不觸發 lazy view） |
| **GUI 點過所有分頁** | ✅ |

---

## Bug #9：Pipeline 崩潰未連帶停止 recorder，UI 與 runtime state 失聯 🔴

| 項目 | 內容 |
|---|---|
| 狀態 | 🔴 待修復（2026-04-16 V Phase 第三輪甲方協同時觸發） |
| 觸發 | 點「開始錄音」→ 錄音約 3 分鐘後 Pipeline 內部拋例外 |
| 檔案 | [main.py:68-104](app/main.py#L68-L104)（主要）、[stream_processor.py](app/core/stream_processor.py)、[audio_importer.py:23](app/core/audio_importer.py#L23)（連鎖） |
| 阻塞 | #3 即時錄音、#5 完整 Pipeline、#6 即時儀表板三區塊（甲方完整流程驗證全數阻塞） |
| 類別 | **邏輯層 / 錯誤處理 / Lifecycle**（與 Flet 0.84 API 無關） |
| 指派建議 | 碼農 A（邏輯類，依本次任務分工） |

### 現象

甲方「開始錄音」後實時錄音，約 3 分鐘時觸發 pipeline 內部例外，**GUI 進入「殭屍 live 模式」**：

| 觀察 | 描述 |
|---|---|
| 錄音計時器 | 持續累加至 **08:19+** 不停 |
| 逐字稿區塊 | 仍有新 segment 進來，但時間戳 **[00:00], [00:02]... [00:08], [00:00], [00:03]...** 在某點**跳回 00** |
| 「停止錄音」按鈕 | 點擊**完全無反應** |
| SnackBar 錯誤提示 | 未顯示（或一閃而過，甲方沒看見） |
| 只能救援方式 | 強制 kill python process |

### log 證據

```
INFO:faster_whisper:Processing audio with duration 00:10.010  × 18 次（~180s = 3 分鐘）
INFO:faster_whisper:VAD filter removed ...
ERROR:__main__:Pipeline error:                                    ← 空訊息！
ERROR:asyncio:Task exception was never retrieved
future: <Task finished name='Task-6959' coro=<<async_generator_athrow without __name__>()> 
       exception=RuntimeError('async generator ignored GeneratorExit')>
RuntimeError: async generator ignored GeneratorExit
```

### 根因拆解

#### 主因 A — `_run` 與 `recorder` lifecycle 解耦

[main.py:68-75](app/main.py#L68-L75) `on_start_recording.innner._run`：
```python
async def _run():
    try:
        await processor.run(recorder.start(), session)
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        page.show_dialog(ft.SnackBar(content=ft.Text(f"處理失敗：{e}")))

page.run_task(_run)
```

- `processor.run()` 拋例外 → `_run` coroutine 結束
- **但 `recorder` 物件還活著**。`recorder.start()` 這個 async generator 若底層用 background thread 持續 capture audio，且 pipeline 不再 consume chunks，state 就掛在那
- `on_stop_recording` ([main.py:100-104](app/main.py#L100-L104)) 只呼叫 `recorder.stop()` set flag，但沒人 consume：
  ```python
  def on_stop_recording():
      nonlocal recorder
      if recorder:
          page.run_task(recorder.stop)
  ```
- dashboard 沒被切回 review/idle，UI 留在 live 態繼續展示過期資料

#### 主因 B — 錯誤訊息被 swallow

`logger.error(f"Pipeline error: {e}")`：
- 用 `str(e)` 而非 `repr(e)` / `logger.exception(...)`
- `asyncio.CancelledError` 或空訊息 exception 的 `str()` 都是 `""`
- → log 只有 `Pipeline error:` 沒下文，debug 時無從下手

#### 主因 C — 逐字稿時間戳歸零

Pipeline crash 後某路徑（可能是新的 `_run` 被觸發，或 transcriber 共享實例被 `reset()`）讓 `chunk_id` 歸零，但 recorder 持續送舊音訊進來，造成時間戳 **[00:08] 後跳 [00:00]** 的詭異現象。

#### 連鎖 D — `audio_importer.py` async gen 警告

[audio_importer.py:23](app/core/audio_importer.py#L23) 本身沒 try/except 吃 GeneratorExit，但在 pipeline 掛掉時 async gen close 過程觸發 `RuntimeError: async generator ignored GeneratorExit`。這多半是 **C 擴充層（`to_thread` 內的 whisper / pydub）長時間阻塞 + asyncio GC 時機**造成，**A+B+C 修好後應自然消失**，本 bug 不單獨處理 D。

### 修復方向建議（由碼農 A 據以實作）

| # | 位置 | 改動 |
|---|---|---|
| A1 | [main.py:68-75](app/main.py#L68-L75) `on_start_recording._run` | `except Exception as e` → `except asyncio.CancelledError: raise` + `except Exception: logger.exception(...)`；`finally` 區塊 `await recorder.stop()` |
| A2 | 同上 | SnackBar 訊息用 `type(e).__name__` 保證非空；停留時間拉長或改持久對話框 |
| A3 | [main.py:91-98](app/main.py#L91-L98) `on_import_audio._run` | 同 A1 A2 處理（匯入音檔路徑） |
| B1 | [main.py:100-104](app/main.py#L100-L104) `on_stop_recording` | 保留 `_run` task handle（`self._pipeline_task = page.run_task(_run)`）；stop 時 `_pipeline_task.cancel()` 配合 `await recorder.stop()` |
| C1 | [main.py:68-98](app/main.py#L68-L98) 兩個 `_run` | Pipeline 異常結束後 `dashboard.set_mode("idle", None)`（錄音）或 `("review", session)`（匯入已有部分資料可保留），避免 GUI 殭屍 |
| D | [audio_importer.py:23](app/core/audio_importer.py#L23) | **不改**（理論無問題，A+B+C 後警告應消失；若仍有再單獨處理） |
| E | transcriber reset 時間戳 | **不改**（Pipeline 不崩後此現象不再重現） |

### 驗證條件（碼農 A 修完後 Verifier 重測）

1. 127 fast tests 無 regression
2. 甲方「開始錄音」→ 錄 5-10 分鐘 → 期間 Pipeline 若掛：log 要有 `logger.exception` 完整 traceback、GUI 要彈可見錯誤、dashboard 回 idle、計時器停
3. 「停止錄音」按鈕在任何 pipeline state（正常/已崩潰）都能把 recorder + pipeline task 清乾淨
4. 強制 kill process 不是唯一救援

### ⚠️ 此類 Bug 的特殊危險性

| 偵測手段 | 是否能抓到 |
|---|---|
| 單元測試 | ❌（測單一函式，不跑 async lifecycle） |
| Import smoke test | ❌ |
| 自動化 GUI 啟動冒煙 | ❌（啟動不觸發 pipeline） |
| **GUI 實機跑真實錄音 3+ 分鐘** | ✅ |

→ 已再次驗證 [[#三輪結語#V Phase 第三輪結語]] 的觀察：**Flet 相關 PR 必須有實機 GUI + 真實 pipeline 時長驗證**，單元/冒煙不夠。

---

## Bug #10：正常按「停止錄音」走 cancel 路徑 → session 完全不落盤（資料遺失）🔴

| 項目 | 內容 |
|---|---|
| 狀態 | 🔴 待修復（2026-04-16 V Phase 第四輪甲方協同錄音時觸發） |
| 觸發 | 實機錄音 ~3 分多鐘 → 按「停止錄音」 |
| 檔案 | [main.py:149-157](app/main.py#L149-L157)（主要）、[main.py:84-108](app/main.py#L84-L108)（副線）、[stream_processor.py:71-88](app/core/stream_processor.py#L71-L88)（`end_recording`/`mark_ready` 沒機會跑） |
| 類別 | **邏輯層 / Pipeline lifecycle**（Bug #9 B1 修復回歸） |
| 阻塞 | #3 即時錄音、#7 會後編輯、#8 匯出（沒 session 可編輯 / 匯出） |
| 嚴重度 | 🟥 **最高** — 甲方實際使用時會錄一整場會議、按停止、資料全丟。比 Bug #9 殭屍態更糟（當時資料至少還在記憶體） |
| 指派建議 | 碼農 A（Bug #9 原修復者，架構他最熟） |

### 現象（V Phase 第四輪 T1 實機）

- 甲方按「開始錄音」→ 實錄 ~3 分 20 秒
- 按「停止錄音」→ UI 直接回 **idle**（「開始錄音 / 匯入音檔」首頁）
- 預期應進 **review 模式**（底部「匯出 Markdown」按鈕、可編輯逐字稿）
- 事後 `data/sessions/` **目錄空白** — session 完全沒落盤

### log 證據

```
INFO:faster_whisper:Processing audio with duration 00:10.010  × 20 次（~200s）
INFO:faster_whisper:VAD filter removed ...
INFO:__main__:Recording pipeline cancelled by user    ← 單獨一行，沒 ERROR / Traceback
```

伴隨 Bug #12 的 asyncio warning（見該章節）。

### 根因拆解

[main.py:149-157](app/main.py#L149-L157) `on_stop_recording`（碼農 A Bug #9 B1 的實作）：
```python
def on_stop_recording():
    nonlocal recorder, pipeline_task
    if recorder:
        page.run_task(recorder.stop)          # ① 設 _recording=False（軟停止）
    if pipeline_task is not None and not pipeline_task.done():
        pipeline_task.cancel()                 # ② 立刻 cancel（硬中斷）
```

**競態**：
1. ① `recorder.stop()` 只設 flag，需要下一次 `while self._recording` 迴圈才會真的退出。意圖是讓 `async for audio_chunk` 自然收尾 → `processor.run()` 跑到 `line 71-88` 產 final summary → `_on_pipeline_done` → `session_mgr.save`
2. ② `pipeline_task.cancel()` **立刻** 向 `_run` 拋 `CancelledError`，比 ① 的軟停止快
3. 結果：`_run` 走 `except asyncio.CancelledError: raise` → `finally` 把 UI 切回 idle，**session 從未通過 `_on_pipeline_done` 保存**

碼農 A devlog（[[devlog_20260416_builderA_bug9]]）的說明印證了這是**設計選擇**而非意外：
> 「正常錄音中按停止 → recorder 停 + pipeline_task cancel → UI 回 idle（會跳過 final summary，這是 B1 設計選擇）」

但這個設計選擇**與 spec 預期嚴重衝突**：

- [[ui_spec]] 規範：錄音結束 → review 模式（可編輯 / 回饋 / 匯出）
- [[data_schema]]#Session：session 必須有 `ready` 狀態落盤供會後審閱
- Spec 沒有任何一處說「正常停止 = 丟棄整個 session」

B1 把 `cancel()` 從「卡死安全網」誤用成「預設停止路徑」，語意翻轉。

### 修復方向建議（由碼農 A 據以實作）

#### 方案 A（推薦）— cancel 只當真安全網

```python
def on_stop_recording():
    nonlocal recorder, pipeline_task
    if recorder:
        page.run_task(recorder.stop)
    # 不要主動 cancel pipeline_task
    # 讓 processor.run() 自然走完 final summary 分支
    # _on_pipeline_done 會把 UI 切 review + save session
```

cancel 只在 **卡死偵測**（例如 N 秒後還沒進 review）時作為救命稻草，可另加一個 watchdog。

#### 方案 B（若 A 風險太高）— 非同步等 drain + timeout 後才 cancel

```python
async def on_stop_recording():
    nonlocal recorder, pipeline_task
    if recorder:
        await recorder.stop()  # 設 flag
    if pipeline_task is not None and not pipeline_task.done():
        try:
            await asyncio.wait_for(pipeline_task, timeout=60)  # 給 final summary 60s
        except asyncio.TimeoutError:
            pipeline_task.cancel()  # 真卡死才 cancel
            logger.warning("Pipeline drain timeout, forced cancel")
```

#### 附帶修改

1. `_run` 的 `finally` 區塊在 cancel 路徑下，若已有 segments，也應嘗試 save session 進 review（給個「部分資料」入口）而不是直接丟 idle
2. [main.py:155](app/main.py#L155) `page.run_task(recorder.stop)` 傳的是 **coroutine function 本體**，`run_task` 需要 coroutine **object**（應為 `recorder.stop()`）— 雖在目前 cancel 主導路徑下沒差別，改方案 A/B 後會露出來

### 驗證條件（碼農 A 修完後 Verifier 重測）

1. 112 fast tests 無 regression
2. 實機錄音 5 分鐘 + 正常按「停止」→ UI 進 review 模式（非 idle）、`data/sessions/` 有檔案、session.state == `ready`
3. 錄音中 Pipeline 真的掛 → 仍走 Bug #9 的 idle 分支（不回歸）
4. 「停止」按鈕在任何狀態都能停（不能退到殭屍 live）
5. 如採方案 B：drain timeout 內正常結束 → review；timeout → cancel → idle + SnackBar 提示

### ⚠️ 此類 Bug 的特殊危險性

| 偵測手段 | 是否能抓到 |
|---|---|
| 單元測試（asyncio fake recorder） | ❌ — 碼農 A 的 6 個新 tests **有測「cancel 走 finally 回 idle」**，但**沒比對 spec 預期行為**（該進 review）。tests 驗證 pattern 實作正確，但沒驗證語意正確 |
| Import smoke / GUI 啟動 | ❌ |
| **GUI 實機錄音 + 目視「停止後 UI 狀態」+ 檢查 `data/sessions/`** | ✅ |

→ 再次證明：碼農的單元測試若只驗證「程式碼按設計跑」而非「設計符合 spec」，可以綠燈通過同時嚴重違反 spec。Verifier 必須拿 spec 當校準尺。

---

## Bug #11：Summarizer 觸發期間 `processor.run()` 主迴圈被阻塞 → UI 逐字稿凍結 30-90s 🟠

| 項目 | 內容 |
|---|---|
| 狀態 | 🔴 待修復（2026-04-16 V Phase 第四輪甲方錄音時目擊） |
| 觸發 | 錄音超過 `summary_interval_sec`（預設 180s）+ segments 數 ≥ `summary_min_new_segments`（預設 10）→ 第一次 summarizer 觸發 |
| 檔案 | [stream_processor.py:31-69](app/core/stream_processor.py#L31-L69)（主迴圈架構） |
| 類別 | **架構 / Pipeline 背景化設計**（非 Bug #9 造成，但 V Phase 前幾輪都沒錄到 3 分鐘以上，首次目擊） |
| 嚴重度 | 🟨 中 — 不致命，但 UX 崩塌（甲方以為掛了）。若 Summarizer 超時 120s（httpx timeout），整個錄音段 120s 沒逐字稿 |
| 指派建議 | 碼農 A（架構設計） |

### 現象

甲方 V4 T1 實機：
- 錄音前 180s 正常：計時器跳、逐字稿持續新增、VAD log 連貫
- 180s 左右：**逐字稿停止新增新 segment**、**會議重點 / Action Items 全程空白**
- faster-whisper 仍 **持續** 在 log 裡 process 音訊（計時器持續跳）— 代表 recorder 還活著 chunk 還進來，只是沒人 transcribe
- 甲方等不下去按了停止 → Bug #10 觸發

### 根因（[stream_processor.py:38-69](app/core/stream_processor.py#L38-L69)）

```python
async for audio_chunk in audio_source:
    # 1. 轉錄
    new_segments = await asyncio.to_thread(
        self.transcriber.transcribe_chunk, audio_chunk, chunk_id
    )
    ...
    # 3. 檢查是否觸發週期摘要
    if (elapsed >= self.summary_interval ...):
        self._summarizing = True
        summary = await self.summarizer.generate(...)   # ← 主迴圈被整串 await 住
        ...
        self._summarizing = False
```

- 整個 `async for` 迴圈 **同一個 task** 內序列執行
- `await self.summarizer.generate(...)` 內部呼叫 `await httpx.post(Ollama)`，Ollama 在 CPU 上跑 Gemma 4 E2B 推理需 **30-90 秒**（Surface Pro 9 i7-1255U）
- 這段期間 event loop 理論上沒 block（httpx 是真 async），但 **這個 task 的主迴圈被這行 await 擋在這裡不動**
- 上游 `audio_source`（[audio_recorder.py:31](app/core/audio_recorder.py#L31) 的 async gen）因下游不 consume，卡在 `yield np.concatenate(transcribe_buffer)` 那行等
- `self._audio_queue` 會累積，但沒人 transcribe_chunk 新 segments
- UI 觀察：計時器繼續跳（由 dashboard_view 的 timer task 驅動，獨立）、VAD log 繼續（audio_callback thread）、但 `on_segment` 停止觸發

### 修復方向建議

#### 方案 A（推薦）— Summarizer 丟 background task，不 block 主迴圈

```python
async def run(self, audio_source, session):
    ...
    pending_summary_task: asyncio.Task | None = None
    async for audio_chunk in audio_source:
        ...
        if (elapsed >= self.summary_interval
                and segments_since_summary >= self.min_new_segments
                and not self._summarizing):
            if pending_summary_task is None or pending_summary_task.done():
                self._summarizing = True
                pending_summary_task = asyncio.create_task(
                    self._run_summary_async(session, ...)
                )
                last_summary_time = time.time()
                segments_since_summary = 0

async def _run_summary_async(self, session, ...):
    try:
        summary = await self.summarizer.generate(...)
        self.session_mgr.update_summary(session, summary)
        if self.on_summary:
            self.on_summary(summary)
    finally:
        self._summarizing = False
```

**關鍵**：主迴圈 fire-and-forget，transcribe 繼續跑；summarizer 跑完後 `on_summary` callback 更新 UI。

#### 方案 B（低成本 Workaround）— 改 UI 提示

目前左下 status bar 疑似沒在 summarizer 期間改狀態。至少應：
- `on_status_change("summarizing")` 觸發時 → status bar 顯示「摘要推理中...」+ spinner
- 讓甲方知道「卡住」不是掛，是在推理

方案 B 不治本（逐字稿仍凍），但至少不會讓甲方誤判。建議兩者並行，方案 A 是治本方案。

### 驗證條件

1. 實機錄音 5 分鐘（跨兩次 summarizer 觸發）→ summarizer 推理期間 **逐字稿持續新增**（不凍結）
2. `on_summary` callback 觸發時 UI 重點 / Action Items 區塊有內容
3. 若採方案 B：status bar 在 summarizer 期間顯示推理中

### ⚠️ 為什麼前三輪沒抓到

- 第一/二輪：Bug #4/#5 Tabs 在進 live 模式前就崩
- 第三輪：Bug #9 在 3 分鐘 summarizer 觸發前 pipeline 就掛（甲方後來重構回憶，當時崩潰時間點可能剛好在 180s summarizer 第一次觸發的衝擊下）
- 第四輪：Bug #9 修了，summarizer 才第一次真的被觸發 → 暴露 Bug #11

Bug #11 其實 **可能是 Bug #9 崩潰的真實近端誘因**（summarizer 阻塞 + 某個 to_thread 異常 → 整條炸）。修 Bug #11 可能連帶預防 Bug #9 再發。

---

## Bug #12：`audio_recorder.start()` async generator 在 `finally` 區塊 `yield` 🟠

| 項目 | 內容 |
|---|---|
| 狀態 | 🔴 待修復（2026-04-16 V Phase 第四輪 Monitor 捕獲，Bug #9 根因 D 未如預期消失） |
| 觸發 | `pipeline_task.cancel()` 或 `async for` 被中斷 → async gen `athrow(GeneratorExit)` 啟動 cleanup |
| 檔案 | [audio_recorder.py:51-80](app/core/audio_recorder.py#L51-L80) |
| 類別 | **Python async gen 規則違反** |
| 嚴重度 | 🟩 低 — 只是 asyncio 的 `Task exception was never retrieved` warning，不致命，但污染 log，妨礙 debug |
| 指派建議 | 碼農 A |

### 現象

Bug #9 修復後，V4 T1 甲方按「停止錄音」→ cancel path：

```
ERROR:asyncio:Task exception was never retrieved
future: <Task ... coro=<<async_generator_athrow without __name__>()> 
       exception=RuntimeError('async generator ignored GeneratorExit')>
RuntimeError: async generator ignored GeneratorExit
```

碼農 A 在 bug_report §Bug #9 連鎖 D 預測「A+B+C 修好後應自然消失」**不成立**，warning 仍出現。

### 根因（[audio_recorder.py:73-80](app/core/audio_recorder.py#L73-L80)）

```python
async def start(self) -> AsyncIterator[np.ndarray]:
    ...
    try:
        while self._recording:
            ...
            if self._buffer_duration(transcribe_buffer) >= self.transcribe_chunk_sec:
                yield np.concatenate(transcribe_buffer)
                ...
    finally:
        stream.stop()
        stream.close()
        # flush 殘餘
        if transcribe_buffer:
            yield np.concatenate(transcribe_buffer)   # ← ❌ async gen finally 內 yield
        if save_buffer:
            self._save_temp(...)
```

Python 規則（[PEP 525](https://peps.python.org/pep-0525/) + Python docs）：
> Using yield in finally blocks ... may cause unexpected behavior when the generator is closed.

具體來說：
- `GeneratorExit` 進到 generator 時，cleanup phase 的 yield 會「吃掉」`GeneratorExit`
- Python 於是拋 `RuntimeError('async generator ignored GeneratorExit')`
- 這就是 V Phase 第三/四輪一直看到的 warning

### 修復方向建議

```python
async def start(self) -> AsyncIterator[np.ndarray]:
    ...
    exit_cleanly = False
    try:
        while self._recording:
            ...
        exit_cleanly = True
    finally:
        stream.stop()
        stream.close()
        # flush 殘餘：**只在正常 while 退出才 yield**，cancel/close 時放棄殘餘
        if exit_cleanly and transcribe_buffer:
            # 仍不能在 finally yield — 改成把殘餘透過別的管道（例如 self.final_chunk 屬性）傳出
            self._final_chunk = np.concatenate(transcribe_buffer)
        if save_buffer:
            self._save_temp(np.concatenate(save_buffer), save_chunk_id)
```

或**更乾淨的重構**：不用 `finally` flush，改把 `while self._recording` 改成有 sentinel 的顯式結束迴圈，殘餘在迴圈內 yield 完才退。

```python
while True:
    if not self._recording and self._audio_queue.empty() and not transcribe_buffer:
        break
    try:
        data = await asyncio.wait_for(self._audio_queue.get(), timeout=0.5)
    except asyncio.TimeoutError:
        if not self._recording and transcribe_buffer:
            yield np.concatenate(transcribe_buffer)
            transcribe_buffer = []
            continue
        continue
    ...
```

碼農 A 自選方案。

### 驗證條件

1. 修完後實機錄音 + 停止 → log **不再** 出現 `async generator ignored GeneratorExit`
2. 殘餘音訊仍能進最後一個 segment（或接受丟棄 — spec 沒明確）

### 跟 Bug #10 的關係

Bug #10 若採方案 A（不 cancel）→ 正常路徑是 `while self._recording` 自然退 → `finally` 只做 cleanup 不 yield 就沒事。但 **真卡死 cancel 時仍會踩 Bug #12**，所以 Bug #12 獨立修才完整。

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

**第三輪結語（驗證 Bug #6 + #7 時）**：commit `43932d3` 修好了 Tabs，但點分頁時 Dropdown 與 lifecycle 又連環炸。明顯沒做基本 GUI smoke test — idle 頁面沒問題不代表所有 view 都沒問題，因為 lazy view 要等實際點到才會建構。

**強烈建議改善流程：**
1. **每次碼農 commit Flet 相關修改前，必須**：啟動 App → 點過所有左側分頁 → 觸發匯入流程 → 截圖證明
2. **派 Researcher 補做「Flet 0.84.0 Lifecycle 變動清單」**，掃出所有在 `__init__` 或 build 階段就呼叫 `update()` / `page.update()` 的位置
3. **建立 GUI smoke test 腳本**（即使是手動 checklist），列出所有需要點過的路徑

```bash
# Researcher 應補強的 grep 模式
\.update\(\)              # 找出所有 update 呼叫，特別檢查在 __init__ 內的
ft\.Dropdown\(            # Bug #6
ft\.Slider\(              # 推測類似的 constructor 變動
ft\.Switch\(              # 推測類似的 constructor 變動
ft\.Checkbox\(            # 推測類似的 constructor 變動
```

待命中，等 Bug #6 + #7 修復後繼續驗證 #2、#5~#10。

---

## V Phase 第三輪結語（2026-04-16 GUI 協同後）

Bug #1~#8 全數 Flet API / Flet 0.84 lifecycle 相關都已收斂。然而**第一次跑真實時長（5+ 分鐘）即時錄音**時，立即暴露 Bug #9 — 這是**非 Flet 層**、**應用邏輯層**的 Pipeline/Recorder lifecycle 設計缺陷。

此現象再次印證前三輪結語的主張：**Flet 相關 commit 的 GUI smoke test，必須含真實 pipeline 時長（≥5 分鐘即時錄音 + 匯入音檔完整跑完）**。單元測試與冒煙測試沒有任何一項能觸發 Bug #9。

建議：
1. 派碼農 A（邏輯類，依本次任務分工）修 Bug #9
2. 修復後 Verifier 先跑 127 fast tests，再協同甲方重跑即時錄音 5-10 分鐘
3. 一併驗證「匯入音檔」路徑的同類 lifecycle 問題（[main.py:91-98](app/main.py#L91-L98)）

---

## V Phase 第五輪結語（2026-04-16 Bug #10/#11/#12 修復後重驗）

Bug #12 實機驗證**通過** — 整輪 log 無 `async generator ignored GeneratorExit` warning，`audio_recorder.start` 的 flush 搬出 finally 有效。

Bug #10/#11 修復的**靜態層面**全部對齊 7 invariants（見 [[verification_report_20260405#9.2]]），但**實機層面**因為 Bug #13 + #14 兩個全新的 Flet 0.84 相關問題暴露而全線無法完成：

- **Bug #13**（`asyncio.shield(page.run_task result)` TypeError）：研究者架構 review 漏網 — 沒驗 Flet 0.84 下 `page.run_task` 回傳 `concurrent.futures.Future` 非 asyncio awaitable。碼農 A 的 `_stop_recording_async` 單元測試用 `asyncio.create_task` 模擬 pipeline_task 可通過，但 Flet runtime 不同
- **Bug #14**（`SummaryPanel.update_highlights` mount 前呼叫 `self.page`）：Bug #7 同類殘留，commit `43932d3` 修 FeedbackView 時沒全面掃描

**I1 + Bug #12 守住了資料** — 兩次 session 都落盤（status=ready + final summary 產生，即使是 placeholder，非資料遺失）。**但 UI 流程完全無法閉環**，甲方體感「停止按鈕沒反應 + 永遠切不到 review」。

**派工建議**：
1. **碼農 A** 修 Bug #13（方案 A 推薦：狀態輪詢取代 shield）
2. **碼農 B** 修 Bug #14 + 全面 grep `if self.page:` pattern 掃 UI lifecycle 殘留
3. **研究者** 補一份「Flet 0.84 async/lifecycle 完整映射研究」— 涵蓋 `page.run_task` 回傳型別、`self.page` property 嚴格化、所有未掃的 lifecycle pattern。避免第六輪再出新 bug
4. 三者修完後 Verifier V Phase 第六輪實機 T1-T6 + S2/S4/S5/S9

**環境觀察（非 bug，甲方側）**：第五輪兩次 session segments 都為空，源自甲方 Surface Pro 9 內建麥克風實際錄音振幅極低（`data/temp/chunk_0000.wav` 分析顯示 peak -52 dBFS，正常說話應 -20 ~ -10 dBFS）。VAD 全過濾是此環境訊號的合理行為。甲方需檢查 Windows 麥克風增益 / 預設 input device / 權限，才能驗 pipeline 產 segments 的路徑。**不阻塞 Bug #13/#14 修復**（修好 UI lifecycle 即可先驗 I2/I3/I5/I6 閉環；segments 真空時的 I2 退化到「final summary = placeholder ready」也可再議是否該進 aborted）。