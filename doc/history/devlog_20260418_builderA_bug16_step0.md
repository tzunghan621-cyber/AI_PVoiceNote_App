---
title: 碼農 A devlog — Bug #16 Step 0 診斷（+F-2 交叉評估）
date: 2026-04-18
author: 碼農 A
bug: Bug #16（V2/V3 空摘要）
related:
  - "[[bug_report]]"
  - "[[devlog_20260418_reviewerB_retro_batch1]]"
  - "[[review_retro_batch1_20260418]]"
stage: Step 0（診斷）+ Step 0.5（F-2 交叉評估）— 完成
status: 等 Director 派 Step 1 修法令
---

# 碼農 A — Bug #16 Step 0 診斷 devlog

## 接令

Director 派工（2026-04-18，Review Gate 追溯後）：
- **Step 0**：甲方實機貼回 `[Bug#16-diag]` log → 判斷假說 A/B/C
- **Step 0.5（新增）**：同份 log 追 `_run_final_summary` fallback 路徑（F-2 交叉評估）
- 不動 `summarizer.py` 既有邏輯
- 修法階段（Step 1-4）必過 Review Gate

## 實機執行

- 指令：`python -u -m app.main > doc/reports/bug16_diag_run.log 2>&1`
- 流程：新會議 → 錄音 ~8 分鐘 → 按停止 → 關 App
- 輸出：[bug16_diag_run.log](../reports/bug16_diag_run.log) 569 行

## 判讀結果

### 三週期 Gemma response 對照

| 版本 | mode | prev_ver | raw keys | highlights_len | action_items | decisions | keywords |
|---|---|---|---|---|---|---|---|
| V1 | initial | None | `['highlights', 'action_items', 'decisions', 'keywords']` | 58 | 2 | 1 | 7 |
| V2 | initial | None | `['highlights', 'action_items', 'decisions', 'keywords']` | 193 | 1 | 4 | 10 |
| **V3** | **incremental** | **2** | **`['會議重點', 'Action Items', '決議事項']`** | **0** | **0** | **0** | **0** |

（V3 keys 在 log 裡顯示為亂碼 `�|ĳ���I` 是 Windows 終端 cp950 顯示問題；實際 Unicode 就是中文 key。）

### V3 raw response（[log line 420](../reports/bug16_diag_run.log)，反亂碼還原）

```json
{
  "會議重點": ["討論了使用 GENMAS 模型進行語音和文本處理...", ...],
  "Action Items": [{"內容": "...", "負責人": "...", "期限": "未明確", "優先級": "中"}],
  "決議事項": ["重新考慮模型的實用性...", ...]
}
```

Gemma 不但用中文 key，連 value type 都從 `string` 變成 `array of strings`，子欄位也中文化（`content` → `內容`）。**完全沒有 keywords 欄位**。

### 根因定位

