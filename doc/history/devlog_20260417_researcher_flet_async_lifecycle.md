---
title: 開發日誌 2026-04-17 — 研究者 Flet 0.84 async/lifecycle 補強研究
date: 2026-04-17
type: devlog
status: complete
author: 研究者（Researcher）
tags:
  - devlog
  - researcher
  - flet
  - async
  - lifecycle
  - bug-13
  - bug-14
related:
  - "[[flet_0.84_async_lifecycle_20260417]]"
  - "[[flet_0.84_migration_20260408]]"
  - "[[pipeline_lifecycle_architecture_20260416]]"
  - "[[devlog_20260416_verifier_vphase5]]"
  - "[[bug_report_flet_api_20260406]]"
---

# 研究者 Flet 0.84 async/lifecycle 補強研究 — 2026-04-17

> 任務來源：V Phase 第五輪實機 FAIL，Bug #13（`asyncio.shield(page.run_task ret)` TypeError）+ Bug #14（`SummaryPanel.update_highlights` mount 前 RuntimeError）兩個新 bug 共同特徵為「前兩輪研究漏網、單元測試抓不到」。大統領派研究者補完 Flet 0.84 async/task 層 + lifecycle 層完整映射。
>
> 產出：[[flet_0.84_async_lifecycle_20260417]]（補強第三篇研究）

---

## 研究結論摘要

### Bug #13 根因與修復方向

- **根因**：Flet 0.84 `page.run_task` 回 `concurrent.futures.Future` 不是 `asyncio.Task`；`asyncio.shield / wait_for / ensure_future / gather / await` 對 cf.Future 一律 TypeError（實測 Python probe 確認 cf.Future 無 `__await__`）
- **Bridge**：`asyncio.wrap_future(cf_future)` 是官方 bridge；或全程用 `task.done() / .cancel() / .result()` 輪詢
- **修復推薦方案 A（輪詢）**：不碰 asyncio↔cf bridge、語意最清晰、單元測好寫
- **影響範圍**：main.py 一個檔，`stream_processor.py` 的 shield OK 不動（其 task 是 `asyncio.create_task` 產物）

### Bug #14 根因與修復方向

- **根因**：Flet 0.84 `BaseControl.page` 改為 property，未 mount 時 **raise RuntimeError 而非 None**（inspect base_control.py L265~L280 + 實測小 demo 確認）。全專案 9+ 處 `if self.page:` 守衛都是**假守衛** — unmount 下會 raise 而非短路
- **修復推薦 Pattern A（mount flag）**：`__init__` 設 `self._mounted = False`；`did_mount` / `will_unmount` hook 維護；所有 `.update()` 前檢 `self._mounted`
- **影響範圍**：dashboard_view.py（TranscriptPanel / SummaryPanel / ActionsPanel 三 panel + DashboardView 本身）、feedback_view / terms_view / settings_view / main_view 共 4 檔

### Flet async callback 原生支援

- `inspect.getsource(base_control.py)` L445~L460 確認 Flet 0.84 event dispatcher **直接 `await` async callback**（`iscoroutinefunction` 分支），也支援 async generator / sync generator
- 本專案 `_handle_import_audio` 已是 async callback 實例，語法成立
- 碼農 A 修 Bug #13 時若想改「async 全鏈」可行，但研究者建議保留現有結構最小改動

---

## §8 反思重點（前兩份研究的遺漏）

### 前一篇 [[flet_0.84_migration_20260408]] 的兩個遺漏

1. **§G lifecycle 盤點只看 `__init__` 內呼叫 `update()`，沒看「事件外被父 control method 驅動」的 pre-mount 路徑**（如 SummaryPanel.update_highlights 被 `_build_review` 在 new 後立刻呼 → Bug #14 現場）
2. **沒查 `self.page` property 在 0.84 的行為變化**。Flet 0.70 之前是普通 attribute 未 mount 為 None；0.84 改 property 未 mount raise。全專案 `if self.page:` 守衛語意翻轉，本該 V3 Bug #7 一次掃乾淨

### 前一篇 [[pipeline_lifecycle_architecture_20260416]] 的遺漏

1. **§2.3 方案 A 建議 `asyncio.wait_for(pipeline_task, T)` 時沒查 `pipeline_task` 在 Flet runtime 下的型別**。我當時假設 asyncio.Task（Python 慣例），但沒 `inspect.getsource(Page.run_task)` → 錯過 `concurrent.futures.Future` 這個關鍵差異
2. **main.py 原本 `pipeline_task: asyncio.Task | None` type annotation 我 review 時沒挑出矛盾**。碼農 A 照假設寫 shield，實機炸

### 下次架構 review 的 Framework Integration Checklist（送大統領評估入 researcher_handbook）

