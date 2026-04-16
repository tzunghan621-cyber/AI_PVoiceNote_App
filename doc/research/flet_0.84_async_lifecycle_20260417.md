---
title: Flet 0.84 Async/Task 與 Lifecycle 完整映射 — Bug #13/#14 修復指引
date: 2026-04-17
type: research
status: complete
author: 研究者（Researcher）
tags:
  - research
  - flet
  - async
  - lifecycle
  - bug-13
  - bug-14
  - v-phase
related:
  - "[[flet_0.84_migration_20260408]]"
  - "[[pipeline_lifecycle_architecture_20260416]]"
  - "[[bug_report_flet_api_20260406]]"
  - "[[devlog_20260416_verifier_vphase5]]"
  - "[[vphase5_raw_round2]]"
---

# Flet 0.84 Async/Task 與 Lifecycle 完整映射 — Bug #13/#14 修復指引

> **補強第三篇**。前兩份（[[flet_0.84_migration_20260408]] 含 §G、[[pipeline_lifecycle_architecture_20260416]]）漏掉兩個面向：Flet runtime 的 task 型別相容性（Bug #13）、`self.page` property 嚴格化的完整影響範圍（Bug #14）。本報告補完並給碼農 A/B 修復條件（不寫 code）。
>
> **方法**：所有結論都以 `pip show flet` 證實版本 = 0.84.0 的實測為準（`inspect` 套件源、小 demo probe）。**不確定的地方明確標註**。

---

## §1 `page.run_task` 回傳型別與 await 模式

### 1.1 實測：回傳型別

直接 `inspect` Flet 0.84 的 `Page.run_task` 原始碼（`flet/controls/page.py` L718~L750）：

```python
def run_task(
    self,
    handler: Callable[InputT, Awaitable[RetT]],
    *args, **kwargs,
) -> Future[RetT]:                                 # ← concurrent.futures.Future
    _context_page.set(self)
    if not inspect.iscoroutinefunction(handler):
        raise TypeError("handler must be a coroutine function")

    future = asyncio.run_coroutine_threadsafe(     # ← 跨 thread bridge
        handler(*args, **kwargs),
        self.session.connection.loop,              # ← Flet 的 session loop
    )

    def _on_completion(f):
        try:
            exception = f.exception()
            if exception:
                raise exception                    # ← 未處理 ex 會從這裡 surface
        except CancelledError:
            pass

    future.add_done_callback(_on_completion)
    return future
```

**結論**：
- **回傳型別**：`concurrent.futures.Future`（不是 `asyncio.Task`，也不是 `asyncio.Future`）
- **型別簽名**：`Callable -> concurrent.futures._base.Future[RetT]`
- **內部機制**：`asyncio.run_coroutine_threadsafe(coro, loop)` — 跨 thread 把 coroutine 丟到 Flet session 的 event loop 跑，同步回傳 cf.Future 做 bridge
- **入參限制**：必須是 **coroutine function**（未呼叫的 `async def`），不是 coroutine object。傳 `recorder.stop()`（已呼叫）會 `TypeError: handler must be a coroutine function`。傳 `recorder.stop`（函式本身）才對。
- **已 done 的 exception 處理**：`_on_completion` 的 done_callback 會 re-raise 任何未處理的 exception，出現在 `ERROR:concurrent.futures:exception calling callback for ...` 這條 log 路徑（這正是 Bug #13 在 V5 raw log L68 的來源）。

### 1.2 實測：`concurrent.futures.Future` 的 await/shield/wait_for 相容性

Python probe 結果（`python -c "import asyncio, concurrent.futures; ..."`）：

| 操作 | 結果 | 說明 |
|---|---|---|
| `cf_future.__await__` 存在？ | **否** | `concurrent.futures.Future` 沒有 `__await__`，**不能 `await` 它** |
| `await cf_future` | TypeError | `object Future can't be used in 'await' expression` |
| `asyncio.shield(cf_future)` | **TypeError** | `An asyncio.Future, a coroutine or an awaitable is required`（Bug #13 現場）|
| `asyncio.wait_for(cf_future)` | **TypeError** | 同上 |
| `asyncio.gather(cf_future)` | **TypeError** | 同上（gather 內部也走 `_ensure_future`）|
| `asyncio.ensure_future(cf_future)` | **TypeError** | 同上 |
| **`asyncio.wrap_future(cf_future)`** | **✅ 回傳 `asyncio.Future`** | 這是唯一官方 bridge — `asyncio/futures.py` 就是為此設計 |
| `asyncio.wrap_future(cf_future)` 後再 `shield/wait_for/await` | ✅ | 變成 asyncio 原生 awaitable |
| `cf_future.result()` / `.done()` / `.cancel()` / `.exception()` | ✅ | 同步 polling API 可用 |

**關鍵**：`asyncio.wrap_future(future)` 是官方的 bridge，把 `concurrent.futures.Future` 綁到當前 running loop、產出 `asyncio.Future`，之後就能 shield/wait_for/await。

### 1.3 `cf_future.cancel()` 行為 — 重要細節

**純 `concurrent.futures.Future.cancel()`** 的規則：只在 `PENDING` 狀態下生效，`RUNNING` 狀態下 `cancel()` 回傳 `False` 且不做任何事。

**但 `asyncio.run_coroutine_threadsafe()` 回傳的 cf.Future 是特化版**：它的 `cancel()` 會透過 `call_soon_threadsafe` 呼叫底層 asyncio task 的 `cancel()`，**即使 task 已在執行仍可 cancel**（會在 task 下一個 await 點拋 `CancelledError`）。這正是 V5 現場依賴的語意。

**對碼農的含義**：`pipeline_task.cancel()` 本身沒壞，是 `asyncio.shield/wait_for(pipeline_task)` 壞（因為它們在 `cancel()` 之前就要先把 cf.Future 變成 asyncio-awaitable，而這步會 TypeError）。

### 1.4 await 模式對照表（給碼農的 cheatsheet）

| 目的 | 對 `asyncio.Task` | 對 `page.run_task(...)` 的 cf.Future |
|---|---|---|
| 等它完成 | `await task` | `await asyncio.wrap_future(task)` |
| 超時 + 不取消 | `await asyncio.wait_for(asyncio.shield(task), T)` | `await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(task)), T)` |
| 超時到直接取消 | `await asyncio.wait_for(task, T)` | `await asyncio.wait_for(asyncio.wrap_future(task), T)`<br>或：先 `asyncio.wait_for(asyncio.shield(...))`，catch TimeoutError 後 `task.cancel()` |
| 查完成狀態 | `task.done()` | `task.done()`（同名 API） |
| 取消 | `task.cancel()` | `task.cancel()`（同名 API，語意同 Flet `run_task` 特化）|
| 拿結果 | `await task` / `task.result()` | `task.result(timeout=...)`（阻塞，**不要**在 event loop 裡用）或 `await asyncio.wrap_future(task)` |
| polling 等（無 bridge） | `while not task.done(): await asyncio.sleep(0.2)` | 同（`done()` 同名 API）|

### 1.5 不確定的地方

- **`asyncio.wrap_future` 在「caller 是 Flet task 本身」時的 cancellation 傳播**：原理上 wrap_future 會把 cf.Future 的 cancellation 雙向 propagate，但我沒實測「shield 包 wrap_future」遇到外層 `_stop_recording_async` 本身被 cancel 時的行為是否完全符合預期。**碼農若採 wrap_future 方案，建議寫整合測試：假裝 outer task 被 cancel 看內層 pipeline_task 是否被保護（shield 語意）**。
- **`cf_future.result(timeout=...)` 是 blocking call**：在 event loop thread 用會卡死整個 UI loop；只能在 Flet `run_thread` 裡用。碼農不要走這條路。

