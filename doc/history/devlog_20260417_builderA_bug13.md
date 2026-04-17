---
title: 開發日誌 2026-04-17 — 碼農 A 修 Bug #13 asyncio.shield(cf.Future) TypeError
date: 2026-04-17
type: devlog
status: active
author: 碼農 A（Builder A）
tags:
  - devlog
  - builder-a
  - bug-13
  - flet
  - concurrent-futures
  - async
related:
  - "[[flet_0.84_async_lifecycle_20260417]]"
  - "[[pipeline_lifecycle_architecture_20260416]]"
  - "[[bug_report_flet_api_20260406]]"
  - "[[devlog_20260416_builderA_bug11_10_12]]"
  - "[[devlog_20260416_verifier_vphase5]]"
---

# 碼農 A — Bug #13 asyncio.shield(cf.Future) TypeError 修復 — 2026-04-17

> 前一棒：實驗者 V Phase 第五輪實機按停止 → TypeError（[[devlog_20260416_verifier_vphase5]]）→ 研究者 [[flet_0.84_async_lifecycle_20260417]] §1 確認 cf.Future 不支援 asyncio.shield → 大統領派工。
> 與碼農 B 並行：我改 main.py，他改 app/ui/（Bug #14 mount lifecycle）。

---

## Bug #13 根因