研究涉及 framework 混合時必做：
1. **Runtime 介面確認**：`inspect.signature` / `inspect.getsource` 所有涉及的 framework API 一次，確認回傳型別、是否 raise、是否 blocking/async
2. **Framework lifecycle 明確**：如 Flet did_mount / will_unmount、asyncio cancel semantics、DB connection pool 開關時機
3. **Cross-runtime 假設標紅**：跨 thread / 跨 runtime bridge（如 `run_coroutine_threadsafe`）列風險清單
4. **實測優先**：每個 pattern 建議附至少一段 probe output；不能只靠官方文件或記憶
5. **結尾自 checklist**：「本 review 涵蓋 framework API contract 嗎？lifecycle 嗎？cross-runtime bridge 嗎？」三問

---

## 交棒建議

### 派工清單

| 角色 | 任務 | 依據 |
|---|---|---|
| **碼農 A** | 修 Bug #13（獨立 PR） | [[flet_0.84_async_lifecycle_20260417#§5 Bug #13 修復指引（給碼農 A）]]；推薦方案 A 輪詢；附帶 Obs-1 mark_exported + Obs-3 empty segments fallback；加 T-F1/T-F5/T-F6 contract+unit test |
| **碼農 B** | 修 Bug #14（獨立 PR，可與 #13 並行） | [[flet_0.84_async_lifecycle_20260417#§6 Bug #14 修復指引（給碼農 B）]]；Pattern A（mount flag）；掃清 §4.2 全清單；加 T-F2/T-F3/T-F4/T-F7/T-F8 test |
| **大統領** | 裁決 spec gap | §9 G8（UI mount lifecycle 守則）建議送甲方簽核；G9（contract test）大統領自決；G10 延後 |
| **實驗者** | V Phase 第六輪 | 兩 PR merge 後 regression + 實機 T1-T6 + S2/S4/S5/S9；靜態新 invariant「I2 UI 轉場完成才算閉環」 |

### 並行性

- 碼農 A 與 B 改不同檔（main.py vs app/ui/*.py），**完全可並行**
- 建議兩 PR 前後腳 review，兩者 merge 後一次 V Phase 第六輪

### 不確定事項（需碼農實測或甲方協助小 demo）

1. §1.5 `asyncio.wrap_future` 外層 cancel 傳播邊界 — 碼農 A 若選方案 B（wrap_future）需 2-3 行 demo 確認；選方案 A 完全避開
2. §6.1 C16 Flet 首次 mount 是否自動 render ctor 當下的 state — 碼農 B 實機驗；若不 render 就補 Pattern C（did_mount 內 render）
3. §3.2 表「page.add 後 / did_mount 前」灰色區窗口 — 不要依賴；mount flag pattern 首行設 True 即可避開

---

## 研究過程紀錄（實測 probe）

```
pip show flet → 0.84.0 (確認版本)

inspect.signature(Page.run_task)
→ (handler: Callable[..., Awaitable[RetT]], *args, **kwargs) -> concurrent.futures._base.Future[RetT]

inspect.getsource(Page.run_task)
→ 內部用 asyncio.run_coroutine_threadsafe(coro, self.session.connection.loop)
→ 回傳 concurrent.futures.Future
→ 附 _on_completion done_callback re-raise exception（Bug #13 的 log surface 來源）

concurrent.futures.Future() — hasattr(__await__) → False
→ 不能直接 await

asyncio.shield(cf_future) → TypeError: An asyncio.Future, a coroutine or an awaitable is required
asyncio.wait_for(cf_future) → TypeError（同）
asyncio.wrap_future(cf_future) → 回 asyncio.Future（OK，可 await/shield/wait_for）

inspect.getsource(BaseControl.page.fget)
→ while parent: if isinstance(Page): return; parent=parent.parent
→ else: raise RuntimeError("Control must be added to the page first")

Probe().page → RuntimeError (直接炸，非 falsy)
try: _ = ctrl.page; except RuntimeError: (唯一正確 detection)

inspect.getsource(base_control.py L440~L460)
→ event dispatch: if iscoroutinefunction(handler): await handler(e)
→ Flet 0.84 原生支援 async callback，無需 lambda 包 run_task
```

---

## 檔案清單

- ✅ 研究報告：`doc/research/flet_0.84_async_lifecycle_20260417.md`（1 份，11 章）
- ✅ 本 devlog：`doc/history/devlog_20260417_researcher_flet_async_lifecycle.md`

### 未更新（守研究者本分）

- ❌ 未動 spec（G8/G9/G10 送大統領裁決）
- ❌ 未改 code（碼農 A/B 依研究執行）
- ❌ 未補 [[bug_report_flet_api_20260406]]（獨立 research 文件；bug_report 的 Bug #13/#14 章節已存在）

---

> 研究者簽核：補強研究完成，填補前兩份研究漏的兩個面向（Flet runtime task 型別 + self.page lifecycle 映射）。交棒大統領派工碼農 A/B 並行修復。