對照 [summarizer.py:178-197](../../app/core/summarizer.py#L178-L197) `_build_incremental_prompt`：

```python
return f"""前次摘要結果：
重點：{prev_summary.highlights}
Action Items：{self._format_actions(prev_summary.action_items)}
決議：{prev_summary.decisions}
...
請更新會議重點、Action Items、決議事項。
回傳格式：JSON"""
```

**完全沒寫 JSON schema、沒指定英文 key、沒列 keywords 欄位。** 對比
[`_build_initial_prompt`](../../app/core/summarizer.py#L156-L176) V1/V2 用的版本明確列出
`highlights / action_items / decisions / keywords` 英文 key schema — 所以 V1/V2 keys 正確，
V3 一進 incremental 立刻崩。

### 假說判定

| 假說 | 成立 | 證據 |
|---|---|---|
| **C（prompt 設計）** | ✅ **主因** | `_build_incremental_prompt` 無 JSON schema，Gemma 用中文 key + array |
| **B（parser 太寬容）** | ✅ **協力** | [summarizer.py:130-140](../../app/core/summarizer.py#L130-L140) `parsed.get("highlights", "")` 找不到英文 key 吐空字串，`parsed is None` 的 T-1 fallback 接不到「parse 成功但 key 全錯」這種 case |
| A（Gemma 失控） | ❌ | V1/V2 highlights_len=58/193，內容貼近會議主題 |

## Step 0.5 — F-2 交叉評估結果

### 「沒機會跑 fallback」

- [log:508](../reports/bug16_diag_run.log) session 進 `processing`
- [log:523](../reports/bug16_diag_run.log) `Pipeline drain exceeded 90s — forcing cancel (watchdog)` 觸發
- [log:525](../reports/bug16_diag_run.log) session transition: processing → **aborted**（`abort_reason=stop_timeout`）
- [log:551](../reports/bug16_diag_run.log) `asyncio.exceptions.CancelledError` — `processor.run()` 被 watchdog cancel
- **`_run_final_summary` 完全沒被呼叫** — watchdog 在進 final 路徑前就把 run() cancel 了
- [log:541](../reports/bug16_diag_run.log) `Dashboard finalize UI failed` → [log:569](../reports/bug16_diag_run.log) `RuntimeError: An attempt to fetch destroyed session.` — Flet session 已 GC，finalize UI 渲染崩

### UI 顯示為何看得到 V1 內容

甲方截圖會議重點 58 字（「會議內容包含對使用GENMAS模型...」）= V1 highlights_len=58 內容。
推測：V2 成功 update_summary 後 UI 應已 re-render 成 193 字版，但 V3 empty 覆蓋時 UI update 路徑
碰上 abort + Flet session GC，UI 留在 **某次成功 render 的快照上**。這是 UI/lifecycle 議題，
**不是 Bug #16 主線**。

### F-2 guard 結論

本次 session 沒走 `_build_fallback_final`，**F-2 guard 的修補必要性未在本 log 直接驗證**。
但：
- 只要未來有 session 真走 final fallback 且 `session.summary` 是空 V3，F-2 bug 會重現
- F-2 guard 成本低（10 行內）、零副作用（舊行為是 `summary_history` 的特例 `n=1`）
- **列入 Step 1 修法清單**（深度防禦）

## Step 1 修法建議（等 Director 放行）

### 修法 A — `_build_incremental_prompt` 補完 schema（C 主因）

在 [summarizer.py:178-197](../../app/core/summarizer.py#L178-L197) 加上明確英文 key schema：

```python
return f"""前次摘要結果：
...（保留現有 context）...

請更新會議摘要，回傳 JSON，必須使用以下英文 key：
- "highlights": 會議重點摘要（字串，繁體中文內容）
- "action_items": 陣列，每項含 content, owner, deadline, priority, status
- "decisions": 字串陣列（決議事項）
- "keywords": 字串陣列（關鍵詞）

回傳格式：JSON"""
```

### 修法 B — summarizer EmptySummaryError + stream_processor `fallback_reason="empty_parse"`（B 協力）

- 在 [summarizer.py:130](../../app/core/summarizer.py#L130) 構造 SummaryResult 前判斷：
  若 `parsed.get("highlights", "").strip() == ""` **且** action_items/decisions/keywords 皆空
  → raise `EmptySummaryError`
- [stream_processor.py:_run_summary_async](../../app/core/stream_processor.py#L50) 捕捉 `EmptySummaryError`
  → 呼叫 `_build_fallback_final(session, "empty_parse")`（或週期版等價邏輯）

### 修法 C — F-2 `_build_fallback_final` guard（深度防禦）

[stream_processor.py:185-208](../../app/core/stream_processor.py#L185-L208) 改用
`session.summary_history` 向前找第一個非空版本：

```python
def _build_fallback_final(self, session, reason):
    for candidate in reversed(session.summary_history or []):
        if candidate.highlights.strip():
            return SummaryResult(
                version=candidate.version + 1,
                highlights=candidate.highlights,
                action_items=list(candidate.action_items),
                decisions=list(candidate.decisions),
                keywords=list(candidate.keywords),
                covered_until=candidate.covered_until,
                model=candidate.model,
                generation_time=0.0,
                is_final=True,
                fallback_reason=reason,
            )
    return SummaryResult(
        version=1,
        highlights="(摘要生成失敗，已保留逐字稿供手動整理)",
        is_final=True,
        fallback_reason=reason,
    )
```

## 附帶發現（非 Bug #16 主線，請 Director 裁決是否開新 bug）

1. **Gemma 慢 + 週期間 ReadTimeout 堆積**
   - 三次 gen_time：78.2s / 85.1s / 89.4s，接近 timeout 閾值
   - [log:173 / 313 / 437](../reports/bug16_diag_run.log) 各有一次 `httpcore.ReadTimeout`
     — 可能是下一週期 ollama call 搶 queue 或 Ollama server 側背壓
2. **watchdog 90s drain 被觸發 → session aborted 而非 ready**
   - session 沒正常走 `_run_final_summary`，影響 review mode 完整性
3. **Flet session GC 競態**
   - [log:541-569](../reports/bug16_diag_run.log) abort 後 UI finalize 崩（`An attempt to fetch destroyed session.`）

以上三點**不屬於 Bug #16 修法範圍**，請 Director 裁決：
- 開 Bug #19 / #20 / #21 分別追？
- 還是合成一張 "Session lifecycle robustness" 主題 bug？

## 紀律檢查

- ✅ Step 0 純診斷，未動 code
- ✅ summarizer.py +51 行 log 保留（診斷資產）
- ✅ devlog 記錄完整（raw response、假說判定、F-2 路徑、修法草稿）
- ⏸ 修法草稿**僅為文字 patch**，實動等 Step 1 派令 + Review Gate

## 待 Director 決策

1. Step 1 修法 A/B/C **一次打包** vs **拆三 PR**？
2. 附帶發現（Gemma 慢、watchdog abort、Flet GC）**新開 bug** vs **合併處理** vs **先擱置**？
3. Review Gate 執行者（審察者 A/B/C）？