[main.py:191](app/main.py#L191)（修前）：

```python
await asyncio.wait_for(asyncio.shield(task), timeout=stop_drain_timeout_sec)
```

`task = pipeline_task = page.run_task(_run)` — **回傳 `concurrent.futures.Future`**（非 `asyncio.Task`）。

研究者 §1.2 實測確認：cf.Future 沒有 `__await__`，`asyncio.shield` / `wait_for` / `ensure_future` 對它一律 `TypeError: An asyncio.Future, a coroutine or an awaitable is required`。

### 為什麼單元測試沒抓到

我上次（Bug #10 commit 9c6b96e）用 `asyncio.create_task` mock pipeline_task — 產出 `asyncio.Task`（有 `__await__`），shield 可通過。Flet runtime 下 `page.run_task` 走 `asyncio.run_coroutine_threadsafe` 回 cf.Future，型別不同。

研究者 §7.1 的結論：**spec-level test ≠ framework runtime 行為**。需加 framework contract test 層。

---

## 選方案 A（輪詢）的理由

研究者給兩個方案（§5.3）：

| | 方案 A（輪詢） | 方案 B（wrap_future） |
|---|---|---|
| 做法 | `while not task.done(): await asyncio.sleep(0.2)` | `asyncio.wrap_future(task)` → 再 `shield/wait_for` |
| 依賴 | 只用 cf.Future 原生 `.done()` / `.cancel()` | 依賴 `asyncio.wrap_future` bridge 語意 |
| 邊界 | 無 bridge 假設 | 重複 wrap 同一 cf.Future 行為未實測（§1.5） |
| 治本 | ✅ 完全避開 asyncio bridge | ❌ 仍在 bridge 層走 |

**選 A**。理由：Bug #13 是「假設 asyncio 介面套 cf.Future」造成的，方案 A 完全不做這個假設。方案 B 把複雜度留給未來（wrap_future 取消傳播邊界未驗）。研究者和實驗者都推薦 A。

---

## Diff 位置 + 變動邏輯

| # | 檔 | 位置 | 變動 |
|---|---|---|---|
| 1 | [app/main.py](app/main.py) | L6 import | 新增 `from concurrent.futures import Future` |
| 2 | [app/main.py](app/main.py) | L50 | `pipeline_task: asyncio.Task \| None` → `pipeline_task: Future \| None` |
| 3 | [app/main.py](app/main.py) | `_stop_recording_async` | 移除 `asyncio.wait_for(asyncio.shield(task), ...)` + `await task`；改兩階段輪詢 |

### 輪詢邏輯（方案 A 實作）

```
Phase 1 — drain wait:
  while not task.done():
    if loop.time() >= deadline (stop_drain_timeout_sec):
      task.cancel()  ← cf.Future.cancel() propagate 到底層 asyncio task（§1.3 OK）
      break
    await asyncio.sleep(0.2)

Phase 2 — post-cancel wait:
  if not task.done():
    cancel_deadline = loop.time() + 10  ← 硬 timeout 防 _run finally 死不下來
    while not task.done():
      if loop.time() >= cancel_deadline:
        logger.error("stuck — giving up")
        break
      await asyncio.sleep(0.2)
```

Phase 2 的存在原因：`task.cancel()` 後 `_run` 的 finally 仍需跑完 save + request_stop + UI 轉場。若不等它完成就 return，`_on_pipeline_done` 可能還在半途執行。加 10 秒硬 timeout 防極端卡死。

### 不動的東西

- **stream_processor.py**（`asyncio.shield(self._summary_task)`）：那個 task 是 `asyncio.create_task` 產物，真正的 `asyncio.Task`，shield 正確。研究者 §4.1 #7 確認。
- **_run 內部邏輯**（Bug #10 commit）：CancelledError / Exception / finally 分流不變。

---

## Contract Test 建立

碼農 B 已建 `tests/contract/test_flet_runtime_contract.py`（T-F2/F3/F4/F8）。我加 T-F1。

### T-F1：page.run_task 回傳型別守護

| Test | 驗證 |
|---|---|
| `test_run_task_source_uses_run_coroutine_threadsafe` | inspect Page.run_task 原始碼含 `run_coroutine_threadsafe` → 回傳必為 cf.Future |
| `test_cf_future_has_no_await` | `concurrent.futures.Future` 無 `__await__` → 確認 asyncio.shield 不可用 |

若 Flet 升版改 `run_task` 內部不再走 `run_coroutine_threadsafe`（例如改用 create_task），T-F1 立即 fail → trigger researcher 重新 review `_stop_recording_async` 相容性。

---

## cf.Future-aware Stop Lifecycle Tests

研究者 §5.1 C12 明確警告：**不要再用 asyncio.create_task mock pipeline_task**。新 tests 用 `_FakeCfFuture`（只有 `.done()` / `.cancel()`，無 `__await__`）：

| Test | 驗證 |
|---|---|
| `test_stop_drain_cf_future_normal_completion` | drain 成功 → 不觸發 cancel |
| `test_stop_drain_cf_future_timeout_triggers_cancel` | 超時 → cancel（I3 安全網） |
| `test_stop_drain_cf_future_already_done_returns_immediately` | 已 done → 不多等 |
| `test_stop_drain_does_not_use_asyncio_await_on_cf_future` | **核心**：fake 無 __await__，code 若 await 會 TypeError；test 通過 = code path 安全 |

---

## Invariants 維持

| Invariant | 影響 | 說明 |
|---|---|---|
| I1（任何路徑落盤） | 不變 | save 在 _run finally，與 stop 輪詢邏輯解耦 |
| I2（ready 才 UI 轉場） | 不變 | _on_pipeline_done 在 _run 內由 sp.run 收尾觸發 |
| I3（cancel 只在真卡死） | 維持 | 輪詢 deadline = stop_drain_timeout_sec；只改達成方式不改語意 |
| I5/I6（SSoT + transition） | 不變 | |

---

## 測試彙總

**Baseline 147 → 161 passed, 1 skipped**

- Contract test T-F1：+2 tests
- cf.Future stop lifecycle：+4 tests
- 碼農 B 並行的 Bug #14 tests（contract T-F2/F3/F4/F8）也在同一 run 中綠燈

---

## 實機層委交實驗者

如同 Bug #9/#11/#10/#12，以下 CLI 無法驗證，明確誠實委交實驗者 V Phase 第六輪：

1. **5+ 分鐘實機錄音 → 按停止** → UI 進 review + `data/sessions/` 有檔（驗 Bug #13 不再 TypeError）
2. **停止按鈕反應** → 甲方按停止後 UI 應在 drain 期間保持回應（200ms 輪詢不卡 event loop）
3. **Bug #13 V5 現場不再現** → log 無 `TypeError: An asyncio.Future, a coroutine or an awaitable is required`
4. **Bug #14 不再現**（碼農 B 並行修）→ log 無 `RuntimeError: Control must be added to the page first`
5. **正常 drain 成功** → 甲方按停止 → final summary 完成 → review mode（非 aborted）
6. **拔 Ollama 模擬** → final summary fallback → review mode with fallback_reason

---

## 未做（守碼農本分 + 非阻塞 Bug #13）

- ❌ 不改 spec（G8/G10 大統領已處理）
- ❌ 不動 stream_processor.py（研究者 §4.1 #7 確認 shield 正確）
- ❌ 不加「二次按停強制逃生」（研究者 C13 Obs-2 列為 future-work）
- ❌ 不加 Obs-1（exporter.py mark_exported）和 Obs-3（empty segments fallback）— 可獨立 PR 不阻塞
- ❌ 不改 dashboard_view 的 async callback 鏈（研究者 §2.3 選項 2 列為優化）

---

## 交棒

| 對象 | 請求 |
|---|---|
| **Reviewer** | 對照研究者 §5.1 C9-C13 逐條審；特別看輪詢的 Phase 2 硬 timeout（10s）是否足夠 |
| **實驗者** | V Phase 第六輪實機 6 點（見上方），特別注意 Bug #13 log 路徑不再出現 TypeError |
| **大統領** | Obs-1/2/3 三項附帶改善是否需要獨立 PR 或 future-work 歸檔 |

> 碼農 A 簽核：Bug #13 修復完成。方案 A 輪詢通過 161 tests。實機層誠實委交。
