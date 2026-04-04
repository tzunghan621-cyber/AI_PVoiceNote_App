# AI_PVoiceNote_App — Agent 指引

> 個人會議指揮中心。語音轉錄 + RAG 知識庫校正 + 本地端 LLM 摘要。

---

## 專案概要

- **產品**：Desktop App（Flet），會議錄音轉錄、專有名詞校正、結構化摘要
- **核心特色**：三區塊工作區（逐字稿 / 會議重點 / Action Items），連動個人 Obsidian 知識庫
- **全程本地運算**：faster-whisper + Gemma 4（Ollama）+ ChromaDB
- **硬體基準**：Surface Pro 9（i7-1255U / 16GB / CPU only）

## 開發規範

遵循 [[AI協作開發規範]] v2.7-AgentTeam：
- P-S-C-V 強制工作流 + Review Gate
- 五角色 Agent 團隊（Director / Builder / Reviewer / Verifier / Researcher）
- **甲方 = 使用者**，**Director = Claude**

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
| 摘要推理 | Gemma 4 4B（Ollama） |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 |
| 向量資料庫 | ChromaDB |
| Desktop UI | Flet |
| 語言 | Python 3.11+ |

## 三階段使用模式

1. **養庫** — 從 Obsidian 知識庫提取重點建成 RAG 詞條
2. **使用 + 回饋** — 執行 Pipeline，審閱，標記校正品質
3. **優化** — 根據回饋增補/移除/調整詞條

## 關鍵 Specs

- [[system_overview]] — 系統架構、技術選型、Pipeline 流程
- [[data_schema]] — 資料結構、詞條格式、回饋格式、匯出格式
- [[ui_spec]] — Desktop App 介面規格
- [[team_roster]] — 團隊花名冊與職責
