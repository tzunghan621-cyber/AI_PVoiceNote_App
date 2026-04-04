---
title: 決策紀錄 — 角色分配與協作模式
date: 2026-04-04
type: decision
status: active
author: 大統領
tags:
  - decision
  - team
  - workflow
---

# 決策紀錄 — 角色分配與協作模式

## 背景

專案啟動時需確認開發規範中五角色（Director / Builder / Reviewer / Verifier / Researcher）的分配方式。

## 決策

甲方明確表示：**「Director 是你，我是甲方」**

| 角色 | 分配 | 說明 |
|------|------|------|
| 甲方 | 使用者 | 需求提出、最終簽核，不參與技術選型細節 |
| 大統領（Director） | Claude（主對話） | 統籌全部 Agent 角色、專案決策、文件管理 |
| 研究者（Researcher） | Claude（CLI-4） | 技術調查、競品研究 |
| Builder | 待命名（CLI-1） | 尚未啟動 |
| Reviewer | 待命名（CLI-2） | 尚未啟動 |
| Verifier | 待命名（CLI-3） | 尚未啟動 |

## 原因

甲方的定位是「出資方 + 需求方」，不是技術管理者。引述甲方態度：
- 技術選型：「這部份我不懂，直接依你的」
- 角色定位：「Director 是你，我是甲方」
- 文件管理：「我們專案要完全 doc 化，不依賴 memory 與對話上下文」

## 影響

- 大統領有權修改 `doc/specs/`，但重大變更仍需甲方簽核
- 甲方以「暫簽待確認」→「Pass」的方式簽核，不逐行審查
- 技術決策由大統領主導，甲方僅在影響使用體驗時介入

## 相關文件

- [[team_roster]] — 完整團隊名冊
- [[AI協作開發規範]] — 開發規範原文
