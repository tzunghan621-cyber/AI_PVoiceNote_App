---
title: 開發日誌 2026-04-18 — 碼農 B Bug #17 (FilePicker overlay) + Obs-5 (Mic Live 會中不動)
date: 2026-04-18
type: devlog
status: complete
author: 碼農 B（Builder B）
tags:
  - devlog
  - builder
  - bug-17
  - obs-5
  - flet
  - filepicker
  - lifecycle
  - v-phase-8-prep
related:
  - "[[bug_report_flet_api_20260406]]"
  - "[[flet_0.84_async_lifecycle_20260417]]"
  - "[[devlog_20260417_verifier_vphase7]]"
  - "[[devlog_20260417_builderB_bug15]]"
---

# 碼農 B — Bug #17 + Obs-5 — 2026-04-18

> 前一棒：實驗者 V Phase 第七輪（[[devlog_20260417_verifier_vphase7]]）
> 交派：大統領指派「Bug #17 FilePicker overlay + 順手查 Obs-5」
> 脈絡：[[bug_report_flet_api_20260406#Bug #17]] + V7 §「Mic Live 會中不動」

---

## Part 1 — Bug #17 三處 FilePicker 統一套 overlay pattern

### 根因回顧

Flet 0.84 的 `ft.FilePicker` 是 **service control**，`save_file` / `pick_files`
透過 session message channel dispatch 到 client（Windows 原生對話框）。
picker 必須先掛進 page tree（慣例：`page.overlay`）才能被 session 識別；
否則 `_invoke_method` 找不到 session 綁定 → `RuntimeError: Session closed`。

三處同樣 pattern 漏加 overlay：
- [app/ui/dashboard_view.py:990](app/ui/dashboard_view.py#L990) `_handle_export`（Bug #17 現場）
- [app/ui/dashboard_view.py:538](app/ui/dashboard_view.py#L538) `_handle_import_audio`（V4 標 PASS 的潛在風險）
- [app/ui/terms_view.py:157](app/ui/terms_view.py#L157) `_on_import` 詞條 YAML 匯入

### 修復（統一 pattern）

三處都改為 append → try/save_file(pick_files) → finally remove：

```python
picker = ft.FilePicker()
self._page_ref.overlay.append(picker)
self._page_ref.update()
try:
    path = await picker.save_file(...)   # 或 pick_files
    if path:
        # 業務邏輯
        ...
finally:
    if picker in self._page_ref.overlay:
        self._page_ref.overlay.remove(picker)
        self._page_ref.update()
```

`if picker in ...overlay` 的 guard 多一層防護：避免「某 path 提前已被移除」
重複 remove 炸 ValueError。

### diff 摘要

**[dashboard_view.py:990-1013](app/ui/dashboard_view.py#L990-L1013) `_handle_export`**
- 新增 `overlay.append(picker) → page.update()`
- `save_file` 包進 try；成功路徑寫檔＋刪音檔 dialog 原樣保留
- finally 內 remove + page.update()

**[dashboard_view.py:538-557](app/ui/dashboard_view.py#L538-L557) `_handle_import_audio`**
- 同 pattern；`pick_files` 成功路徑進 `_show_meeting_info_dialog` 原樣保留

**[terms_view.py:156-177](app/ui/terms_view.py#L156-L177) `_on_import`**
- 同 pattern；YAML 匯入 batch + SnackBar 反饋原樣保留

---

## Part 2 — Obs-5 Mic Live 會中不動

### 實驗者 V7 觀察

甲方進會中模式（按「開始錄音」）頂部 Mic Live 音量條**不更新**，dBFS 文字
卡 `-80`。V7 `Mic Test`（idle）PASS → 確認 Mic Test A1 fallback 好的；
但 **live 路徑**的音量 poll 沒跑起來。

### 5 分鐘內診斷 — 根因確定

閱讀 [main.py:98-107](app/main.py#L98-L107) `on_start_recording` 執行序：

```python
session = session_mgr.create(...)
dashboard.set_mode("live", session)       # ← ①
recorder = AudioRecorder(config)
dashboard.set_audio_recorder(recorder)    # ← ②
```

對照 [dashboard_view.py:411-425](app/ui/dashboard_view.py#L411-L425) `set_mode`
→ `_build_live()` → [dashboard_view.py:627](app/ui/dashboard_view.py#L627)
呼叫 `self._start_level_poll()`。

[dashboard_view.py:795-799](app/ui/dashboard_view.py#L795-L799) 舊 `_start_level_poll`：
```python
def _start_level_poll(self):
    if not self._audio_recorder:
        return                   # ← ① 此時 _audio_recorder 仍是 None → early return
    self._level_poll_running = True
```

步驟 ① 觸發 `_start_level_poll` 時 `_audio_recorder` 還是 `None`（Bug #15
的殘存 wiring 順序），poll 任務沒起 → `_level_poll_running = False`。

接著步驟 ② `set_audio_recorder(recorder)`：
```python
self._audio_recorder = recorder
if self._level_poll_running:      # ← False → 不進 if
    self._stop_level_poll()
    self._start_level_poll()
```

**`_level_poll_running` 永遠是 False**（步驟 ① 沒成功啟動）→ 注入 recorder 後
也不會重啟 poll → Mic Live 永遠 dead。

Bug #15 的 setter 只處理「正在跑 → 換 recorder 要重啟 binding」，**沒處理
「在 live mode 但從沒啟動過」的冷啟動情境**。V7 實機之所以暴露是因為
V7 是 Bug #15 修完後第一次真跑「會中模式」的完整 Mic Live，V6 靜態複核
時只推到「setter 已加」沒推到「order of call」這層。

### 修復

方案選擇：改動最窄 scope 放在 `set_audio_recorder`（不動 main.py 呼叫順序，
避免和碼農 A Bug #16 工作交鋒）：

```python
def set_audio_recorder(self, recorder):
    self._audio_recorder = recorder
    if self._mode == "live":                 # ← 新條件：只要 live mode
        if self._level_poll_running:
            self._stop_level_poll()
        self._start_level_poll()             # ← 冷啟動也走
```

語意：dashboard 知道自己 mode；外部注入 recorder 後，只要 mode 允許就
保證 Mic Live poll 跑。不論 recorder 是「新換」還是「第一次拿到」。

Docstring 內補完整 root cause（Obs-5 脈絡），避免未來再動 wiring 時踩回這坑。

### 同 PR 決策 — 5 分鐘內修完

Obs-5 屬 wiring 類簡單修（1 行邏輯改），診斷確定 + 改動極小，**合併進本 PR**。
不另開 Bug #18。

---

## Part 3 — Contract test T-F10（L4a 框架服務使用契約）

### 設計

[tests/contract/test_flet_runtime_contract.py](tests/contract/test_flet_runtime_contract.py)
新增 `TestFilePickerOverlayContract` class：

- **`test_every_filepicker_usage_mounts_to_overlay`**：grep-based — 掃 app/ 下
  所有 `ft.FilePicker()` 建立處，同一函式內必含 `overlay.append`。
- **`test_every_filepicker_usage_removes_from_overlay`**：搭配 append 必含
  `overlay.remove`（finally block）— 防 overlay 洩漏。

**實作細節**：`_iter_filepicker_sites()` 以 regex 切函式邊界（`def` 起到下一個
`def`/`class` 止），比直接 `"overlay.append" in full_text` 嚴格 — 避免同檔某
function 有 FilePicker 沒加 overlay、另一個 function 有 overlay 呼叫，被全檔
grep 誤通過。

### 覆蓋範圍

```
app/ui/dashboard_view.py::_handle_export        ✅
app/ui/dashboard_view.py::_handle_import_audio  ✅
app/ui/terms_view.py::_on_import                ✅
```

三處全被抓到且全通過。未來任何新 FilePicker 使用漏 overlay → test fail 擋住。

### L4a 缺口意義

實驗者 V7 §11 反思：現有 T-F1（Flet API 簽章）、T-F8（BaseControl.page
property lifecycle）屬 **L2/L3**（API + lifecycle 契約），沒有 **L4a 框架服
務使用契約**（「要怎麼用才 work」）。T-F10 就是此層的首次落地測試。模式
可推廣：Dialog / SnackBar / BottomSheet 若未來也是 service control pattern，
類似 grep test 可擴充。

---

## 自測結果

### Fast tests (not slow, not real_audio)

```
148 passed, 22 deselected, 11 warnings in 15.90s
```

對比 V7 baseline 146 → +2（T-F10 兩個新 case）。無 regression。

### Integration tests

```
6 passed, 11 warnings in 7.84s
```

含 `test_main_on_start_recording_calls_set_audio_recorder` — Bug #15 wiring
smoke 仍綠。

### Contract subset（重跑獨立確認）

```
tests/contract/test_flet_runtime_contract.py ............ [100%]
12 passed in 0.93s
```

V7 baseline 10 → +2（T-F10）。

---

## 實機驗證 — 委交實驗者 V Phase 第八輪

本輪**無實機驗證**（碼農本分）；以下三項留給 V8 重驗：

### V8 重驗遞交清單

1. **Bug #17 主現場 — 匯出 Markdown**
   - 步驟：甲方完成錄音 → review → 按「匯出 Markdown」
   - 期望：Windows 存檔對話框彈出 → 選路徑 → .md 寫盤 → 「是否刪除原音檔」dialog
   - 失敗指標：無對話框 / RuntimeError: Session closed / 無 hover 色變

2. **Bug #17 順手修 — 匯入音檔**
   - 步驟：idle 按「📁 匯入音檔」
   - 期望：Windows 開檔對話框彈出 → 選 .wav/.mp3/.m4a → 會議資訊 dialog → 進 live
   - 說明：V4 標 PASS 但 V7 未重測；此輪新掛 overlay，確保 V7 若回測不會炸

3. **Bug #17 詞條 YAML 匯入**
   - 步驟：進「詞條」頁 → 按匯入 YAML
   - 期望：Windows 開檔對話框彈出 → 選 .yaml/.yml → SnackBar 顯示「已匯入 N 筆詞條」

4. **Obs-5 — Mic Live 會中音量條**
   - 步驟：idle 按「開始錄音」→ 進 live mode
   - 期望：頂部 🎤 音量條**隨聲音變化**（四級顏色依 ui_spec §2.5）+ dBFS 文字脫離 -80
   - 失敗指標：音量條 value=0 / dBFS 文字卡 -80 / 靜音 3+ 秒無 SnackBar
   - （附屬）靜音超過 3 秒應彈 SnackBar「麥克風訊號極弱」

5. **回歸 — 錄音停止 + 轉 review**
   - 步驟：錄音 5+ 分鐘 → 停止
   - 期望：V Phase 7 的 I1-I7 全 PASS 不退回；Mic Live 在 `set_mode("review")` 時停止 poll（`_level_poll_running = False`）

---

## 守本分

- ✅ 修 Bug #17 三處 + 加 T-F10 contract test（派工範圍內）
- ✅ 診斷 Obs-5 + 修復（5 分鐘內 + 改動極小，合併同 PR）
- ✅ 不動 ui_spec §2.5 Mic Live（現有 spec 與修復方向相容）
- ✅ 不動 Bug #16 相關檔（碼農 A 處理中）
- ❌ 不做實機驗證（委交實驗者 V8）
- ❌ 不處理 Obs-8「停止要等很久 UI 無反饋」stopping indicator（bug report §Bug #17 附帶建議提的，但超出本派工單核心；若大統領要求再開單獨一棒）

## 交棒

| 對象 | 請求 |
|---|---|
| **大統領** | 驗 2-3 commit split + 決策是否同 PR 順手加 Obs-8 stopping indicator（建議：不加，讓 Obs-8 獨立一棒避免改動擴散） |
| **實驗者** | 進 V Phase 第八輪 — 跑上面 5 項重驗清單；特別留意 Obs-5 修完後 idle → live → review → idle 循環的 poll lifecycle |
| **甲方** | 靜候 V8 實機驗證；準備再跑 5+ 分鐘錄音 + 匯出 Markdown 確認 Bug #17 修復 |
| **碼農 A** | 繼續 Bug #16 Gemma 空摘要診斷；本 PR 無 main.py 動作、不交疊 |
| **研究者** | 待命；若 T-F10 模式可推廣到 Dialog / SnackBar（其他 service controls）可補一份 L4a 清單研究 |

---

## Commit 切分

1. `fix: Bug #17 FilePicker 三處統一 overlay mount (L4a 框架服務使用契約)`
2. `fix: Obs-5 Mic Live 會中不動 — set_audio_recorder live-mode 冷啟動 poll`
3. `test: T-F10 contract test — 守護 FilePicker 必須 overlay mount`
