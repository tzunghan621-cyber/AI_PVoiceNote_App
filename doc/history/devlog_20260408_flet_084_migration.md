---
title: Flet 0.84.0 全面 Migration — 一次修完 28 處
date: 2026-04-08
type: devlog
agent: 碼農（Builder）
status: 完成
tags: [devlog, flet, migration, breaking-change, v-phase, builder]
related:
  - "[[flet_0.84_migration_20260408]]"
  - "[[bug_report_flet_api_20260406]]"
  - "[[devlog_20260406_v_phase]]"
  - "[[devlog_20260408_filepicker_api]]"
---

# Flet 0.84.0 全面 Migration

> 對應研究：[[flet_0.84_migration_20260408]]
> 對應 Bug：[[bug_report_flet_api_20260406]]

## 背景

V Phase 已踩 4 顆雷，研究者系統性掃描出 28 個行號 / 6 個檔案需修。
本次依研究者報告**一次全部處理完**，避免逐顆雷重跑驗證循環。

## 修正清單

### A1. App 啟動 / 全域 API
- [app/main.py:177](app/main.py#L177)：`ft.app(target=main)` → `ft.run(main)`

### A2. Page API
- [dashboard_view.py:354](app/ui/dashboard_view.py#L354)：`page.on_resized` → `page.on_resize`
- [main_view.py](app/ui/main_view.py)：`MainView.self.page` → `self._page_ref`（避免將來改為 Container 子類別撞到 read-only property）

### Dialog 改 `show_dialog` / `pop_dialog`
- dashboard_view：會議資訊輸入、刪檔確認、刪除會議確認 — 共 3 處對話框、含 `setattr(dlg,'open',False)` lambda 也清掉
- terms_view：詞條 CRUD 對話框

### SnackBar 改 `show_dialog(SnackBar)`
- main.py：兩處 pipeline error
- dashboard_view._show_snackbar
- terms_view 匯入完成提示
- settings_view 儲存提示

### Padding：全改具名 `ft.Padding(...)`
- dashboard_view 7 處（73, 99, 275, 290, 534, 585, 600）
- main_view 2 處
- terms_view 2 處
- settings_view 1 處

### Alignment
- feedback_view.py / main_view.py：`ft.alignment.center` → `ft.Alignment.CENTER`

### Button 樣式：`color/bgcolor` 包進 `ButtonStyle`
- dashboard_view 殘餘 3 處（596, 734, 773）
- 順手把 idle「開始錄音」、live「停止錄音」、review「匯出 Markdown」也一併包進 ButtonStyle（這幾個技術上 Bug Report #2 同類，只是研究者掃描時優先列了 review/delete 那 3 個）

### Tabs 架構重構（最痛點）— [dashboard_view._apply_responsive_layout](app/ui/dashboard_view.py#L634)

舊：`Tab(text=, content=)` 把 panel 塞進去。
新：Tab 只負責 header（label），`Tabs.on_change` 切換外部 `Container.content` slot。

兩處重構：
- 中等視窗（兩欄）：右欄 `right_slot` Container + `right_tabs` 切換 summary/actions
- 窄視窗（單欄）：`single_slot` Container + `single_tabs` 切換 transcript/summary/actions

### 依賴鎖定
- [pyproject.toml](pyproject.toml)：`flet>=0.25.0` → `flet==0.84.0`，避免將來自動升到 1.0 又踩一輪雷

## 驗證

### Pytest
```
127 passed, 1 skipped, 1 warning in 26.89s
```
原 106 tests + 新增測試全綠。

### Smoke import
```
python -c "import app.main; import app.ui.dashboard_view; ..."
imports OK
```
全模組可成功 import，無語法/API 相容性錯誤。

> ⚠️ 真正的視窗冒煙測試（`python -m app.main` 開窗）需在有 GUI session 的環境跑，
> 本次在 headless agent 環境僅做 import-level smoke test。
> 建議 Verifier 接手跑 V Phase 第二輪，重點驗：開始錄音對話框、Tab 切換、SnackBar 顯示。

## 殘留 / 待後續

研究報告 §B3「低危」項目（IconButton.icon_color、Animation 等）目前 0.84 仍支援，
本次未動。若 V Phase 第二輪 Verifier 發現新雷再追補。

研究報告 §A6~A13 的 Icon/Badge/Checkbox/Card 等控制項本專案目前都未用到舊 API，
grep 確認無命中，跳過。

## 結語

研究者的盤點報告省了大量時間。28 個點位加上 Tabs 架構重構，半小時內全部處理完並通過 pytest。
下一步交給 Verifier 做 V Phase 第二輪實機驗證。
