---
title: Team Roster
date: 2026-04-05
type: spec
status: active
author: 大統領
tags:
  - team
  - roles
---

# Team Roster

> 專案團隊名冊與職務定義。開發規範見 [[AI協作開發規範]]。

---

## 組織架構

```
                    甲方
                  （需求方）
                     │
                     ▼
                   大統領
                 （Director）
                     │
        ┌────────┬───┴───┬────────┐
        ▼        ▼       ▼        ▼
     Builder  Reviewer Verifier 研究者
     (CLI-1)  (CLI-2)  (CLI-3)  (CLI-4)
```

---

## 職務表

| 職務 | 角色定位 | 核心職責 | 產出目錄 | CLI |
|------|---------|---------|---------|-----|
| **Director** | 總指揮 | 專案決策、優先順序、資源分配、審核簽核、對甲方負責 | `doc/specs/` | 主對話 |
| **Builder** | 實作者 | 執行 P-S-C 階段：寫計畫、寫測試、寫程式碼 | `doc/plans/`、原始碼 | CLI-1 |
| **Reviewer** | 審查者 | 每個 Review Gate 的獨立審查，確保產出符合 specs | `doc/reports/review_*.md` | CLI-2 |
| **Verifier** | 驗證者 | V 階段：自動化測試、環境驗證、冒煙測試 | 驗收報告 | CLI-3 |
| **Researcher** | 研究者 | 技術調查、競品研究、可行性評估、深度分析 | `doc/research/`、`doc/reports/` | CLI-4 |

---

## 職務詳述

### Director（大統領）
- 統籌所有 Agent 角色，分派任務
- 唯一有權修改 `doc/specs/`（或授權 Builder 修改）
- 處理升級事項（Review 3 次仍 Fail、Agent 遇 blocker）
- 審核 Reviewer 的報告，做 Pass/Fail 最終判定
- 對甲方負責，重大決策需甲方簽核

### Builder
- 執行 P-S-C-V 中的 **Plan → Spec/Test → Code** 三階段
- 嚴格遵循 `doc/specs/`，不自行發明需求
- 產出後交 Reviewer 審查，**不自審**
- 可與 Researcher 平行工作

### Reviewer
- **必須獨立 CLI**，不與 Builder 共用（自己寫自己審會有盲點）
- 僅審查當前 phase 的產出，不跨階段
- 同一 phase 最多 Review 3 次，第 3 次仍 Fail 升級大統領
- 審查標準：與 specs 一致性、完整性、品質、安全性

### Verifier
- 執行 P-S-C-V 中的 **Verify** 階段
- 跑自動化測試、環境冒煙測試、回歸測試
- 自測通過後產出驗收報告，列出需甲方手動驗證的項目
- 若自測失敗，可內部修復或回報 Builder

### Researcher（研究者）
- 技術可行性評估、第三方套件分析、競品調查
- 不直接修改程式碼，產出研究報告供 Director/Builder 決策
- 可在任何階段被大統領召喚，不受 P-S-C-V 流程約束

---

## 團隊名單

| 代號 | 職務 | 狀態 | 備註 |
|------|------|------|------|
| **甲方** | 需求方 | 🟢 在線 | 唯一需求來源，最終簽核權 |
| **大統領** | Director | 🟢 在線 | 主對話 CLI |
| **研究者** | Researcher | 🟢 已報到 | 已完成競品研究（[[competitive_analysis_20260404]]） |
| **碼農** | Builder | 🟢 在線 | CLI-1，執行中：S Phase（Phase 2+3） |
| **審察者** | Reviewer | 🟢 在線 | CLI-2，已完成 P Phase Review（2 輪） |
| **實驗者** | Verifier | ⚪ 待報到 | CLI-3 |

---

## P-S-C-V 流程與角色對應

```
P (Plan) → [Review Gate] → S (Spec/Test) → [Review Gate] → C (Code) → [Review Gate] → V (Verify)
 Builder     Reviewer        Builder          Reviewer       Builder      Reviewer      Verifier
  CLI-1       CLI-2           CLI-1            CLI-2          CLI-1        CLI-2          CLI-3
                                                                                           ↓
                                                                              甲方簽核（最終驗收）
```

> Researcher（CLI-4）可在任何階段平行運作，不阻塞主流程。
> 不是每個任務都需要全部角色。簡單 bug 可以只用 Builder + Reviewer。大統領判斷何時需要誰。

---

## 啟動 Prompt

每個 CLI 開頭使用以下 prompt 切換角色：

```
你是「{代號}」。角色：{職務}。職責：{一句話描述}。
請閱讀 CLAUDE.md 了解專案規範，然後開始 {具體任務}。
```

---

## 異動紀錄

| 日期 | 異動 |
|------|------|
| 2026-04-04 | 初始建立：甲方、大統領、研究者 |
| 2026-04-05 | 重構為職務表 + 名單分離；補完職務詳述與 P-S-C-V 對應圖 |
| 2026-04-05 | 甲方命名：碼農（Builder）、審察者（Reviewer）、實驗者（Verifier） |
| 2026-04-05 | 碼農、審察者報到上線；碼農完成 P Phase + S Phase（Phase 0+1）；審察者完成 P Phase Review（2 輪） |
