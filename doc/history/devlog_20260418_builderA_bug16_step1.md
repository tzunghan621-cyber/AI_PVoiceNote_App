---
title: 碼農 A devlog — Bug #16 Step 1 修法四件套（A/B/C/D）
date: 2026-04-18
author: 碼農 A
bug: Bug #16（V2/V3 空摘要）+ F-1（stop_drain_timeout 時序張力）
related:
  - "[[devlog_20260418_builderA_bug16_step0]]"
  - "[[bug_report]]"
  - "[[decision_20260418_review_gate_restore]]"
stage: Step 1（實作）— 完成，等審察者 B Review Gate
status: 待 Review Gate
---

# 碼農 A — Bug #16 Step 1 修法 devlog

## 接令

Director 決策（接續 Step 0 診斷）：
- A/B/C 一次打包 + F-1 升格修法 D 併入
- 附帶發現 #1 Gemma 慢 / #3 Flet GC → V8 觀察，不開 bug
- Review Gate：審察者 B
- 新增 test ≥ 4 條

## 四件套實際改動

### 修法 A — `_build_incremental_prompt` 補完 JSON schema

| 檔案 | 變更 |
|---|---|
| [app/core/summarizer.py:186-202](../../app/core/summarizer.py#L186-L202) | incremental prompt 加入英文 key 明示 + 各欄位型別說明 + 「不可翻譯為中文 key」警示 |

**原因**：Step 0 log 實證 V3 Gemma 回中文 key（`會議重點` / `Action Items` / `決議事項`），
parser `parsed.get("highlights", ...)` 全 miss 吐空。initial prompt 本就明列英文 key schema，
incremental prompt 缺失此約束。

### 修法 B — `EmptySummaryError` + 週期 / final 兩層 catch

| 檔案 | 變更 |
|---|---|
| [app/core/summarizer.py:20-26](../../app/core/summarizer.py#L20-L26) | 新增 `class EmptySummaryError(Exception)` |
| [app/core/summarizer.py:130-145](../../app/core/summarizer.py#L130-L145) | parse 後判斷 highlights/action_items/decisions/keywords **全空** → raise EmptySummaryError（保留非空欄位 partial content 正常通過） |
| [app/core/stream_processor.py:14](../../app/core/stream_processor.py#L14) | import `EmptySummaryError` |
| [app/core/stream_processor.py:62-73](../../app/core/stream_processor.py#L62-L73) | `_run_summary_async` catch EmptySummaryError → 呼叫 `_build_fallback_summary(..., is_final=False)` → update_summary 複用最近非空週期版（`fallback_reason="empty_parse"`） |
| [app/core/stream_processor.py:195-200](../../app/core/stream_processor.py#L195-L200) | `_run_final_summary` catch EmptySummaryError → `_build_fallback_final(session, "empty_parse")` |

**Director 要求「週期層也要 catch」已落實**：V2 空時即觸發 fallback，不讓空摘要覆蓋 UI。

### 修法 C — `_build_fallback_final` F-2 guard

| 檔案 | 變更 |
|---|---|
| [app/core/stream_processor.py:207-240](../../app/core/stream_processor.py#L207-L240) | 抽出 `_build_fallback_summary(session, reason, is_final)` 共用 helper：`reversed(summary_history)` 向前找第一個 `highlights.strip() != ""` 的版本複用。is_final=True 全無非空時回占位失敗文案；is_final=False 全無非空時回 None（週期版不 update，UI 保留前版） |
| [app/core/stream_processor.py:198-205](../../app/core/stream_processor.py#L198-L205) | `_build_fallback_final` 改為呼叫 helper，保留 public API |

**失敗文案**維持 Step 0 草稿版「(摘要生成失敗，已保留逐字稿供手動整理)」。

### 修法 D — D1：config 值放寬（F-1 時序張力修補）

**方案選擇：D1（改 config 值）**，未選 D2（階段式 drain 邏輯）或 D3（調小 final timeout）。

**理由**：
1. **風險最低** — 不動 `main.py` / `stream_processor.py` 的 drain 邏輯，只改 config。符合本次 scope「Bug #16 主線」，不順手改其他機制。
2. **D2 超出本次 scope** — 階段式 drain 需拆 `pending wait → final timeout` 各自守門，動 [main.py:205](../../app/main.py#L205) `_stop_recording_async` 的 watchdog 邏輯，測試面更大，應獨立 bug 追。
3. **D3 不可行** — Step 0 log 顯示甲方實機 Gemma gen_time 78-89s，若 final_timeout 調小於此會常態性 timeout，反而觸發 fallback 而非真的 final。
4. **體感代價可接受** — 甲方按停止最壞等 190s（實際多半 drain 在 pending 完成時即結束，實測 happy path << 190s）。比 session 被誤 abort 成 UI 崩壞好太多。
5. **Obs-8「drain 期間 UI indicator」建議不順手補** — 動 UI 層（`dashboard_view.py` / `main.py` lifecycle），超出 Bug #16 scope。Director 提到可併，但我判斷獨立改動更清潔；若 Review Gate 認為必要可再開。

| 檔案 | 變更 |
|---|---|
| [config/default.yaml:28](../../config/default.yaml#L28) | `stop_drain_timeout_sec: 90 → 190`（60 pending + 120 final + 10 buffer）+ 註釋引用 Bug #16 修法 D |
| [doc/specs/data_schema.md:355](../../doc/specs/data_schema.md#L355) | §8 config 說明同步改 90→190，加「必須 ≥ pending_summary_wait_sec + final_summary_timeout_sec + 10s buffer」不變式 |
| [doc/specs/system_overview.md:175](../../doc/specs/system_overview.md#L175) | 異常路徑說明同步更新預設值 90→190 |

## 新增 tests（7 條，遠超 Director 要求的 4 條）

| test | 檔案 | 覆蓋 |
|---|---|---|
| `test_incremental_prompt_contains_json_schema` | [test_summarizer.py](../../tests/test_summarizer.py) | 修法 A 防回歸：prompt 須含四個英文 key + 「不可翻譯為中文」警示 |
| `test_summarizer_raises_empty_summary_error_on_empty_parse` | 同上 | 修法 B：Gemma 回中文 key JSON → raise EmptySummaryError |
| `test_empty_summary_error_not_raised_on_partial_content` | 同上 | 修法 B 邊界：任一欄位非空不 raise（避免誤殺） |
| `test_build_fallback_final_skips_empty_and_finds_non_empty_history` | [test_stream_processor.py](../../tests/test_stream_processor.py) | 修法 C 主線：V2/V3 空 → 複用 V1（非空） |
| `test_build_fallback_final_all_empty_returns_placeholder` | 同上 | 修法 C 邊界：history 全空 → 占位失敗文案 |
| `test_build_fallback_final_no_history_returns_placeholder` | 同上 | 修法 C 邊界：history 為 [] → 占位失敗文案 |
| `test_stop_drain_timeout_covers_pending_plus_final` | 同上 | 修法 D：讀 repo default config 驗 `drain >= pending + final + 10` |

## 自測結果

```bash
$ python -m pytest -m "not slow and not real_audio" -q
159 passed, 22 deselected, 11 warnings in 20.55s

$ python -m pytest tests/contract/test_flet_runtime_contract.py -v
16 passed in 0.88s
```

- **159 passed**（Director 要求 152+；新增 7 條皆綠，舊 152 條零回歸）
- **16 flet contract 全綠**
- 22 deselected 為 slow / real_audio 標記（預期）

## Scope 守護

- ✅ 只動 Director 派令的 4 檔：`app/core/summarizer.py` / `app/core/stream_processor.py` / `config/default.yaml` / 新增 test
- ✅ spec 同步：`data_schema.md` §8 + `system_overview.md` §4.2（因修法 D 改 config 值，須對齊 Single Source of Truth）
- ✅ 不動 `app/core/models.py`（`summary_history` 欄位原本就在）
- ✅ 不動 `app/main.py`（D 選 D1 不動 watchdog 邏輯）
- ✅ 不動 UI（Obs-8 indicator 不順手補）
- ✅ `[Bug#16-diag]` log 行保留（診斷資產，未來再重現可直接用）

## 預期 V8 甲方驗證

修法落地後甲方應可觀察到：
1. 長錄音（> 6 分鐘觸發 V2/V3）不再出現空摘要 UI
2. 若 Gemma 偶發回中文 key，會進 empty_parse fallback 複用 V1/V2 非空版本
3. 按停止到 review 切換不再因 watchdog 90s 早於 final timeout 而 abort
4. 體感：停止到 review 最壞 190s，happy path 不受影響

V8 觀察（非 bug）：Gemma 慢 / Flet GC 競態，請甲方記錄但不列阻塞。

## 待 Review Gate

- 不 push（紀律：過審察者 B 才 push）
- commit 暫不執行，等 Review PASS
- 預期 commit scope：
  - `app/core/summarizer.py`
  - `app/core/stream_processor.py`
  - `config/default.yaml`
  - `doc/specs/data_schema.md`（D 修法連帶）
  - `doc/specs/system_overview.md`（D 修法連帶）
  - `tests/test_summarizer.py`
  - `tests/test_stream_processor.py`
  - `doc/history/devlog_20260418_builderA_bug16_step0.md`（已存在）
  - `doc/history/devlog_20260418_builderA_bug16_step1.md`（本檔）

---

**碼農 A 報告 Director：Step 1 四件套完成 + 測試全綠 + devlog 封包。請派審察者 B 進行 Review Gate。**
