# AI_PVoiceNote_App — Agent 指引

> 會議即時智能儀表板。開會時即時轉錄 + RAG 校正 + 週期性摘要，會後可編輯匯出。

---

## 專案概要

- **產品**：Desktop App（Flet），會議進行中即時顯示逐字稿/重點/Action Items
- **兩種模態**：會中（即時儀表板，唯讀）→ 會後（編輯工作區，可修改/回饋/匯出）
- **App 自有知識庫**：獨立的智能產品，透過 Claude Code 從 Obsidian 知識庫同步充實
- **全程本地運算**：faster-whisper + Gemma 4（Ollama）+ ChromaDB
- **硬體基準**：Surface Pro 9（i7-1255U / 16GB / CPU only）

## 核心架構概念

- **串流 Pipeline**：錄音、轉錄、校正同時進行，摘要每 3~5 分鐘週期性更新
- **知識庫分層**：App 自有知識庫（data/terms + ChromaDB）+ 外部 Obsidian 同步
- **三區塊**：逐字稿 / 會議重點 / Action Items，響應式佈局（三欄/兩欄/單欄）

## 開發規範

遵循 [[AI協作開發規範]] v2.7-AgentTeam：
- P-S-C-V 強制工作流 + Review Gate
- 五角色 Agent 團隊（Director / Builder / Reviewer / Verifier / Researcher）
- **甲方 = 使用者**，**大統領 = Director (Claude)**

## 角色與權責

詳見 [[team_roster]]。

- **甲方** = 使用者，負責需求提出和最終簽核
- **大統領** = Director (Claude)，統籌所有 Agent 角色
- `doc/specs/` 為 Single Source of Truth
- 不實作與 specs 矛盾的代碼，要改先更新 specs

## 文件體系

```
doc/
├── specs/      ⭐ Single Source of Truth
├── plans/      🚧 實作計畫
├── history/    👣 開發日誌
├── manuals/    📖 使用手冊
├── reports/    📊 Review / 測試報告
├── research/   🔬 技術研究
└── archive/    🗄️ 封存文件
```

所有 `.md` 檔必須：YAML frontmatter + `[[wikilink]]` 內部連結 + Obsidian 格式。

## 技術棧

| 層 | 技術 |
|---|---|
| 語音轉文字 | faster-whisper small |
| 摘要推理 | Gemma 4 E4B（Ollama，`gemma4:e4b`），降級 E2B |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 |
| 向量資料庫 | ChromaDB |
| Desktop UI | Flet |
| 語言 | Python 3.11+ |

## 三階段進化模式

1. **養庫** — 甲方透過 Claude Code 從 Obsidian 知識庫同步重點至 App 知識庫
2. **使用 + 回饋** — 開會即時使用，會後審閱回饋
3. **優化** — 根據回饋增補/移除/調整 App 知識庫詞條

## 關鍵 Specs

- [[system_overview]] — 系統架構、串流 Pipeline、知識庫架構
- [[data_schema]] — 資料結構、詞條格式、Session、回饋、匯出格式
- [[ui_spec]] — 即時儀表板（會中）+ 編輯工作區（會後）
- [[team_roster]] — 團隊名冊與職責
