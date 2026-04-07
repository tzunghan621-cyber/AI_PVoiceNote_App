# 真實錄音測試素材目錄

把要跑端對端整合測試的真實會議錄音放在這個目錄。

## 支援格式

- `.wav`
- `.mp3`
- `.m4a`

## 注意事項

- **本目錄內檔案不入 git**（`.gitignore` 已排除），避免大檔污染 repo
- 測試會自動掃描所有支援格式並逐一跑完整 Pipeline
- 每個檔案都會跑：`AudioImporter → Transcriber → RAGCorrector → Summarizer → Exporter`
- 產出的 Markdown 會寫到 `pytest` 的 `tmp_path`，測試結束自動清理

## 執行方式

```bash
# 跑真實錄音測試（需 Ollama 在跑 + 模型已 pull + faster-whisper 模型可用）
python -m pytest -m real_audio -v -s

# 日常開發跳過
python -m pytest -m "not real_audio and not slow"
```

## 前置需求

- Ollama 已啟動：`ollama serve`
- 模型已下載：`ollama pull gemma4:e2b`
- faster-whisper 模型會在第一次執行時自動下載

## 建議的測試素材

- 短音檔（30 秒～1 分鐘）：快速 smoke test
- 中等音檔（5～10 分鐘）：模擬真實會議片段
- 含專有名詞的內容：驗證 RAG 校正命中
