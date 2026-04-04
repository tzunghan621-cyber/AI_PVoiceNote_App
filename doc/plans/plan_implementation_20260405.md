---
title: 實作計畫
date: 2026-04-05
type: plan
status: revised
author: 碼農
reviewer: 審察者（待 Re-review）
revision: 修正 C-1/M-1/M-2/M-3/M-4 + m-1/T-1/T-2/T-3/R-1
tags:
  - implementation
  - plan
  - p-phase
---

# 實作計畫

> 碼農 P 階段產出。依據 [[system_overview]]、[[data_schema]]、[[ui_spec]] 規格。
> 競品差異化參考：[[competitive_analysis_20260404]]

---

## 1. 實作分期與依賴關係

### 依賴圖

```
Phase 0: 基礎建設
  config_manager ──┐
  data_models ─────┤（無外部依賴）
  pyproject.toml ──┘

Phase 1: 獨立核心模組（互不依賴，可平行開發）
  ├── knowledge_base（需 ChromaDB + sentence-transformers）
  ├── transcriber（需 faster-whisper）
  ├── audio_recorder（需 sounddevice/pyaudio）
  ├── audio_importer（需 pydub）
  └── feedback_store（純 JSON 讀寫）

Phase 2: 組合模組（依賴 Phase 1）
  ├── rag_corrector ← knowledge_base + data_models
  ├── summarizer ← Ollama + data_models
  ├── exporter ← data_models
  └── session_manager ← data_models

Phase 3: 管線整合
  └── stream_processor ← audio_recorder + transcriber + rag_corrector
                         + summarizer + session_manager

Phase 4: UI — 基礎框架與核心頁面
  ├── main_view（導航框架 + 狀態列）
  ├── dashboard_view（即時儀表板 + 會後編輯）
  └── settings_view

Phase 5: UI — 輔助頁面 + 打包
  ├── terms_view（詞條管理）
  ├── feedback_view（回饋統計）
  └── 打包為 .exe
```

### 每期預估模組數與重點

| Phase | 名稱 | 模組數 | 重點 |
|-------|------|--------|------|
| 0 | 基礎建設 | 3 | 專案骨架、資料模型、設定管理 |
| 1 | 獨立核心 | 5 | 每個模組可獨立單測 |
| 2 | 組合模組 | 4 | 模組間串接，整合測試 |
| 3 | 管線整合 | 1 | StreamProcessor 串流協調 |
| 4 | UI 核心 | 3 | 即時儀表板（核心差異化功能） |
| 5 | UI 輔助 + 打包 | 3 | 詞條管理、回饋統計、.exe |

---

## 2. 各模組核心邏輯偽代碼

### Phase 0

#### 0-1. 資料模型（`app/core/models.py`）

> 新增 `models.py`，specs 未列但所有 dataclass 需要集中定義。

```python
# 依 data_schema 定義所有 dataclass
# TranscriptSegment, Correction, CorrectedSegment,
# ActionItem, SummaryResult, Participant, Session,
# UserEdits, FeedbackEntry, SessionFeedback

@dataclass
class TranscriptSegment:
    index: int; start: float; end: float
    text: str; confidence: float; chunk_id: int

@dataclass
class Correction:
    segment_index: int; original: str; corrected: str
    term_id: str; similarity: float

@dataclass
class CorrectedSegment:
    index: int; start: float; end: float
    original_text: str; corrected_text: str
    corrections: list[Correction]

@dataclass
class ActionItem:
    id: str; content: str; owner: str | None
    deadline: str | None; source_segment: int
    status: str; priority: str; note: str | None
    user_edited: bool     # [M-4] True 時 AI 週期更新不覆蓋
    created: str; updated: str

@dataclass
class SummaryResult:
    version: int; highlights: str
    action_items: list[ActionItem]; decisions: list[str]
    keywords: list[str]; covered_until: int
    model: str; generation_time: float; is_final: bool

# Session, Participant, UserEdits, FeedbackEntry, SessionFeedback 同理
```

#### 0-2. ConfigManager（`app/data/config_manager.py`）

```python
class ConfigManager:
    def __init__(self, config_path="config/default.yaml"):
        self._config = yaml.safe_load(open(config_path))

    def get(self, dotted_key: str, default=None):
        # "whisper.model" → self._config["whisper"]["model"]
        keys = dotted_key.split(".")
        val = self._config
        for k in keys:
            val = val.get(k, default) if isinstance(val, dict) else default
        return val

    def set(self, dotted_key: str, value):
        # 寫入記憶體 + 回寫 YAML
        ...

    def save(self):
        yaml.dump(self._config, open(self._path, "w"))
```

#### 0-3. 專案骨架

