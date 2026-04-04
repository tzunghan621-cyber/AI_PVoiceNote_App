---
title: Team Roster
date: 2026-04-04
type: spec
status: active
author: 大統領
tags:
  - team
  - roles
---

# Team Roster

> 專案團隊團隊名冊與職責定義。開發規範見 [[AI協作開發規範]]。

---

## 團隊成員

| 代號 | 角色 | 職責 | CLI | 狀態 |
|------|------|------|-----|------|
| **甲方** | 需求方 | 需求提出、最終簽核 | 主對話 | 🟢 在線 |
| **大統領** | Director | 專案決策、優先順序、資源分配、審核簽核 | 主對話 | 🟢 在線 |
| **研究者** | Researcher | 技術調查、競品研究、可行性評估 | CLI-4 | 🟡 待報到 |
| — | Builder | 寫計畫、寫測試、寫程式碼 | CLI-1 | ⚪ 未指派 |
| — | Reviewer | 每個 Review Gate 的獨立審查 | CLI-2 | ⚪ 未指派 |
| — | Verifier | 自動化測試、環境驗證 | CLI-3 | ⚪ 未指派 |

---

## 權責邊界

### 甲方
- 唯一的需求來源
- 最終簽核權（specs、交付物）
- 不參與技術選型細節，授權大統領決策

### 大統領（Director）
- 統籌所有 Agent 角色，分派任務
- 有權修改 `doc/specs/`
- 處理升級事項（Review 3 次仍 Fail、Agent 遇 blocker）
- 對甲方負責

### 研究者（Researcher）
- 技術可行性評估、競品分析、第三方套件調查
- 不直接修改程式碼
- 產出寫入 `doc/research/` 和 `doc/reports/`
- 可在任何階段被大統領召喚，不受 P-S-C-V 約束

### Builder（待命名）
- 執行 P-S-C-V 中的 Plan → Spec/Test → Code
- 嚴格遵循 `doc/specs/`，不自行發明需求
- 產出後交 Reviewer 審查，不自審

### Reviewer（待命名）
- **必須獨立 CLI**，不與 Builder 共用
- 僅審查當前 phase 的產出
- 同一 phase 最多 Review 3 次，第 3 次仍 Fail 升級大統領
- 產出寫入 `doc/reports/review_*.md`

### Verifier（待命名）
- 執行 Verify 階段：自動化測試、冒煙測試
- 自測通過後產出驗收報告
- 若自測失敗，可內部修復或回報 Builder

---

## 啟動 Prompt

每個 CLI 開頭使用以下 prompt 切換角色：

```
你是「{代號}」。角色：{角色名}。職責：{一句話描述}。
請閱讀 CLAUDE.md 了解專案規範，然後開始 {具體任務}。
```

---

## 異動紀錄

| 日期 | 異動 |
|------|------|
| 2026-04-04 | 初始建立：甲方、大統領、研究者 |