---

## §2 Async event callback 支援度 + 推薦 pattern

### 2.1 實測：Flet 0.84 原生支援 async on_click

`flet/controls/base_control.py` L445~L460 的 event dispatch：

```python
event_handler = getattr(self, field_name)
if inspect.iscoroutinefunction(event_handler):
    if get_param_count(event_handler) == 0:
        await event_handler()
    else:
        await event_handler(e)
elif inspect.isasyncgenfunction(event_handler):
    ...
elif inspect.isgeneratorfunction(event_handler):
    ...
```

**結論**：Flet 0.84 的事件派發**直接 `await` async callback**。以下寫法全部合法：

```python
# 直接 async callback
ft.ElevatedButton("停止", on_click=self._stop_async)
async def _stop_async(self, e): ...

# 零參 async callback
ft.ElevatedButton("停止", on_click=async_fn_zero_arg)
async def async_fn_zero_arg(): ...

# 同時支援 param_count=0 和 1
```

參考本專案已有案例：[dashboard_view.py:478](app/ui/dashboard_view.py#L478) `async def _handle_import_audio(self, e):` 就是原生 async callback + `on_click=self._handle_import_audio`，實機驗過會動。

### 2.2 當前 `on_stop_recording` 的評語

[main.py:205-207](app/main.py#L205-L207)：

```python
def on_stop_recording():
    page.run_task(_stop_recording_async)
```

注釋寫「Flet 回呼為同步」—— **這個註解過時了**。Flet 0.84 支援 async 回呼。但這段 code 本身沒壞，因為 `_stop_recording_async` 本來就被當 coroutine function 丟進 `page.run_task` 跑（`iscoroutinefunction` 檢查通過）。

**但呼叫鏈的頂層** [dashboard_view.py:555-557](app/ui/dashboard_view.py#L555-L557) `_handle_stop` 是同步的 `on_click` handler，它 call `self._on_stop_recording()`（= main.py 的 `on_stop_recording`）。這條鏈可以改成 all-async，但不是 Bug #13 必要條件。

### 2.3 推薦 pattern（給碼農 A 修 Bug #13 時選擇）

**選項 1（最小改動）**：保留目前「同步 button handler → `page.run_task` 包一層 async」的結構，只修 `_stop_recording_async` 內部的 shield/wait_for 對 cf.Future 的相容性。

**選項 2（語意更清楚）**：整條鏈改 all-async
- `dashboard_view._handle_stop` 改 `async def _handle_stop(self, e): if self._on_stop_recording: await self._on_stop_recording()`
- `main.py on_stop_recording` 改 `async def on_stop_recording(): await _stop_recording_async()`
- Flet 會自動 await 這條 async 鏈

**研究者建議選項 1**。理由：Bug #13 的修復應只觸碰 cf.Future 相容性問題（最窄 scope），不把「整條 async 化」這種設計改動綁進 bug fix。選項 2 屬優化，可獨立 PR。

---

## §3 `self.page` lifecycle 映射表

### 3.1 實測：`BaseControl.page` property 的行為

`flet/controls/base_control.py` L265~L280 原始碼：

```python
@property
def page(self) -> "Union[Page, BasePage]":
    parent = self
    while parent:
        if isinstance(parent, Page):
            return parent
        parent = parent.parent
    raise RuntimeError(
        f"{self.__class__.__qualname__}({self._i}) "
        "Control must be added to the page first"
    )
```

**實測結果**（未 mount 的控件 `if self.page:` 會發生什麼）：

```python
class Probe(ft.Container):
    def __init__(self):
        super().__init__(content=ft.Text('hi'))

p = Probe()
if p.page:       # ← 直接 RuntimeError，不是 falsy
    ...
# RuntimeError: Probe(4) Control must be added to the page first
```

### 3.2 self.page 狀態映射表（全覆蓋）

| 階段 | `self.page` 表現 | 可否呼叫 `control.update()` | 是否安全存取 `self._page_ref`（本專案自訂 attr） |
|---|---|---|---|
| `__init__()` 執行中（尚未 `super().__init__` / 尚未被 `page.add` / 尚未當任何 control 的 content） | ❌ `RuntimeError` | ❌ `RuntimeError`（`update` 內讀 `self.page`） | ✅（但 constructor 內本來就不該 update） |
| 控件建立後、尚未加入任何父 control / page | ❌ `RuntimeError` | ❌ | ✅（若 ctor 已 `self._page_ref = page`） |
| 賦給父的 `content=` 後、父尚未被 `page.add` | ❌ `RuntimeError` | ❌ | ✅ |
| `page.add(ctrl)` 之後、`did_mount()` 尚未呼叫（極短窗口，不保證存在） | ⚠️ 灰色區（Flet 內部 mount 流程）— **不要依賴** | ⚠️ 可能行可能不行 | ✅ |
| `did_mount()` 已呼叫 | ✅ 回傳 Page | ✅ | ✅ |
| 事件 callback 觸發（`on_click` / `on_change` / `on_resize` 等） | ✅（事件派發前 `base_control.py` L448 會先 `if not self.page: raise`，**事件能派到**本身就保證 mounted） | ✅ | ✅ |
| `page.run_task` 裡的 background task（不論 `async def`） | ✅ 若 task 在 mount 期間起跑；⚠️ 若 task 持有 weak/long-lived ref 到某個 control，且該 control 後來被 unmount → 此時 `self.page` 又變 RuntimeError | ⚠️ 視 control mount 狀態而定 | ✅ |
| 定時器 task（如 `_update_timer`） | 同上 — 必須自己檢查 | 同上 | ✅ |
| `will_unmount()` 呼叫時 | ✅（仍 mounted，但即將脫離）— 可在此 dispose | ✅ | ✅ |
| `will_unmount()` 之後、parent 被切換後 | ❌ `RuntimeError`（已脫離 page tree） | ❌ | ✅（但更新也沒意義）|
| `before_update()` 內 | ✅（mount 後才會被呼叫） | ❌ **禁止**（會無限遞迴）—— docstring 明示 | ✅ |
| `build()` 內（Flet 0.84 的 build hook） | ✅ —— 官方 docstring 明示「page property is available」 | ⚠️ 建議改 data，不要 self-update | ✅ |

### 3.3 核心危險：`if self.page:` 守衛是**假守衛**

**本專案 `self.page` 守衛**（至 2026-04-17 盤點結果）：

| 檔案:行號 | context | 觸發時機 | 目前守衛寫法 | 危險？|
|---|---|---|---|---|
| [dashboard_view.py:102](app/ui/dashboard_view.py#L102) | `TranscriptPanel.append` | UI callback + 背景 pipeline task 都會呼 | `if self._auto_scroll and self.page:` | 🔴 mount 前（`_build_live` 剛建完未 add）若走到會炸 |
| [dashboard_view.py:124](app/ui/dashboard_view.py#L124) | `TranscriptPanel._scroll_to_bottom` | 按鈕 callback | `if self.page:` | 🟡 事件觸發時已 mount，低風險；但若外部 code 在 mount 前呼仍會炸 |
| [dashboard_view.py:171](app/ui/dashboard_view.py#L171) | `SummaryPanel._on_highlights_changed` | TextField on_change | `if self.page:` | 🟡 事件觸發必 mount |
| [dashboard_view.py:178](app/ui/dashboard_view.py#L178) | `SummaryPanel.update_highlights` | `_build_review` **剛 new 就呼**（L571）| `if self.page:` | **🔴 Bug #14 現場** |
| [dashboard_view.py:188](app/ui/dashboard_view.py#L188) | `SummaryPanel.update_decisions` | `_build_review` 同上（L572） | `if self.page:` | **🔴 Bug #14 同類殘留** |
| [dashboard_view.py:253](app/ui/dashboard_view.py#L253) | `ActionsPanel._refresh_ui` | `set_items` 由 `_build_review` L573 呼 | `if self.page:` | **🔴 Bug #14 同類殘留** |
| [dashboard_view.py:378](app/ui/dashboard_view.py#L378) | `DashboardView.set_mode` | main.py `_on_pipeline_done` / `_finalize_ui` | `if self.page:` | 🟢 DashboardView 本身在 app 建立時就 mount，事件觸發時必 mount |
| [dashboard_view.py:638](app/ui/dashboard_view.py#L638) | `DashboardView._on_page_resized` | page.on_resize 事件 | `if self.page:` | 🟢 事件觸發必 mount |
| [dashboard_view.py:643](app/ui/dashboard_view.py#L643) | `DashboardView._apply_responsive_layout` | `_build_live` / `_build_review` / `_on_page_resized` 都呼 | `if self.page and self._page_ref.window else 1400` | 🟡 首次 `_build_live` 時 DashboardView 已 mount、但層疊讀 `_page_ref.window` 若 mount 前會讀到 None —— 目前有 `else 1400` fallback，OK |
| [feedback_view.py:39](app/ui/feedback_view.py#L39) | `FeedbackView.refresh` | `did_mount` 呼叫（Bug #7 修過） | `if self.page:` | 🟢 `did_mount` 時必 mount（除非 feedback_view 被 unmount 後還有其他路徑 call refresh，目前沒有）|
| [terms_view.py:106](app/ui/terms_view.py#L106) | `TermsView.refresh` | `did_mount` + 事件 on_click / on_change | `if self.page:` | 🟢 同上；但注意 `_on_import` (L151 async) 結束後 `self.refresh()` 若 view 已切換到別分頁可能 unmount → 🟡 |
| [settings_view.py:116](app/ui/settings_view.py#L116) | `SettingsView._save` | 按鈕事件 | `if hasattr(self, 'page') and self.page:` | 🟡 `hasattr(self, 'page')` 永遠 True（property 存在），守衛形同虛設；但事件觸發必 mount 所以實際 OK |
| [settings_view.py:130](app/ui/settings_view.py#L130) | `SettingsView._reset` loop 內 | 按鈕事件 | `if self.page:` | 🟢 事件必 mount |
| [main_view.py:64,69,80,89](app/ui/main_view.py#L64) | `StatusBar` 四個 update_* | `main.py` 各種路徑（含 `_ensure_ml_modules` async load、`_show_pipeline_error`）| `if self.page:` | 🟢 StatusBar 被 `page.add` 於 MainView.build，在 callback 時必 mount |

**🔴 三個高危殘留**：`SummaryPanel.update_highlights` / `update_decisions` / `ActionsPanel._refresh_ui`，全在 [dashboard_view.py:561-573](app/ui/dashboard_view.py#L561-L573) `_build_review` 內建完 new panel 就立刻呼叫。

### 3.4 為什麼「事件觸發必 mount」是安全假設

`base_control.py` L440~L450 event dispatcher 的前置檢查：

```python
if not self.page:
    raise RuntimeError(
        "Control must be added to a page before triggering events. ..."
    )
```

**反證**：若 control 未 mount，事件**根本派不到**（Flet 會在 dispatcher 層直接 raise）。所以任何 `on_click` / `on_change` / `on_resize` callback 的 body 內，`self.page` 一定已 mount。**但 control 方法被程式碼**（非事件）**直接 call** 時沒有這個保護 —— Bug #14 就是這條路徑。

### 3.5 正確的 Lifecycle-Aware 守衛 pattern（給碼農 B）

**Pattern A（推薦，最清晰）—— 自己追蹤 mount 狀態**：

```python
class LifecycleAwarePanel(ft.Container):
    def __init__(self, ...):
        super().__init__(...)
        self._mounted = False

    def did_mount(self):
        self._mounted = True

    def will_unmount(self):
        self._mounted = False

    def _safe_update(self, ctrl=None):
        if self._mounted:
            (ctrl or self).update()
```

優點：`self._mounted` 存取絕不 raise；語意明確；will_unmount 後可立即擋下後續 callback。

**Pattern B（最省改動）—— try/except on self.page**：

```python
def update_highlights(self, text):
    if not self._user_edited_highlights:
        self._highlights_field.value = text
        self._highlights_field.color = COLOR_AI_DIM
        try:
            _ = self.page
            self._highlights_field.update()
        except RuntimeError:
            # 未 mount — 先改 state，等 did_mount 後自己會 render 出新 value
            pass
```

缺點：每次 probe 都要 try/except；但改動最小，可逐點套用。

**Pattern C（不推薦）—— 改架構讓 update 不在 pre-mount 路徑發生**：
- 把「pre-mount 填資料」改成「先改 state，mount 後 did_mount 一次性 render」
- 例如 `_build_review` 只建 panel + 賦初值到 `panel._highlights_field.value`，**不** call `update_highlights()`；等 panel 掛上去 `did_mount` 時一次 render

缺點：設計改動較大；優點：根除問題不用守衛。

**研究者建議**：碼農 B 主修時用 **Pattern A**（mount flag + safe_update helper），把三個現有的 panel（TranscriptPanel / SummaryPanel / ActionsPanel）統一改造。Pattern B 當 fallback 用於非 panel 的散點（如 `SettingsView` 裡的 hasattr+self.page 守衛改寫）。

### 3.6 不確定的地方

- **`did_mount` 呼叫時 `self._page_ref` 是否已等同於 `self.page`**：本專案多處用 `self._page_ref`（app-level 傳入）做 page 操作（show_dialog / pop_dialog / run_task），這繞過了 `self.page` property，**一直能用**（因為是普通 attribute 不經 descriptor）。但在 `did_mount` 之後，Flet 實際 mount 到的 page 可能不是建構當下傳入的那個 page（理論上邊界情況 — 多 page 應用）。本專案單 page，不受影響；但若未來擴成多 window/多 page 架構，要重新驗。
- **非事件來源的背景 task 在 unmount 後仍 hold 控件 ref**：可能造成 use-after-unmount。本專案的 `_update_timer` task 在 `_stop_timer` 設 `_timer_running = False` 後會退出，安全；但要人工檢查所有 `page.run_task` 啟的 task。

---

## §4 本專案受影響位置清單

### 4.1 Async/Task 層（對應 Bug #13）

| # | 檔案:行號 | 現況 | 風險 | 建議 pattern |
|---|---|---|---|---|
| 1 | [main.py:137](app/main.py#L137) | `pipeline_task = page.run_task(_run)` 存 cf.Future，nonlocal 型別 annotation 錯寫 `asyncio.Task` | 型別 annotation 誤導碼農；實際 cf.Future | 把 annotation 改 `concurrent.futures.Future` 或去掉 `asyncio.` 前綴 |
| 2 | [main.py:172](app/main.py#L172) | 同上（匯入路徑） | 同上 | 同上 |
| 3 | [main.py:174-203](app/main.py#L174-L203) `_stop_recording_async` 整段 | L187 `task.done()` OK、L188 type check OK、**L191 `asyncio.wait_for(asyncio.shield(task), ...)` 對 cf.Future TypeError** | 🔴 Bug #13 現場 | 見 §5 修復指引 |
| 4 | [main.py:197-201](app/main.py#L197-L201) cancel 後的 `await task` | `await task` 對 cf.Future 亦 TypeError；目前被 `except (asyncio.CancelledError, Exception): pass` 吞掉，行為上是「broken but silent」 | 🟡 不會 surface 但語意錯 | 改 `await asyncio.wrap_future(task)` 或改輪詢 |
| 5 | [main.py:207](app/main.py#L207) `page.run_task(_stop_recording_async)` | 回傳 cf.Future 沒存，fire-and-forget | 🟡 若 stop 函式 raise，只會在 `_on_completion` 噴 ERROR log，無法 catch；**V5 Bug #13 就是從這條路 surface** | OK（fire-and-forget 語意正確），但要確保 `_stop_recording_async` 內部完全 try/except safe |
| 6 | [dashboard_view.py:713](app/ui/dashboard_view.py#L713) `self._page_ref.run_task(_update_timer)` | 回傳 cf.Future fire-and-forget | 🟢 內部 async fn 已 try/except（break on update fail） | OK |
| 7 | [stream_processor.py:75-76](app/core/stream_processor.py#L75-L76) `asyncio.wait_for(asyncio.shield(task), ...)` 其中 `task = self._summary_task` | `_summary_task` 是 `asyncio.create_task()` 產物（L124），**真正的 asyncio.Task** | 🟢 相容 | 不動（保留） |
| 8 | [stream_processor.py:124](app/core/stream_processor.py#L124) `asyncio.create_task(...)` | 主迴圈內（已 in event loop），產 asyncio.Task | 🟢 | 不動 |
| 9 | [stream_processor.py:162](app/core/stream_processor.py#L162) `asyncio.wait_for(self.summarizer.generate(...), ...)` | generate 回 coroutine | 🟢 coroutine 是 awaitable | 不動 |
| 10 | [audio_recorder.py:54](app/core/audio_recorder.py#L54) `asyncio.wait_for(self._audio_queue.get(), ...)` | pure asyncio | 🟢 | 不動 |

**要點**：Bug #13 的修復範圍**只有 main.py 一個檔**。`stream_processor.py` 的 shield 正確（因為那個 task 是 create_task 產的）。碼農 A 不要誤動 stream_processor。

### 4.2 Lifecycle 層（對應 Bug #14）

#### A. 🔴 高危（`_build_review` pre-mount 呼叫路徑）

| # | 檔案:行號 | 呼叫鏈 | 目前寫法 | 建議 |
|---|---|---|---|---|
| A1 | [dashboard_view.py:571](app/ui/dashboard_view.py#L571) | `_build_review` → `SummaryPanel.update_highlights` | `if self.page:` → 炸 | Pattern A：SummaryPanel 加 `_mounted` flag；或 Pattern C：`_build_review` 改成先賦值 `_highlights_field.value` 不 call update_highlights |
| A2 | [dashboard_view.py:572](app/ui/dashboard_view.py#L572) | `_build_review` → `SummaryPanel.update_decisions` | 同上 L188 | 同 A1 |
| A3 | [dashboard_view.py:573](app/ui/dashboard_view.py#L573) | `_build_review` → `ActionsPanel.set_items` → `_refresh_ui` L253 | 同上 | 同 A1 |
| A4 | [dashboard_view.py:568-569](app/ui/dashboard_view.py#L568-L569) | `_build_review` for-loop 呼 `TranscriptPanel.append` → L102 `if self._auto_scroll and self.page:` | 🔴 同類 | Pattern A：TranscriptPanel 加 `_mounted` flag；`append` 改 `_safe_update` |

#### B. 🟡 中危（邏輯上事件觸發必 mount，但若未來 code path 改動容易爆同類）

| # | 檔案:行號 | 改法 |
|---|---|---|
| B1 | [dashboard_view.py:124](app/ui/dashboard_view.py#L124) TranscriptPanel._scroll_to_bottom | 併 Pattern A 改造 |
| B2 | [dashboard_view.py:171](app/ui/dashboard_view.py#L171) SummaryPanel._on_highlights_changed | 併 A1 改 |
| B3 | [terms_view.py:106](app/ui/terms_view.py#L106) TermsView.refresh | 併 Pattern A；特別注意 `_on_import` 的 async 路徑結束後 view 可能已切走 |
| B4 | [settings_view.py:116](app/ui/settings_view.py#L116) `hasattr(self, 'page') and self.page` | Pattern A 或至少改 try/except；hasattr 對 property 永遠 True，守衛形同虛設 |

#### C. 🟢 低危（目前行為 OK，但為一致性可順手改）

| # | 檔案:行號 | 備註 |
|---|---|---|
| C1 | [dashboard_view.py:378](app/ui/dashboard_view.py#L378) `set_mode` 的 `if self.page:` | DashboardView 本身在 app 建立時就 mount，事件呼叫時必 mount。**但**：set_mode 也被 `_on_pipeline_done` 從 `page.run_task` 啟動的 background task 呼叫 — 此時 DashboardView 仍 mount（沒有卸載路徑），OK。為一致性建議用 `_mounted` flag |
| C2 | [dashboard_view.py:638](app/ui/dashboard_view.py#L638) `_on_page_resized` | 事件必 mount，OK |
| C3 | [feedback_view.py:39](app/ui/feedback_view.py#L39) `FeedbackView.refresh` | `did_mount` 呼叫時必 mount；但 Bug #7 修法是預設只從 `did_mount` 走，目前 OK |
| C4 | [main_view.py:64-89](app/ui/main_view.py#L64-L89) StatusBar.update_* | 被 main.py 從 background task 呼叫，StatusBar 一直 mount，OK |

### 4.3 不在這次掃描範圍的殘留風險

- **任何未來新增 panel 重演 Pattern A1~A3 陷阱**：研究者建議把 mount-flag pattern 寫進 CLAUDE.md 的 UI 寫作規範，避免未來同類爆發（送大統領決定是否入 spec）。
- **`page.run_task` 啟的 task 裡對 control update**：timer / pipeline_task 末尾的 UI 轉場。目前 timer 以 `_timer_running` flag 控制，OK；pipeline `_on_pipeline_done` 走 DashboardView（常駐 mount），OK。未來新增 background updater 要套 Pattern A。

---

## §5 Bug #13 修復指引（給碼農 A）

### 5.1 碼農修完後程式必須滿足的條件（檢核清單）

**C9. `_stop_recording_async` 不再對 cf.Future 呼叫 asyncio.shield/wait_for/await**
- [ ] L191 的 `await asyncio.wait_for(asyncio.shield(task), ...)` 改掉；不得直接對 `pipeline_task`（cf.Future）呼叫任何 asyncio 語法（shield/wait_for/ensure_future/gather/await）
- [ ] L199 的 `await task` 改掉；改為 `await asyncio.wrap_future(task)` 或輪詢

**C10. watchdog 超時語意與 I3 invariant 維持一致**
- [ ] drain 超時 = `stop_drain_timeout_sec`（預設 90）仍是主要 timeout
- [ ] 超時觸發 `task.cancel()`（cf.Future.cancel() 在 run_coroutine_threadsafe 特化下會 propagate 到底層 asyncio task，**OK 不需換 API**）
- [ ] cancel 後**必須等 task 真的完成才回返**（避免 UI 切 review 的 race：`_on_pipeline_done` 是在 pipeline task 內呼的，call 者要等它跑完）

**C11. 正常路徑 UI 閉環恢復**
- [ ] 甲方按停止 → drain 期間 UI 可顯示「停止中...」（可選，不強制）
- [ ] drain 成功 → `_on_pipeline_done` 正常 call → UI 進 review
- [ ] 實機 V5 現場「停止按鈕無反應」不再發生

**C12. 單元測試抓得到 cf.Future vs asyncio.Task 差異**
- [ ] V5 devlog §「未抓到原因」結論：碼農 A 用 `asyncio.create_task` mock pipeline_task 導致 shield 可通過，實機炸。**新測試要模擬真正的 cf.Future**：
  - 方法 1：用 `asyncio.run_coroutine_threadsafe(coro, loop)` 產真 cf.Future（最接近實機）
  - 方法 2：mock 出只有 `done()`/`cancel()`/`result()` 介面的 mock，**拔掉 `__await__`**，確保 code path 不走 asyncio 語法
  - 方法 3（推薦）：測試雙軌 — 舊 asyncio.Task mock 測保留、新增 cf.Future 真實測（可 xfail 標記實機才能跑）
- [ ] 建議加一個 smoke test 斷言 `type(page.run_task(...)) is concurrent.futures.Future`（未來 Flet 升版行為改變能提早 catch）

**C13. 附帶修改（依 V5 Obs）**
- [ ] Obs-1：[exporter.py:15-16](app/core/exporter.py#L15-L16) `session.status = "exported"` 改走 `SessionManager.mark_exported(session, path)`
- [ ] Obs-2：`_stop_recording_async` 加「二次按停」強制逃生 —— 若進入時 `task` 存在且 `stop_drain_timeout_sec` 計時已啟動但未結束（需追蹤），第二次 call 直接 `task.cancel()`。研究者建議：用一個 `_stop_requested_at: float | None` 欄位追蹤；進入時若 not None 且 `now - that > 10` 秒 → 直接 cancel。**非阻塞，可列 future-work 不阻斷 Bug #13 PR**
- [ ] Obs-3：[stream_processor.py:141-144](app/core/stream_processor.py#L141-L144) 若 `len(session.segments) == 0` → skip final summary call、直接 `_build_fallback_final(session, "empty_segments")`。修 §6 原則 3「明確告知使用者」

### 5.2 具體動點

| # | 檔案 | 位置 | 動作 |
|---|---|---|---|
| 1 | [main.py:49](app/main.py#L49) | `pipeline_task: asyncio.Task` | 改 `pipeline_task: Future | None = None`；import `from concurrent.futures import Future` |
| 2 | [main.py:191](app/main.py#L191) | `asyncio.wait_for(asyncio.shield(task), ...)` | 改方案見 §5.3 |
| 3 | [main.py:199](app/main.py#L199) | `await task` | 改方案見 §5.3 |

### 5.3 兩個可行實作方向（碼農自選）

**方案 A — 輪詢（Verifier 推薦、研究者支持）**

語意最清晰、不引入 wrap_future 的邊界行為：

碼農實作條件（不寫 code，給碼農自由發揮）：
- 進入 `_stop_recording_async` 時記錄 `deadline = loop.time() + stop_drain_timeout_sec`
- `while not task.done()` + 檢查 `loop.time() >= deadline` + `await asyncio.sleep(0.2)`
- 超時 → `task.cancel()` → 繼續 poll 到 `task.done()`（最多再等 5~10 秒保險）
- 整段不碰 `asyncio.shield / wait_for / await task / wrap_future`

優點：
- 完全不依賴 asyncio 對 cf.Future 的 bridge 假設
- `task.done()` / `task.cancel()` 是 cf.Future 原生 API，穩定
- 邏輯一目了然，單元測試好寫（mock `task.done()` 序列）

缺點：
- 200ms 粒度（夠用）
- 多幾行 code

**方案 B — `asyncio.wrap_future`（更簡潔但需理解 bridge 語意）**

碼農實作條件：
- `async_fut = asyncio.wrap_future(task)` 在 drain 之前一次
- `await asyncio.wait_for(asyncio.shield(async_fut), timeout=stop_drain_timeout_sec)`
- TimeoutError → `task.cancel()` 對 cf.Future（會 propagate）→ `await asyncio.wrap_future(task)` 再等完（第二次 wrap 是否合法？**需實測**：同一 cf.Future 重複 wrap_future 會回**不同**的 asyncio.Future，因為第二次 wrap 的 cf.Future 可能已經 done 了 — 理論上可以，但碼農若選方案 B 請先跑小 demo 確認）

優點：更 pythonic、行數少。
缺點：有「wrap_future 能否重複」這個 edge case，且 shield 保護語意碼農要自己理解透。

**研究者強烈推薦方案 A**。理由：Bug #13 是「假設 asyncio 介面套 cf.Future」造成的，方案 A 完全不做這個假設，從根源上排除同類 bug。方案 B 仍在 bridge 層走，雖技術上正確但把複雜度還給未來。

### 5.4 回歸風險

- **watchdog 超時後等太久**：若 cancel 後 task 死不下來（極端 bug），`while task.done()` 會卡死 event loop 這個 task。建議最後一段輪詢加硬 timeout（例 10 秒），即使 `task.done()=False` 也強制 return，避免 UI 永遠卡在停止中。
- **drain 期間 UI update**：目前 `on_stop_recording` 是 fire-and-forget，甲方按停止後無視覺回饋。C11 說「可選顯示停止中」— 建議碼農順手加一個 `status_bar` 或 dashboard 上的「停止中...」indicator（從按下到 `_on_pipeline_done` 之間）。非阻塞 Bug #13 但 V5 甲方 UX 體感強烈；**碼農 A 判斷**。
- **I3 invariant 語意不變**：即使換 polling，cancel 仍是「超時才啟動的安全網」。§1.3 / §1.4 中 pipeline_lifecycle 架構 review 的 I3 不需改。

---

## §6 Bug #14 修復指引（給碼農 B）

### 6.1 碼農修完後程式必須滿足的條件（檢核清單）

**C14. Bug #14 不再現**
- [ ] 實機按停止 → `_on_pipeline_done` → `dashboard.set_mode("review")` → `_build_review` → `SummaryPanel.update_highlights` 不 raise RuntimeError
- [ ] `_build_review` 內三條 call：`update_highlights` / `update_decisions` / `set_items` 全部安全
- [ ] 對 panel 的 for-loop append（transcript_panel 填歷史 segments）安全

**C15. 同類 pattern 全面掃清（防止下輪再爆）**
- [ ] grep 清掃所有 UI 檔的 `\.update\(\)` 與 `if self\.page` 與 `if self\._page`
- [ ] 套 Pattern A（`_mounted` flag + did_mount / will_unmount）於**所有 panel-class**（TranscriptPanel / SummaryPanel / ActionsPanel）
- [ ] `if self.page:` 守衛**全數移除或改為 try/except**（因為它是假守衛，在 unmount 時會 raise 而非 return False）
- [ ] 改完後 grep 再掃一次，確保沒殘留 `if self.page:`（或至少每一個殘留都附 comment 說明為什麼該處事件觸發必 mount 安全）

**C16. `did_mount` hook 內首次填資料**
- [ ] Panel 的 did_mount 若需首次從 session 填入資料（如 review mode 下的 highlights）—— 研究者建議由 Pattern C：`_build_review` 存 session state 到 panel 的 `_pending_highlights` / `_pending_decisions` / `_pending_items`，did_mount 時一次 render。**這樣完全不需要 mount flag**，因為 did_mount 被呼叫時本來就 mount。
- [ ] 若採 Pattern A（mount flag），`_build_review` 的 pre-mount call 仍會 return 早（`if not self._mounted: return`），此時 panel 內部狀態雖已改（value 已寫）但沒 update；等 panel mount 到 page 後，首次 render 會帶出新值。**需驗證 Flet 的 first-render 行為：control 剛 mount 時會不會自動 render 當前 state？**

**研究者不確定的地方（需碼農實測或甲方協助）**：
- **Flet 0.84 控件首次 mount 時**：會呼叫 `did_mount()`，但在 `did_mount` 執行**之前**，Flet 會不會先用 ctor 當下的 property 值做一次 render？我推測是「先 render 一次 → 再 did_mount」，因為這是大多數 UI 框架的標準流程。**若如此，Pattern A 足夠：pre-mount 改 `_highlights_field.value`，mount 時自動 render 出來，did_mount 不需做額外事**。
- 若不如此，要靠 did_mount 觸發一次 `update()` / 手動 render，這就是 Pattern C。
- **建議**：碼農 B 實作時先用 Pattern A + 實機 V Phase 第六輪驗；若 review mode 首屏不顯示 highlights 就補 Pattern C（did_mount 內 call 一次 `_refresh_from_session`）。

### 6.2 具體動點

#### 階段 1 — Panel 類改造（Pattern A）

| # | 檔案 | class | 動作 |
|---|---|---|---|
| 1 | [dashboard_view.py](app/ui/dashboard_view.py) | TranscriptPanel | `__init__` 加 `self._mounted = False`；加 `did_mount` / `will_unmount`；`append` 把 `if self._auto_scroll and self.page` 改 `if self._auto_scroll and self._mounted`；`_scroll_to_bottom` 同樣 |
| 2 | [dashboard_view.py](app/ui/dashboard_view.py) | SummaryPanel | 同上；`_on_highlights_changed` / `update_highlights` / `update_decisions` 三處改 |
| 3 | [dashboard_view.py](app/ui/dashboard_view.py) | ActionsPanel | 同上；`_refresh_ui` 改 |

#### 階段 2 — DashboardView 本身（低危但一致性）

| # | 檔案 | 動作 |
|---|---|---|
| 4 | [dashboard_view.py:378](app/ui/dashboard_view.py#L378) `set_mode` | 建議改為「先切 content，再 if 旗標 update」—— 用 mount_flag 而非 self.page |
| 5 | [dashboard_view.py:638,643](app/ui/dashboard_view.py#L638) 響應式佈局 | 事件驅動必 mount，不急改但建議一致化 |

#### 階段 3 — 其他 view

| # | 檔案 | 動作 |
|---|---|---|
| 6 | [feedback_view.py:39](app/ui/feedback_view.py#L39) | 改 `if self._mounted:` — 目前 Pattern B 事件只從 did_mount 觸發 OK，但套 Pattern A 更穩 |
| 7 | [terms_view.py:106](app/ui/terms_view.py#L106) | 同上 |
| 8 | [settings_view.py:116,130](app/ui/settings_view.py#L116) | 同上；特別改掉 `hasattr(self, 'page')` 這個假守衛 |
| 9 | [main_view.py:64,69,80,89](app/ui/main_view.py#L64) StatusBar | 改 `if self._mounted:` — 目前用 `if self.page:` 實際 OK 因為 StatusBar 一直 mount，但防未來新 call site 從 pre-mount 誤觸 |

### 6.3 全面防禦 pattern 建議（寫進 CLAUDE.md 的 UI 規範）

研究者建議送大統領評估加入 CLAUDE.md 或新增 `doc/specs/ui_conventions.md`：

1. **所有 custom control**（繼承 `ft.Container` / `ft.UserControl` 等）必須：
   - `__init__` 內 `self._mounted = False`
   - overriding `did_mount`: `self._mounted = True; super().did_mount()`
   - overriding `will_unmount`: `self._mounted = False; super().will_unmount()`
2. **所有 `xxx.update()` 呼叫前必檢 `self._mounted`**（不用 `self.page`，它是假守衛會 raise）
3. **`__init__` 內絕不呼叫 `update()` 或 `self.refresh()`**；首次渲染靠「建構階段賦值 property」或「did_mount 內 render」
4. **`page.run_task` 啟的 background task 內**：若會動 UI，必須檢 `self._mounted`（task 生命週期可能長於 control）
5. **事件 callback（`on_*`）內不需檢查**（Flet 保證事件派發前 control 已 mount）

### 6.4 回歸風險

- **改 `_mounted` flag 後舊行為**：某些 code path 原本「靜默忽略」（因 `if self.page` 在 page==None 時回 falsy 然後不 update），改 flag 後邏輯等價。但極邊界情況「control 已 mount 但 Flet 內部 page ref 還沒 set」（3.2 表「灰色區」）—— 我沒實測；碼農若遇到首次 mount 沒 render 出 highlights，檢查這點。
- **did_mount 沒覆蓋 base 的 debug log**：`BaseControl.did_mount` 有 `controls_log.debug(...)`，override 時別忘 `super().did_mount()`。
- **Pattern A 對 panel 外部已賦值的狀態**：`_build_review` 賦 `panel._highlights_field.value = text`（直接碰 field 的 attr），Flet 的 `before_update` 可能 validate；實測若 value 是 `ft.TextField` 原生 attr 應 OK（dashboard_view.py 很多地方都這樣寫）。

---

## §7 新增 Regression Tests 建議

### 7.1 反思：為什麼既有 test 沒抓到 Bug #13/#14

V5 Verifier devlog §「未抓到原因」已結論：

| Bug | 漏抓原因 | 新測試策略 |
|---|---|---|
| #13 | 單元測試用 `asyncio.create_task` mock pipeline_task → shield 可通過；實機 cf.Future 不同 | **測 runtime type 假設**，見下 7.2 T-F1 |
| #14 | 第三輪 Bug #7 commit 43932d3 只修 FeedbackView 沒掃全項目；`if self.page:` 假守衛沒被測到 | **加 pre-mount call test**，見下 7.2 T-F2 |

研究者反思補充：**兩個 bug 的共同模式**是「framework integration 假設」——
- Bug #13 假設 `page.run_task → asyncio.Task`（錯）
- Bug #14 假設 `self.page → None or Page`（錯，未 mount 時 raise）

**根治方法**：測試不只測「我方 code」，要測「框架 API contract」。若 framework 升版改了 contract，測試應先 fail。

### 7.2 必加的 Spec-Level Tests

| Test 名 | 類別 | 驗證什麼 | 實作方式 |
|---|---|---|---|
| **T-F1**: `test_flet_run_task_returns_concurrent_future` | Smoke / contract | Flet runtime 下 `page.run_task` 回傳型別是 `concurrent.futures.Future`（非 asyncio.Task）；如果未來 Flet 升版改了此行為，此 test fail 提醒 researcher 補研究 | 用 `flet_test` 工具或整合測 harness 開 session 跑一個 `async def noop(): pass`，assert type；或直接 `inspect.signature(Page.run_task).return_annotation is concurrent.futures.Future`（不跑 runtime 也可） |
| **T-F2**: `test_summary_panel_update_does_not_raise_pre_mount` | Unit | 建 `SummaryPanel()` 不 mount，呼 `update_highlights("x")` 不 raise | 直接單元測；斷言 `_highlights_field.value == "x"`（state 仍改），`_mounted == False`（沒 update）|
| **T-F3**: `test_actions_panel_set_items_pre_mount_does_not_raise` | Unit | 同 T-F2 但 ActionsPanel | 同 |
| **T-F4**: `test_transcript_panel_append_pre_mount_does_not_raise` | Unit | TranscriptPanel 未 mount 時 append segment 不 raise | 同 |
| **T-F5**: `test_stop_recording_async_with_running_cf_future` | Unit（重寫） | 用 `asyncio.run_coroutine_threadsafe` 或 mock-without-`__await__` 產 cf.Future；驗 drain 正常路徑完成、超時路徑 cancel | 替換原 `test_on_stop_recording_waits_for_pipeline_drain` 類 test |
| **T-F6**: `test_stop_recording_async_timeout_cancels_cf_future` | Unit（重寫） | 同上，模擬 task 永不 done，驗 `task.cancel()` 被呼叫 | 同 |
| **T-F7**: `test_build_review_full_flow` | Integration | 建 DashboardView，set_mode("review", session_with_summary)，驗不 raise、panel 狀態正確 | 可能需 Flet test harness；或至少斷言各 panel 的 `_highlights_field.value` |
| **T-F8**: `test_self_page_raises_pre_mount_contract` | Contract | 驗 Flet 0.84 下 BaseControl.page 未 mount raise RuntimeError（守衛 Flet 升版行為變動）| `try: _ = Control().page; except RuntimeError: pass` |
| **T-F9**: `test_event_callback_async_is_awaited` | Smoke | Flet 0.84 async on_click 直接 await（驗證第 2 節結論）| 若無 runtime harness，改查 `inspect.getsource` 裡 `iscoroutinefunction(event_handler)` 分支還在 |

### 7.3 非單元層測試（給實驗者 V Phase 第六輪）

1. **實機整合 test**：`python -m app.main` 背景啟動 + Monitor；模擬甲方按停（若能 script）或甲方真實按停
   - Bug #13 不再現 = 無 `ERROR:concurrent.futures:exception calling callback` + 無 `TypeError: An asyncio.Future...`
   - Bug #14 不再現 = 無 `RuntimeError: ...Control must be added to the page first`
   - UI 進 review（目視）+ 甲方可點「匯出 Markdown」
2. **reviewer 檢核表加一條**：PR diff 必含「所有 custom control 的 `_mounted` flag 覆蓋」；gre p `if self\.page` 殘留數量應**明顯下降**。
3. **Flet contract snapshot test**：每次 Flet 升版前跑 T-F1 / T-F8 / T-F9，fail 則觸發 researcher 重新 review。

### 7.4 實驗者反思「不要再寫驗 pattern 不驗 spec」如何落地

- 第五輪反思：「單元綠燈 ≠ 符合 spec」在靜態層已收斂（spec-level tests 存在）；但 V5 發現 **「spec-level 綠燈 ≠ framework runtime 行為」**
- 建議下一輪再加一層：**framework contract test**（T-F1 / T-F8 / T-F9）。這一層的測試不是驗業務邏輯，而是「我們對 Flet 的假設是否成立」。一旦 contract 變，所有業務 test 的前提也塌。

---

## §8 前兩份研究的遺漏反思

### 8.1 [[flet_0.84_migration_20260408]] 的遺漏

第一篇盤點了 Flet 0.84 所有 constructor / API 命名不相容，覆蓋率不錯。補強 §G（2026-04-09）進一步盤點了 `.update()` 與 lifecycle 變動。**兩個遺漏**：

1. **§G 的 `.update()` 盤點只看「`__init__` 內直接呼叫」**，沒看「事件驅動但可能在 pre-mount 路徑呼叫」的方法（如 `update_highlights` 被 `_build_review` 從 DashboardView 驅動，時機不是事件而是從父 control 的 method 呼）。這類 call site 形式上不在 `__init__` 但語意上等同 pre-mount。
2. **沒查 `self.page` property 的行為變化**。Flet 0.70 之前 `page` 是一般 attribute，未 mount 時為 None；0.84 改成 property 未 mount 時 raise RuntimeError。所有 `if self.page:` 守衛在 0.84 下語意翻轉，我沒發現。

**如果當時做了**：grep `if self.page` → 讀 `BaseControl.page` 源碼 → 一眼看出「property fget 未 mount 會 raise」 → 整個守衛模式要改。Bug #14 本輪（V5）才爆出，其實 V3/V4 Bug #7 修 FeedbackView 時就該一次解。

### 8.2 [[pipeline_lifecycle_architecture_20260416]] 的遺漏

第二篇架構 review 給 7 invariants + summarizer 選型 + stop 語意，對 Python asyncio 層面完整；但**完全沒查 Flet runtime 的 async bridge 模型**：

1. §2.3 方案 A 建議「`asyncio.wait_for(pipeline_task, timeout)`」時沒問「pipeline_task 在 Flet 0.84 runtime 下是什麼型別」。**這是 framework integration 盲點**。
2. 我當時假設 `pipeline_task = page.run_task(_run)` 回 asyncio.Task，因為 Python 語境下大部分 `run_task` 風格 API 都回 asyncio.Task。**這個假設沒驗**。
3. 碼農 A 看 main.py 原本的 `pipeline_task: asyncio.Task | None = None` type annotation（不是我寫的，但我 review 時沒挑出矛盾），照著假設寫 shield。實機炸。

**如果當時做了**：花 30 秒 `inspect.getsource(Page.run_task)` → 看到 `concurrent.futures.Future` return type → 當場把 §2.3 方案 A 的條件改成「若 `pipeline_task` 是 cf.Future 則需 `asyncio.wrap_future` 或輪詢」。

### 8.3 下次架構 review 的 Framework Integration Checklist（提議送大統領入 researcher_handbook）

當研究者做「涉及 Flet / asyncio / DB driver / HTTP client 等框架混合」的架構 review 時，必須：

1. **Framework runtime 介面確認**：所有涉及到的框架 API 都要 `inspect.signature` / `inspect.getsource` 一次，確認回傳型別、入參型別、是否 raise、是否 blocking/async。**不能只靠官方文件或記憶**。
2. **Framework 生命週期確認**：如 Flet 的 `did_mount` / `will_unmount` / `before_update`、asyncio 的 task cancellation semantics、DB connection pool 的 open/close 時機 — 要在架構 review 裡明確標 framework 的 lifecycle state machine。
3. **Cross-runtime 假設標紅**：所有「從 A runtime 把東西丟給 B runtime」的介面（Flet run_task 跨 thread、asyncio 和 concurrent.futures bridge、sync DB driver 在 async context）要列入風險清單、明確寫「bridge 函式是 X」、「不能直接套 Y」。
4. **實測優先**：當研究者提 pattern 建議時（如 §2.3 方案 A），必須附至少一段 probe 的 output（哪怕是 `type(...)` 印出）。本次 Flet async/lifecycle 研究就是**這個規矩的試金石** — 每個結論都附實測 evidence。
5. **架構 review 文件結尾加 §「研究者自 checklist」**：附類似「本 review 涵蓋了 framework API contract 嗎？涵蓋了 lifecycle 嗎？涵蓋了 cross-runtime bridge 嗎？」三問，逼迫自己回答「是」才能結案。若「否」要顯式列 future-work。

---

## §9 與 Spec 的 Gap（送大統領裁決）

### G8（🟥 高優先）— UI 規範缺「mount lifecycle 守則」

**位置**：無（建議新增 `doc/specs/ui_conventions.md` 或併入 [[ui_spec]]）

**現況**：本專案重複爆發 `if self.page:` 假守衛 bug（Bug #7、Bug #14），同類 pattern 在全項目至少 9 處。spec 完全沒規範「UI 控件的 mount 生命週期應如何寫」。每個碼農靠各自經驗，形成 pattern 不一致。

**建議**：入 spec § 6.5 UI 規範
1. 所有 custom control 套 `_mounted` flag pattern（§6.3）
2. `__init__` 禁止 update；首屏資料由建構 attr 賦值或 did_mount 內 render
3. grep `if self.page:` 應為 0 或每處附說明 comment
4. 「UI 轉場」invariant（延續 V5 Verifier 建議）：mode=review 必須伴隨 UI 轉場實際發生（而非只是 status=ready 表象成立）

**影響**：碼農 B 本次修法按 §6.3 pattern，同步更新 spec，日後新 panel 一致。

### G9（🟧 中優先）— 碼農開發時需要 Flet runtime probe helper

**位置**：建議新增 `tests/contract/test_flet_runtime_contract.py` 或 similar

**現況**：本輪 Bug #13 暴露「我們對 Flet 的假設沒 test 守護」。未來 Flet 升版若改 `page.run_task` 回傳型別、或改 `BaseControl.page` 行為，現有 test 不會 fail。

**建議**：加 T-F1 / T-F8 / T-F9（§7.2）為 contract test；每次 `pip install` 升版 Flet 前 CI 先跑這組 test，fail 則 block upgrade + trigger researcher 重新 review。

### G10（🟨 低優先）— research 文件命名空間

**位置**：`doc/research/` 已有三份 Flet 相關：

- `flet_0.84_migration_20260408.md`（原始 + §G 補強）
- `pipeline_lifecycle_architecture_20260416.md`（架構 review）
- `flet_0.84_async_lifecycle_20260417.md`（本篇）

**現況**：三份各自獨立，互不取代。`flet_0.84_migration_20260408` 的 §G 與本篇 §3 有重疊但後者更完整。

**建議**：在 `migration_20260408.md` §G 開頭加 redirect：「2026-04-17 後以 [[flet_0.84_async_lifecycle_20260417]] 為 lifecycle 單一權威來源」。本篇為新的 SSoT。非阻塞。

---

## §10 研究者結論與交棒建議

### 10.1 結論

- **Bug #13 根因**：`page.run_task` 回 `concurrent.futures.Future` 不是 `asyncio.Task`；`asyncio.shield / wait_for / ensure_future / gather` 對 cf.Future 一律 TypeError。**Bridge**：`asyncio.wrap_future(cf_future)` 或改輪詢。
- **Bug #14 根因**：Flet 0.84 `BaseControl.page` 改為 property，未 mount 時 **raise RuntimeError 而非返 None**。全專案 9+ 處 `if self.page:` 守衛都是**假守衛** — 在 unmount 狀態下會 raise 而非短路。碼農用 `self._mounted` flag 取代。
- **根本模式**：兩個 bug 都是「framework integration 假設沒驗」造成。修法不只補 bug，還要加 contract test + UI 規範 spec + researcher checklist 防未來同類。

### 10.2 給大統領的派工建議

1. **碼農 A 修 Bug #13**（獨立 PR）
   - 遵循 §5 指引，推薦**方案 A（輪詢）**
   - 附帶 Obs-1 (mark_exported) / Obs-3 (empty segments fallback)
   - 加 T-F1 / T-F5 / T-F6 tests
   - Obs-2（二次按停）視碼農判斷，可列 future-work 不阻 PR

2. **碼農 B 修 Bug #14**（獨立 PR，可與 #13 並行）
   - 遵循 §6 指引，Pattern A（`_mounted` flag）為主
   - 掃清**所有** `if self.page:` 殘留（§4.2 完整清單）
   - 加 T-F2 / T-F3 / T-F4 / T-F7 / T-F8 tests
   - 若 Pattern A 仍有 review mode 首屏不顯示資料的問題，補 Pattern C（did_mount 內 render）

3. **大統領/研究者 spec 補強**
   - G8（UI mount lifecycle 守則）建議送甲方簽核（涉及 spec 新章）
   - G9（contract test）可大統領直接裁決
   - G10 非阻塞，可延後

4. **V Phase 第六輪（實驗者）**
   - 兩個 PR merge 後 regression 跑 T-F1~T-F9
   - 實機 T1-T6 + S2/S4/S5/S9（V5 阻塞的全部補跑）
   - 靜態檢核加新 invariant「I2 UI 轉場完成才算閉環」

### 10.3 研究者守本分（本篇沒做的事）

- ❌ 沒寫 code（本文 0 行業務 Python；§1/§2 的 probe code 只是 inspect，不改 app）
- ❌ 沒動 spec（§9 G8/G9/G10 只建議，送大統領/甲方）
- ❌ 沒補 bug_report 章節（本篇為獨立 research）
- ❌ 沒指派 Builder 具體實作細節（§5/§6 只給條件，方案自選）

### 10.4 不確定標註（誠實交代）

| 項 | 為什麼不確定 | 補救建議 |
|---|---|---|
| §1.5 `asyncio.wrap_future` 外層 cancel 傳播邊界 | 沒實測「outer task 被 cancel 時 wrap_future 的 async.Future 行為」| 碼農若選方案 B 請 2-3 行 demo 確認；推薦走方案 A 完全避開 |
| §3.6 `did_mount` vs `_page_ref` 多 page 邊界 | 本專案單 page 不受影響；未來若多 page 需重驗 | 入 future-work；本次修法 OK |
| §6.1 C16 Flet 首次 mount 是否自動 render 當前 state | 沒實測；推測是（標準 UI 框架行為） | 碼農 B 實作時實機驗；若不 render 就補 Pattern C |
| §3.2 表「page.add 後 / did_mount 前」灰色區窗口 | Flet 內部 mount 流程未逐步追 | 不要依賴該窗口做事；mount flag pattern 把 `_mounted=True` 放 `did_mount` 最前端即可避開 |

---

## §11 引用來源

- [flet-dev/flet v0.84.0 source — `page.py` L718~L750](https://github.com/flet-dev/flet/blob/v0.84.0/sdk/python/packages/flet/src/flet/controls/page.py)
- [flet-dev/flet v0.84.0 source — `base_control.py` L265~L280（page property）](https://github.com/flet-dev/flet/blob/v0.84.0/sdk/python/packages/flet/src/flet/controls/base_control.py)
- [flet-dev/flet v0.84.0 source — `base_control.py` L440~L460（event dispatch）](https://github.com/flet-dev/flet/blob/v0.84.0/sdk/python/packages/flet/src/flet/controls/base_control.py)
- [Python `asyncio.wrap_future` 官方文件](https://docs.python.org/3/library/asyncio-future.html#asyncio.wrap_future)
- [Python `asyncio.run_coroutine_threadsafe` 官方文件](https://docs.python.org/3/library/asyncio-task.html#asyncio.run_coroutine_threadsafe)
- 本專案實測：`pip show flet`（0.84.0）、`inspect.getsource(Page.run_task)`、`inspect.getsource(BaseControl.page.fget)`、`concurrent.futures.Future.__await__`（None）、`asyncio.wrap_future` 與 `asyncio.shield` compatibility probe（§1.2 表）、`BaseControl().page` → RuntimeError（§3.1）
- 前置研究：[[flet_0.84_migration_20260408]]（原始 + §G）、[[pipeline_lifecycle_architecture_20260416]]
- 實機證據：[[vphase5_raw_round2]] L68~L82（Bug #13 Traceback）、L88~L108（Bug #14 Traceback）
- 實驗者反思：[[devlog_20260416_verifier_vphase5]] §「為什麼靜態沒抓到 Bug #13/#14」

---

> 研究者簽核：§1/§2 實測完成、§3 lifecycle 映射表含全專案 9+ 個守衛盤點、§4/§5/§6 修復指引給條件不給 code、§7 framework contract test 建議、§8 前兩份研究遺漏反思含下次 review checklist、§9 spec gap 三項送大統領。交棒碼農 A 修 #13、碼農 B 修 #14，可並行。