- `pyproject.toml`：定義依賴（faster-whisper, chromadb, flet, sentence-transformers, ollama, pyyaml, sounddevice, pydub）
- `requirements.txt`：同步產出
- `config/default.yaml`：依 [[data_schema#8. 設定檔]] 產出
- 所有 `__init__.py`

---

### Phase 1：獨立核心模組

#### 1-1. KnowledgeBase（`app/core/knowledge_base.py`）

```python
class KnowledgeBase:
    def __init__(self, config: ConfigManager):
        self.terms_dir = config.get("knowledge_base.terms_dir")
        self.chroma = chromadb.PersistentClient(path=config.get("knowledge_base.chroma_dir"))
        self.collection = self.chroma.get_or_create_collection("terms")
        self.embedder = SentenceTransformer(config.get("embedding.model"))
        self._load_all_terms()

    def _load_all_terms(self):
        # 掃描 terms_dir 下所有 .yaml，載入為 dict
        # 同步向量索引：若 chroma 中缺少/過期則 upsert
        for yaml_file in glob(terms_dir / "*.yaml"):
            term = yaml.safe_load(open(yaml_file))
            embed_text = f"{term['term']} {' '.join(term['aliases'])} {term.get('context','')}"
            self.collection.upsert(
                ids=[term["id"]],
                documents=[embed_text],
                metadatas=[{"term": term["term"], "category": term.get("category","")}]
            )
            self._terms[term["id"]] = term

    def query(self, text: str, top_k=5) -> list[dict]:
        # 向量查詢，回傳最相似的詞條
        results = self.collection.query(
            query_embeddings=[self.embedder.encode(text).tolist()],
            n_results=top_k
        )
        return [self._terms[tid] for tid in results["ids"][0]]

    def add_term(self, term_dict: dict): ...
    def update_term(self, term_id: str, updates: dict): ...
    def delete_term(self, term_id: str): ...
    def get_term(self, term_id: str) -> dict: ...
    def list_terms(self, category: str = None) -> list[dict]: ...
    def update_stats(self, term_id: str, field: str, increment: int = 1): ...
    def import_yaml_batch(self, yaml_content: str) -> int: ...
```

#### 1-2. Transcriber（`app/core/transcriber.py`）

```python
class Transcriber:
    def __init__(self, config: ConfigManager):
        self.model = WhisperModel(
            config.get("whisper.model"),
            device=config.get("whisper.device"),
            compute_type="int8"  # CPU 優化
        )
        self.language = config.get("whisper.language")
        self._segment_counter = 0

    async def transcribe_chunk(self, audio_data: np.ndarray, chunk_id: int) -> list[TranscriptSegment]:
        # 呼叫 faster-whisper 轉錄單一音訊區塊
        segments, info = self.model.transcribe(
            audio_data, language=self.language,
            vad_filter=True  # 過濾靜音
        )
        result = []
        for seg in segments:
            ts = TranscriptSegment(
                index=self._segment_counter,
                start=seg.start, end=seg.end,
                text=seg.text.strip(),
                confidence=seg.avg_logprob,  # 轉換為 0-1
                chunk_id=chunk_id
            )
            self._segment_counter += 1
            result.append(ts)
        return result

    def reset(self):
        self._segment_counter = 0
```

#### 1-3. AudioRecorder（`app/core/audio_recorder.py`）

> **[C-1 修正]** 雙層串流設計：小區塊（`transcribe_chunk_sec`=10 秒）即時送 Whisper，
> 大區塊（`audio_chunk_duration_sec`=600 秒）背景暫存 WAV。兩層獨立運作。

```python
class AudioRecorder:
    def __init__(self, config: ConfigManager):
        self.sample_rate = config.get("audio.sample_rate")
        self.channels = config.get("audio.channels")
        self.temp_dir = config.get("audio.temp_dir")
        # 雙層參數
        self.transcribe_chunk_sec = config.get("streaming.transcribe_chunk_sec")  # 10 秒，送 Whisper
        self.save_chunk_sec = config.get("streaming.audio_chunk_duration_sec")    # 600 秒，暫存 WAV
        self._recording = False
        self._audio_queue = asyncio.Queue()
        self._temp_paths: list[str] = []

    def _audio_callback(self, indata, frames, time_info, status):
        # sounddevice 回呼，把音訊資料放入 queue
        self._audio_queue.put_nowait(indata.copy())

    async def start(self) -> AsyncIterator[np.ndarray]:
        """
        啟動麥克風錄音。
        - 每 transcribe_chunk_sec 秒 yield 一個小區塊給 StreamProcessor/Transcriber（即時轉錄）
        - 每 save_chunk_sec 秒在背景存一個大區塊 WAV 到 temp_dir（磁碟暫存）
        """
        self._recording = True
        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=self._audio_callback
        )
        stream.start()

        transcribe_buffer = []   # 小區塊 buffer（送 Whisper）
        save_buffer = []         # 大區塊 buffer（存 WAV）
        save_chunk_id = 0

        try:
            while self._recording:
                data = await self._audio_queue.get()
                transcribe_buffer.append(data)
                save_buffer.append(data)

                # 層 1：每 transcribe_chunk_sec 秒 yield 給 Transcriber
                if self._buffer_duration(transcribe_buffer) >= self.transcribe_chunk_sec:
                    yield np.concatenate(transcribe_buffer)
                    transcribe_buffer = []

                # 層 2：每 save_chunk_sec 秒暫存 WAV
                if self._buffer_duration(save_buffer) >= self.save_chunk_sec:
                    self._save_temp(np.concatenate(save_buffer), save_chunk_id)
                    save_buffer = []
                    save_chunk_id += 1
        finally:
            stream.stop()
            # flush 殘餘
            if transcribe_buffer:
                yield np.concatenate(transcribe_buffer)
            if save_buffer:
                self._save_temp(np.concatenate(save_buffer), save_chunk_id)

    async def stop(self):
        self._recording = False

    def _save_temp(self, audio: np.ndarray, chunk_id: int):
        # 存 WAV 到 temp_dir，記錄路徑
        path = Path(self.temp_dir) / f"chunk_{chunk_id:04d}.wav"
        # scipy.io.wavfile.write(path, self.sample_rate, audio)
        self._temp_paths.append(str(path))

    def _buffer_duration(self, buffer: list) -> float:
        total_samples = sum(b.shape[0] for b in buffer)
        return total_samples / self.sample_rate

    def get_temp_paths(self) -> list[str]:
        return self._temp_paths
```

#### 1-4. AudioImporter（`app/core/audio_importer.py`）

> **[C-1 連動修正]** yield 單位改用 `transcribe_chunk_sec`（10 秒），
> WAV 暫存改用 `audio_chunk_duration_sec`（600 秒），與 AudioRecorder 一致。

```python
class AudioImporter:
    def __init__(self, config: ConfigManager):
        self.sample_rate = config.get("audio.sample_rate")
        self.transcribe_chunk_sec = config.get("streaming.transcribe_chunk_sec")  # 10 秒，送 Whisper
        self.save_chunk_sec = config.get("streaming.audio_chunk_duration_sec")    # 600 秒，存 WAV
        self.temp_dir = config.get("audio.temp_dir")
        self._temp_paths: list[str] = []

    async def import_file(self, file_path: str) -> AsyncIterator[np.ndarray]:
        # 載入音檔 → 統一為 16kHz mono
        audio = AudioSegment.from_file(file_path)
        audio = audio.set_frame_rate(self.sample_rate).set_channels(1)
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0

        transcribe_samples = int(self.transcribe_chunk_sec * self.sample_rate)
        save_samples = int(self.save_chunk_sec * self.sample_rate)
        save_chunk_id = 0

        for i in range(0, len(samples), transcribe_samples):
            # 每 transcribe_chunk_sec yield 一段給 Pipeline
            yield samples[i:i+transcribe_samples]

            # 每 save_chunk_sec 暫存一段 WAV
            chunk_end = i + transcribe_samples
            if chunk_end % save_samples < transcribe_samples or chunk_end >= len(samples):
                wav_start = save_chunk_id * save_samples
                self._save_temp(samples[wav_start:min(chunk_end, len(samples))], save_chunk_id)
                save_chunk_id += 1

    def get_duration(self, file_path: str) -> float: ...
    def _save_temp(self, audio: np.ndarray, chunk_id: int): ...
    def get_temp_paths(self) -> list[str]:
        return self._temp_paths
```

#### 1-5. FeedbackStore（`app/data/feedback_store.py`）

```python
class FeedbackStore:
    def __init__(self, config: ConfigManager):
        self.feedback_dir = config.get("feedback.dir")

    def save(self, session_feedback: SessionFeedback):
        path = Path(self.feedback_dir) / f"{session_feedback.session_id}.json"
        path.write_text(json.dumps(asdict(session_feedback), ensure_ascii=False, indent=2))

    def load(self, session_id: str) -> SessionFeedback | None: ...

    def list_all(self) -> list[SessionFeedback]:
        # 載入全部回饋，用於統計分析
        ...

    def get_term_stats(self) -> dict[str, dict]:
        # 彙整每個 term_id 的回饋統計
        # 回傳: {term_id: {correct: N, wrong: N, missed: N}}
        all_fb = self.list_all()
        stats = defaultdict(lambda: {"correct": 0, "wrong": 0, "missed": 0})
        for fb in all_fb:
            for entry in fb.entries:
                if entry.term_id:
                    stats[entry.term_id][entry.type] += 1
        return stats

    def get_high_frequency_misses(self, threshold=3) -> list[str]:
        # 回傳高頻遺漏的文字（用於 auto_suggest 候選）
        ...
```

---

### Phase 2：組合模組

#### 2-1. RAGCorrector（`app/core/rag_corrector.py`）

```python
class RAGCorrector:
    def __init__(self, knowledge_base: KnowledgeBase, config: ConfigManager):
        self.kb = knowledge_base
        self.similarity_threshold = 0.6  # 低於此分數不校正

    def correct(self, segment: TranscriptSegment) -> CorrectedSegment:
        corrections = []
        corrected_text = segment.text

        # 對 segment 文字查詢知識庫
        candidates = self.kb.query(segment.text, top_k=5)

        for candidate in candidates:
            term = candidate
            # 檢查 aliases 是否出現在文字中（模糊比對）
            for alias in term["aliases"]:
                if self._fuzzy_match(alias, segment.text):
                    # 計算相似度
                    sim = self._compute_similarity(alias, term["term"])
                    if sim >= self.similarity_threshold:
                        # 替換
                        corrected_text = corrected_text.replace(alias, term["term"])
                        corrections.append(Correction(
                            segment_index=segment.index,
                            original=alias,
                            corrected=term["term"],
                            term_id=term["id"],
                            similarity=sim
                        ))
                        # 更新統計
                        self.kb.update_stats(term["id"], "hit_count")
                        self.kb.update_stats(term["id"], "correction_count")

        return CorrectedSegment(
            index=segment.index,
            start=segment.start, end=segment.end,
            original_text=segment.text,
            corrected_text=corrected_text,
            corrections=corrections
        )

    def _fuzzy_match(self, alias: str, text: str) -> bool: ...
    def _compute_similarity(self, alias: str, term: str) -> float: ...
```

#### 2-2. Summarizer（`app/core/summarizer.py`）

```python
class Summarizer:
    def __init__(self, config: ConfigManager):
        self.model = config.get("ollama.model")
        self.base_url = config.get("ollama.base_url")
        self._version = 0

    async def generate(
        self,
        segments: list[CorrectedSegment],
        previous_summary: SummaryResult | None = None,
        participants: list[Participant] = None,
        is_final: bool = False
    ) -> SummaryResult:
        start_time = time.time()

        # 組裝 prompt
        if previous_summary:
            # [m-1 修正] 用 index 過濾而非 list 切片，避免 segment 跳號時切片錯位
            new_segments = [s for s in segments if s.index > previous_summary.covered_until]
            prompt = self._build_incremental_prompt(
                new_segments,
                previous_summary,
                participants
            )
        else:
            prompt = self._build_initial_prompt(segments, participants)

        if is_final:
            prompt += "\n這是最終摘要，請全面整合所有內容。"

        # 呼叫 Ollama
        response = await self._call_ollama(prompt)

        # 解析回應為結構化結果
        self._version += 1
        return self._parse_response(
            response, self._version,
            covered_until=segments[-1].index,
            generation_time=time.time() - start_time,
            is_final=is_final,
            previous_actions=previous_summary.action_items if previous_summary else []
        )

    def _build_incremental_prompt(self, new_segments, prev_summary, participants):
        # 依 system_overview 4.2 增量策略
        transcript = "\n".join(f"[{s.start:.0f}s] {s.corrected_text}" for s in new_segments)
        return f"""前次摘要結果：
重點：{prev_summary.highlights}
Action Items：{self._format_actions(prev_summary.action_items)}
決議：{prev_summary.decisions}
與會人員：{self._format_participants(participants)}

新增逐字稿段落：
{transcript}

請更新會議重點、Action Items、決議事項。
保留仍然有效的項目，新增或修改有變化的項目。
回傳格式：JSON"""

    async def _call_ollama(self, prompt: str) -> str:
        # HTTP POST to Ollama /api/generate
        ...

    def _parse_response(self, response, version, **kwargs) -> SummaryResult: ...
    def _build_initial_prompt(self, segments, participants): ...
    def _check_hierarchical_needed(self, segments) -> bool:
        # 判斷是否需要階層式摘要（超過 context window）
        ...

    def reset(self):
        self._version = 0
```

#### 2-3. SessionManager（`app/core/session_manager.py`）

```python
class SessionManager:
    def __init__(self, config: ConfigManager):
        self.sessions_dir = config.get("sessions.dir")

    def create(self, title: str, audio_source: str,
               participants: list[Participant] = None) -> Session:
        return Session(
            id=str(uuid4()),
            title=title or f"會議 {datetime.now():%Y-%m-%d %H:%M}",
            created=datetime.now().isoformat(),
            ended=None,
            participants=participants or [],
            mode="live", status="recording",
            audio_source=audio_source,
            audio_paths=[], audio_duration=0.0,
            segments=[], summary_history=[],
            summary=None, user_edits=None,
            feedback=None, export_path=None
        )

    def add_segment(self, session: Session, segment: CorrectedSegment):
        session.segments.append(segment)

    def update_summary(self, session: Session, summary: SummaryResult):
        session.summary_history.append(summary)
        session.summary = summary

    def end_recording(self, session: Session):
        session.ended = datetime.now().isoformat()
        session.status = "processing"

    def mark_ready(self, session: Session):
        session.status = "ready"
        session.mode = "review"

    def save_user_edits(self, session: Session, edits: UserEdits):
        session.user_edits = edits

    def save(self, session: Session):
        path = Path(self.sessions_dir) / f"{session.id}.json"
        path.write_text(json.dumps(asdict(session), ensure_ascii=False, indent=2))

    def delete_audio(self, session: Session):
        """[M-1] UI 確認後呼叫，刪除暫存音檔"""
        for p in session.audio_paths:
            Path(p).unlink(missing_ok=True)
        session.audio_paths = []

    def load(self, session_id: str) -> Session: ...
    def list_sessions(self) -> list[dict]: ...  # 輕量清單（id, title, date, status）
```

#### 2-4. Exporter（`app/core/exporter.py`）

> **[M-1 修正]** Exporter 只負責匯出 Markdown，不主動刪除音檔。
> 音檔刪除由 UI 層在匯出成功後彈出確認對話框（[[ui_spec#7. 對話框與通知]]），
> 使用者選擇 [刪除] 時才呼叫 `SessionManager.delete_audio(session)`。

```python
class Exporter:
    def export(self, session: Session, output_path: str):
        """匯出 Markdown，不刪除音檔"""
        md = self._build_markdown(session)
        Path(output_path).write_text(md, encoding="utf-8")
        session.status = "exported"
        session.export_path = output_path
        # 音檔刪除交由 UI 確認後呼叫 SessionManager.delete_audio()

    def _build_markdown(self, session: Session) -> str:
        # 依 data_schema#7 匯出格式
        # 優先使用 user_edits，其次 AI summary
        highlights = session.user_edits.highlights_edited \
            if session.user_edits and session.user_edits.highlights_edited \
            else (session.summary.highlights if session.summary else "")

        decisions = session.user_edits.decisions_edited \
            if session.user_edits and session.user_edits.decisions_edited \
            else (session.summary.decisions if session.summary else [])

        # 組裝 frontmatter + 各區塊
        ...
        # 逐字稿區塊：有校正的段落標記刪除線
        for seg in session.segments:
            if seg.corrections:
                # ~~original~~ → **corrected**（校正：term_id）
                ...
            else:
                # 純文字
                ...
```

---

### Phase 3：管線整合

#### 3-1. StreamProcessor（`app/core/stream_processor.py`）

> **[C-1 連動修正]** audio_source 現在每 10 秒 yield 一個小區塊（非 10 分鐘）。
> 每個小區塊即時轉錄→校正→送 UI，摘要仍依週期觸發。
> **[M-4 修正]** on_summary 傳入 user_edited 保護資訊，供 UI merge 使用。

```python
class StreamProcessor:
    """串流管線控制器 — 協調 錄音→轉錄→校正→週期摘要"""

    def __init__(self, transcriber, rag_corrector, summarizer,
                 session_manager, config):
        self.transcriber = transcriber
        self.corrector = rag_corrector
        self.summarizer = summarizer
        self.session_mgr = session_manager
        self.summary_interval = config.get("streaming.summary_interval_sec")
        self.min_new_segments = config.get("streaming.summary_min_new_segments")
        self._summarizing = False  # [R-1] 防止 Whisper 與 Gemma 同時 CPU 推理

        # 事件回呼（UI 綁定用）
        self.on_segment: Callable[[CorrectedSegment], None] = None
        self.on_summary: Callable[[SummaryResult], None] = None
        self.on_status_change: Callable[[str], None] = None

    async def run(self, audio_source: AsyncIterator[np.ndarray],
                  session: Session):
        """
        主迴圈：消費音訊串流（每 10 秒一個小區塊），驅動整條 pipeline。
        audio_source 由 AudioRecorder 或 AudioImporter 提供。
        """
        last_summary_time = time.time()
        segments_since_summary = 0
        chunk_id = 0

        async for audio_chunk in audio_source:
            # 1. 轉錄（每 10 秒小區塊即時轉錄）
            new_segments = await self.transcriber.transcribe_chunk(
                audio_chunk, chunk_id
            )
            chunk_id += 1

            # 2. 逐條校正 + 送 UI
            for seg in new_segments:
                corrected = self.corrector.correct(seg)
                self.session_mgr.add_segment(session, corrected)
                if self.on_segment:
                    self.on_segment(corrected)
                segments_since_summary += 1

            # 3. 檢查是否觸發週期摘要
            #    [R-1] 確保不在 Whisper 繁忙時同時跑 Gemma
            elapsed = time.time() - last_summary_time
            if (elapsed >= self.summary_interval and
                    segments_since_summary >= self.min_new_segments
                    and not self._summarizing):
                self._summarizing = True
                summary = await self.summarizer.generate(
                    session.segments,
                    previous_summary=session.summary,
                    participants=session.participants
                )
                self.session_mgr.update_summary(session, summary)
                if self.on_summary:
                    self.on_summary(summary)
                last_summary_time = time.time()
                segments_since_summary = 0
                self._summarizing = False

        # 錄音結束：產生最終摘要
        self.session_mgr.end_recording(session)
        if self.on_status_change:
            self.on_status_change("processing")

        final_summary = await self.summarizer.generate(
            session.segments,
            previous_summary=session.summary,
            participants=session.participants,
            is_final=True
        )
        self.session_mgr.update_summary(session, final_summary)
        self.session_mgr.mark_ready(session)

        if self.on_summary:
            self.on_summary(final_summary)
        if self.on_status_change:
            self.on_status_change("ready")
```

---

### Phase 4：UI 核心頁面

#### 4-1. MainView（`app/ui/main_view.py`）

```python
class MainView:
    """主視窗：左側導航 + 右側內容 + 底部狀態列"""

    def build(self, page: ft.Page):
        page.title = "會議即時智能儀表板"
        page.theme_mode = ft.ThemeMode.DARK

        # 左側導航
        nav_rail = ft.NavigationRail(
            destinations=[
                ft.NavigationRailDestination(icon=ft.icons.MIC, label="會議"),
                ft.NavigationRailDestination(icon=ft.icons.BOOK, label="詞條"),
                ft.NavigationRailDestination(icon=ft.icons.ANALYTICS, label="回饋"),
                ft.NavigationRailDestination(icon=ft.icons.SETTINGS, label="設定"),
            ],
            on_change=self._navigate
        )

        # 底部狀態列
        self.status_bar = StatusBar()  # Ollama 狀態、模型、詞條數、暫存量

        # 內容區
        self.content = ft.Container(expand=True)

        page.add(ft.Row([nav_rail, self.content], expand=True))
        page.add(self.status_bar.build())
```

#### 4-2. DashboardView（`app/ui/dashboard_view.py`）

```python
class DashboardView:
    """即時儀表板（會中）+ 編輯工作區（會後）"""

    def build(self, mode: str):  # mode: "live" | "review" | "idle"
        if mode == "idle":
            return self._build_idle()  # [開始錄音] [匯入音檔] + 歷史清單
        elif mode == "live":
            return self._build_live_dashboard()
        else:
            return self._build_review_workspace()

    # ── [M-2 新增] 會議資訊對話框（ui_spec#2.2）──

    def _show_meeting_info_dialog(self, on_confirm: Callable, on_skip: Callable):
        """
        開始錄音/匯入前彈出快速填寫對話框。
        - 名稱：預設「YYYY-MM-DD HH:MM 會議」
        - 與會人員：逗號分隔或逐個新增
        - [開始] → on_confirm(title, participants)
        - [跳過] → on_skip()（使用預設值，稍後可修改）
        """
        title_field = ft.TextField(
            label="會議名稱",
            value=f"{datetime.now():%Y-%m-%d %H:%M} 會議"
        )
        participants_field = ft.TextField(
            label="與會人員（逗號分隔）",
            hint_text="John, Mary, ..."
        )

        def on_start(e):
            names = [n.strip() for n in participants_field.value.split(",") if n.strip()]
            participants = [Participant(name=n, role=None, source="manual") for n in names]
            dialog.open = False
            on_confirm(title_field.value, participants)

        def on_skip_click(e):
            dialog.open = False
            on_skip()

        dialog = ft.AlertDialog(
            title=ft.Text("會議資訊（可稍後修改）"),
            content=ft.Column([title_field, participants_field], tight=True),
            actions=[
                ft.TextButton("跳過", on_click=on_skip_click),
                ft.ElevatedButton("開始", on_click=on_start),
            ]
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _on_start_recording(self, e):
        """[開始錄音] 按鈕 → 先彈會議資訊對話框 → 再啟動 Pipeline"""
        self._show_meeting_info_dialog(
            on_confirm=lambda title, parts: self._start_pipeline(title, parts, "microphone"),
            on_skip=lambda: self._start_pipeline(None, [], "microphone")
        )

    def _on_import_audio(self, e):
        """[匯入音檔] 按鈕 → 選檔 → 彈會議資訊 → 啟動 Pipeline"""
        # file_picker 選檔後同樣觸發 _show_meeting_info_dialog
        ...

    # ── 即時儀表板 ──

    def _build_live_dashboard(self):
        # [M-3 修正] HighlightsPanel → SummaryPanel（涵蓋 highlights + decisions）
        self.transcript_panel = TranscriptPanel(editable=False)
        self.summary_panel = SummaryPanel(editable=True)    # 重點 + 決議，可編輯
        self.actions_panel = ActionsPanel(editable=True)     # Actions 可編輯

        # 響應式佈局（依 ui_spec#2.3）
        return ft.ResponsiveRow([
            ft.Container(self.transcript_panel, col={"lg": 4, "md": 6, "sm": 12}),
            ft.Container(self.summary_panel,    col={"lg": 4, "md": 6, "sm": 12}),
            ft.Container(self.actions_panel,     col={"lg": 4, "md": 12, "sm": 12}),
        ])

    def _build_review_workspace(self):
        # 同三區塊，全部可編輯
        # 額外：校正回饋 UI（hover 顯示 original → corrected）
        # [M-1] 匯出成功後彈確認對話框：「是否刪除原始音檔？」[刪除] [保留]
        ...

    def on_new_segment(self, segment: CorrectedSegment):
        # StreamProcessor 回呼：即時新增逐字稿行
        self.transcript_panel.append(segment)

    def on_new_summary(self, summary: SummaryResult):
        """
        StreamProcessor 回呼：更新重點 + 決議 + Actions。
        保護使用者已編輯的內容不被 AI 覆蓋。
        """
        # [M-3] 重點 + 決議一起更新
        if not self._user_edited_highlights:
            self.summary_panel.update_highlights(summary.highlights)
        if not self._user_edited_decisions:
            self.summary_panel.update_decisions(summary.decisions)

        # [M-4] Action Items merge 保護：
        # 利用 ActionItem.user_edited 欄位（data_schema 已新增），
        # merge 時跳過 user_edited=True 的項目，只更新/新增 AI 產生的項目。
        self.actions_panel.merge_with_protection(summary.action_items)


class SummaryPanel:
    """[M-3 新增] 會議重點 + 決議事項面板"""

    def __init__(self, editable: bool):
        self.editable = editable
        self.highlights_editor = ft.TextField(multiline=True, read_only=not editable)
        self.decisions_list = ft.Column()  # 決議事項獨立區塊

    def build(self):
        return ft.Column([
            ft.Text("💡 會議重點", size=16, weight=ft.FontWeight.BOLD),
            self.highlights_editor,
            ft.Divider(),
            ft.Text("📋 決議事項", size=16, weight=ft.FontWeight.BOLD),
            self.decisions_list,
        ])

    def update_highlights(self, highlights: str): ...
    def update_decisions(self, decisions: list[str]): ...


class ActionsPanel:
    """Action Items 面板"""

    def merge_with_protection(self, new_actions: list[ActionItem]):
        """
        [M-4] 合併 AI 新產出的 Action Items，保護使用者已編輯的項目。
        策略：
        1. 遍歷現有 items，若 user_edited=True → 保留不動
        2. 遍歷 new_actions，依 id 比對：
           - 已存在且 user_edited=True → 跳過（不覆蓋）
           - 已存在且 user_edited=False → 更新內容
           - 不存在 → 新增（user_edited=False）
        3. 原有 items 中 user_edited=False 但 new_actions 中已不存在 → 保留（不主動刪除）
        """
        existing = {item.id: item for item in self._items}
        for new_item in new_actions:
            if new_item.id in existing:
                if not existing[new_item.id].user_edited:
                    # AI 項目可更新
                    self._update_item(new_item.id, new_item)
            else:
                # 新項目
                new_item.user_edited = False
                self._add_item(new_item)
        self._refresh_ui()
```

#### 4-3. SettingsView（`app/ui/settings_view.py`）

```python
class SettingsView:
    """設定頁面 — 依 ui_spec#5"""

    def build(self):
        return ft.Column([
            # Whisper 設定
            self._section("語音轉錄", [
                self._dropdown("模型", ["tiny","small","medium"], "whisper.model"),
                self._dropdown("語言", ["zh","en","ja"], "whisper.language"),
            ]),
            # Ollama 設定
            self._section("摘要模型", [
                self._text_field("模型名稱", "ollama.model"),
                self._text_field("Ollama URL", "ollama.base_url"),
                self._test_connection_button(),
            ]),
            # 串流設定
            self._section("串流處理", [
                self._slider("摘要週期（秒）", 60, 600, "streaming.summary_interval_sec"),
                self._slider("最少新 Segments", 5, 30, "streaming.summary_min_new_segments"),
            ]),
            # 匯出設定
            self._section("匯出", [
                self._folder_picker("預設匯出目錄", "export.default_dir"),
                self._checkbox("包含原始逐字稿", "export.include_raw_transcript"),
                self._checkbox("包含校正標記", "export.include_corrections"),
            ]),
        ])
```

---

### Phase 5：UI 輔助頁面

#### 5-1. TermsView（`app/ui/terms_view.py`）

```python
class TermsView:
    """詞條管理 — 依 ui_spec#3"""

    def build(self):
        return ft.Column([
            # 頂部工具列：搜尋框 + 分類篩選 + [新增] + [批次匯入]
            self._toolbar(),
            # 詞條清單（DataTable）
            ft.DataTable(
                columns=["詞條", "別名", "分類", "命中", "成功率", "操作"],
                rows=self._build_rows()
            ),
        ])

    def _build_rows(self):
        terms = self.kb.list_terms()
        for t in terms:
            success_rate = t["stats"]["success_count"] / max(t["stats"]["correction_count"], 1)
            # 每行一個 term，可展開編輯
            ...
```

#### 5-2. FeedbackView（`app/ui/feedback_view.py`）

```python
class FeedbackView:
    """回饋統計 — 依 ui_spec#4"""

    def build(self):
        stats = self.feedback_store.get_term_stats()
        return ft.Column([
            # 總覽卡片
            self._overview_cards(stats),  # 總成功率、總校正數
            # 低效詞條清單
            self._low_performing_terms(stats),  # success_rate < 50%
            # 零命中詞條
            self._zero_hit_terms(),
            # 高頻遺漏建議
            self._high_frequency_misses(),
        ])
```

---

## 3. 自驗證計畫

每個模組完成後，碼農先自測再提交 Review Gate。

### Phase 0 驗證

| 模組 | 自測方式 |
|------|---------|
| data_models | 單元測試：實例化每個 dataclass，驗證欄位、預設值、JSON 序列化/反序列化 |
| config_manager | 單元測試：讀取 default.yaml，get/set/save 迴圈驗證 |
| 專案骨架 | `pip install -e .` 成功，所有 import 路徑正確 |

### Phase 1 驗證

| 模組 | 自測方式 |
|------|---------|
| knowledge_base | 單元測試：CRUD 詞條、向量查詢（用固定 fixture 詞條，驗證 top-1 命中率）、批次匯入、stats 更新 |
| transcriber | 整合測試：準備 3 秒測試音檔（中文、英文），驗證回傳 TranscriptSegment 非空、index 遞增 |
| audio_recorder | 手動測試：錄 5 秒，驗證 async generator yield 音訊區塊、暫存 WAV 產出 |
| audio_importer | 單元測試：匯入不同格式（WAV/MP3），驗證切段數量正確、每段長度符合設定 |
| feedback_store | 單元測試：save/load 迴圈、get_term_stats 彙整正確性 |

### Phase 2 驗證

| 模組 | 自測方式 |
|------|---------|
| rag_corrector | 整合測試：固定知識庫 + 已知誤聽文字，驗證校正結果符合預期（如「寶石四」→「Gemma 4」） |
| summarizer | 整合測試：準備 mock 逐字稿，呼叫 Ollama，驗證回傳 SummaryResult 結構完整、JSON 可解析。**[T-1]** 額外測試：mock Gemma 回傳非 JSON 字串，驗證 fallback 行為（保留前次摘要 + 不崩潰） |
| session_manager | 單元測試：create → add_segment → update_summary → end → export 全生命週期。**[T-2]** 額外測試：save → load 迴圈，驗證反序列化後所有欄位一致（含 segments、summary_history、user_edits） |
| exporter | 單元測試：固定 Session 物件 → 匯出 Markdown → 驗證格式符合 data_schema#7 |

### Phase 3 驗證

| 模組 | 自測方式 |
|------|---------|
| stream_processor | 端對端整合測試：以 AudioImporter 匯入短音檔（30 秒），驗證：(1) on_segment 被呼叫 N 次；(2) on_summary 被呼叫；(3) session.status == "ready"；(4) session.summary.is_final == True |

### Phase 4-5 驗證

| 模組 | 自測方式 |
|------|---------|
| main_view | 手動測試：App 啟動、導航切換、狀態列顯示 |
| dashboard_view | 手動測試：(1) 開始錄音 → 即時逐字稿滾動；(2) 週期摘要出現在重點/Actions；(3) 停止 → 進入編輯模式；(4) 匯出產出 .md。**[T-3]** 額外測試：會中編輯保護 — 手動編輯 highlights → 觸發 on_new_summary → 驗證使用者編輯版本未被覆蓋；手動編輯某 ActionItem（user_edited=True）→ 觸發 merge → 驗證該項未被覆蓋 |
| settings_view | 手動測試：修改設定 → 重啟驗證生效 |
| terms_view | 手動測試：新增/編輯/刪除詞條、批次匯入、搜尋篩選 |
| feedback_view | 手動測試：有回饋資料時統計數字正確 |

---

## 4. 風險項目與應對策略

### 高風險

| 風險 | 影響 | 應對策略 |
|------|------|---------|
| **Gemma 4 CPU 推理過慢** | 摘要更新延遲超過 30 秒，使用者體驗差 | (1) 量化為 Q4_K_M；(2) 限制送入 Gemma 的 token 數（只送新段落 + 前次摘要）；(3) 設定 `num_ctx` 最小夠用值；(4) 若仍慢，Prompt 壓縮：省略低信心 segments |
| **faster-whisper CPU 延遲** | 即時轉錄跟不上說話速度 | (1) 使用 `small` model + `int8` compute_type；(2) VAD 過濾靜音減少無效轉錄；(3) 若仍延遲，降級為 `tiny` model（設定可切換） |
| **記憶體超限（16GB）** | App 崩潰 | Whisper ~1.5GB + Gemma4 ~3GB + ChromaDB ~0.5GB + App ~0.5GB ≈ 5.5GB，安全但需監控。(1) 音訊串流處理不累積；(2) UI 虛擬捲動；(3) 長會議階層式摘要限制 context |

### 中風險

| 風險 | 影響 | 應對策略 |
|------|------|---------|
| **Gemma 4 輸出格式不穩定** | JSON 解析失敗，摘要顯示空白 | (1) Prompt 明確要求 JSON 格式 + 範例；(2) 解析失敗時 retry 一次；(3) 仍失敗則保留前次摘要 + 狀態列提示 |
| **RAG 校正誤判** | 把正確的詞替換錯誤 | (1) similarity_threshold 預設 0.6，偏保守；(2) 回饋機制讓使用者標記錯誤；(3) 持續低效的詞條在統計頁醒目標示 |
| **Flet 響應式佈局限制** | 三欄佈局在某些解析度顯示異常 | (1) 使用 ResponsiveRow + breakpoint 斷點；(2) 優先確保 ≥1400px 三欄正常；(3) 窄螢幕退化為 Tab 切換 |
| **Ollama 未啟動或模型未下載** | App 啟動後摘要功能失效 | (1) 啟動時偵測 Ollama 連線狀態，狀態列即時顯示；(2) 錄音/轉錄/校正不依賴 Ollama，可獨立運作；(3) 設定頁提供連線測試按鈕 |
| **[R-1] Whisper + Gemma CPU 時間片競爭** | 兩個模型同時跑 CPU 推理，互相拖慢，轉錄延遲 + 摘要延遲疊加 | (1) StreamProcessor 中 `_summarizing` 旗標確保摘要與轉錄不同時推理（見 Phase 3 偽代碼）；(2) Gemma 摘要在轉錄間隙（等待新音訊區塊時）觸發；(3) 若仍衝突，摘要改為 asyncio.create_task 低優先級排程，轉錄 await 完成後再 resume |

### 低風險

| 風險 | 影響 | 應對策略 |
|------|------|---------|
| **音檔格式不支援** | 匯入失敗 | pydub 支援主流格式（WAV/MP3/M4A/OGG），不支援時顯示錯誤訊息 |
| **ChromaDB 索引損毀** | 知識庫查詢失敗 | (1) 詞條 YAML 為 source of truth，可隨時重建索引；(2) 啟動時驗證索引完整性 |
| **長會議 context 超限** | 階層式摘要品質下降 | (1) 每層摘要保留關鍵詞確保主題不丟失；(2) 實際使用中 3 小時會議 ≈ 300 段落，增量摘要足夠 |

---

## 5. 備註

- **不實作與 specs 矛盾的代碼** — 如有疑義先回報大統領更新 specs
- **新增 `models.py`** — specs 目錄結構未列，但所有 dataclass 集中管理是必要的，Phase 0 提交時附帶說明
- 每個 Phase 完成後通過 Review Gate 才進下一期
- Phase 1 五個模組互相獨立，可依實際狀況調整順序
