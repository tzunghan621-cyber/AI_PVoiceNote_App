"""測試 StreamProcessor — 管線整合、週期摘要觸發、最終摘要"""

import asyncio
import json

import numpy as np
import pytest
import yaml
from unittest.mock import MagicMock, AsyncMock, patch

from app.data.config_manager import ConfigManager
from app.core.stream_processor import StreamProcessor
from app.core.models import (
    TranscriptSegment, CorrectedSegment, Correction,
    SummaryResult, ActionItem, Session, Participant,
)


@pytest.fixture
def config(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "streaming": {
            "summary_interval_sec": 1,  # 1 秒觸發（測試用）
            "summary_min_new_segments": 2,  # 至少 2 段
        },
        "sessions": {"dir": str(sessions_dir)},
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


def _make_mock_transcriber():
    """Mock Transcriber：每個 chunk 產 2 個 segments"""
    t = MagicMock()
    call_count = [0]

    def transcribe_chunk(audio, chunk_id):
        idx = call_count[0]
        call_count[0] += 2
        return [
            TranscriptSegment(index=idx, start=float(idx * 5), end=float(idx * 5 + 5),
                              text=f"段落 {idx}", confidence=0.9, chunk_id=chunk_id),
            TranscriptSegment(index=idx + 1, start=float((idx + 1) * 5),
                              end=float((idx + 1) * 5 + 5),
                              text=f"段落 {idx + 1}", confidence=0.85, chunk_id=chunk_id),
        ]

    t.transcribe_chunk = MagicMock(side_effect=transcribe_chunk)  # 同步方法，非 AsyncMock
    return t


def _make_mock_corrector():
    """Mock RAGCorrector：原封不動回傳"""
    c = MagicMock()

    def correct(seg):
        return CorrectedSegment(
            index=seg.index, start=seg.start, end=seg.end,
            original_text=seg.text, corrected_text=seg.text,
            corrections=[],
        )

    c.correct = MagicMock(side_effect=correct)
    return c


def _make_mock_summarizer():
    """Mock Summarizer"""
    s = MagicMock()
    call_count = [0]

    async def generate(segments, previous_summary=None, participants=None, is_final=False):
        call_count[0] += 1
        return SummaryResult(
            version=call_count[0], highlights=f"摘要 v{call_count[0]}",
            action_items=[ActionItem(
                id=f"ai-{call_count[0]}", content=f"待辦 {call_count[0]}",
                owner="John", deadline=None, source_segment=0,
                status="open", priority="medium", note=None,
                user_edited=False,
                created="2026-04-05T10:00:00", updated="2026-04-05T10:00:00",
            )],
            decisions=[f"決議 {call_count[0]}"], keywords=["key"],
            covered_until=segments[-1].index if segments else 0,
            model="gemma4:e2b", generation_time=0.1, is_final=is_final,
        )

    s.generate = AsyncMock(side_effect=generate)
    return s


def _make_mock_session_manager():
    mgr = MagicMock()
    mgr.add_segment = MagicMock()
    mgr.update_summary = MagicMock()
    mgr.end_recording = MagicMock()
    mgr.mark_ready = MagicMock()
    return mgr


async def _make_audio_source(n_chunks: int):
    """產生 n 個音訊區塊的 async generator"""
    for i in range(n_chunks):
        yield np.random.randn(16000).astype(np.float32)  # 1 秒
        await asyncio.sleep(0.01)


class TestBasicPipeline:
    @pytest.mark.asyncio
    async def test_segments_produced(self, config):
        """Pipeline 跑完後 session 應有 segments"""
        transcriber = _make_mock_transcriber()
        corrector = _make_mock_corrector()
        summarizer = _make_mock_summarizer()
        session_mgr = _make_mock_session_manager()

        sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        session = Session(title="test")

        received_segments = []
        sp.on_segment = lambda seg: received_segments.append(seg)

        await sp.run(_make_audio_source(3), session)

        # 3 chunks × 2 segments/chunk = 6 segments
        assert len(received_segments) == 6
        assert session_mgr.add_segment.call_count == 6

    @pytest.mark.asyncio
    async def test_final_summary(self, config):
        """Pipeline 結束後應產生最終摘要"""
        transcriber = _make_mock_transcriber()
        corrector = _make_mock_corrector()
        summarizer = _make_mock_summarizer()
        session_mgr = _make_mock_session_manager()

        sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        session = Session(title="test")

        summaries = []
        sp.on_summary = lambda s: summaries.append(s)

        await sp.run(_make_audio_source(3), session)

        # 最後一個 summary 應為 is_final=True
        assert len(summaries) >= 1
        assert summaries[-1].is_final is True

        # 應呼叫 end_recording 和 mark_ready
        session_mgr.end_recording.assert_called_once()
        session_mgr.mark_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_changes(self, config):
        """Pipeline 應觸發 status_change 回呼"""
        transcriber = _make_mock_transcriber()
        corrector = _make_mock_corrector()
        summarizer = _make_mock_summarizer()
        session_mgr = _make_mock_session_manager()

        sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        session = Session(title="test")

        statuses = []
        sp.on_status_change = lambda s: statuses.append(s)

        await sp.run(_make_audio_source(2), session)

        assert "processing" in statuses
        assert "ready" in statuses


class TestPeriodicSummary:
    @pytest.mark.asyncio
    async def test_periodic_summary_triggered(self, config):
        """滿足條件時應觸發週期摘要"""
        transcriber = _make_mock_transcriber()
        corrector = _make_mock_corrector()
        summarizer = _make_mock_summarizer()
        session_mgr = _make_mock_session_manager()

        sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        session = Session(title="test")

        summaries = []
        sp.on_summary = lambda s: summaries.append(s)

        # 用 5 個 chunks + sleep 確保 interval 過期
        async def slow_source():
            for i in range(5):
                yield np.random.randn(16000).astype(np.float32)
                await asyncio.sleep(0.3)  # 讓 summary_interval (1s) 有機會觸發

        await sp.run(slow_source(), session)

        # 應至少有 1 個週期摘要 + 1 個最終摘要
        assert len(summaries) >= 2

    @pytest.mark.asyncio
    async def test_no_summary_below_min_segments(self, config):
        """segments 不足 min_new_segments 時不觸發"""
        transcriber = MagicMock()
        # 每個 chunk 只產 1 個 segment
        call_count = [0]
        def single_seg(audio, chunk_id):
            idx = call_count[0]
            call_count[0] += 1
            return [TranscriptSegment(
                index=idx, start=0.0, end=5.0,
                text="test", confidence=0.9, chunk_id=chunk_id,
            )]
        transcriber.transcribe_chunk = MagicMock(side_effect=single_seg)  # 同步方法

        corrector = _make_mock_corrector()
        summarizer = _make_mock_summarizer()
        session_mgr = _make_mock_session_manager()

        # min_new_segments=2, 但只有 1 個 chunk → 1 個 segment
        sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        session = Session(title="test")

        summaries = []
        sp.on_summary = lambda s: summaries.append(s)

        await sp.run(_make_audio_source(1), session)

        # 只有最終摘要（is_final），沒有週期摘要
        assert len(summaries) == 1
        assert summaries[0].is_final is True


class TestSummarizingGuard:
    @pytest.mark.asyncio
    async def test_summarizing_flag(self, config):
        """[R-1] _summarizing 旗標防止同時推理"""
        transcriber = _make_mock_transcriber()
        corrector = _make_mock_corrector()
        summarizer = _make_mock_summarizer()
        session_mgr = _make_mock_session_manager()

        sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        assert sp._summarizing is False


class TestSyncTranscriberIntegration:
    """[M-1a] 整合測試：使用真正的同步 Transcriber stub（非 AsyncMock）
    驗證 asyncio.to_thread 正確包裝同步方法。"""

    @pytest.mark.asyncio
    async def test_sync_transcriber_with_to_thread(self, config):
        """真正的同步 transcribe_chunk 應透過 to_thread 正常運作"""

        class SyncTranscriberStub:
            """模擬真實 Transcriber — 純同步方法"""
            def __init__(self):
                self._counter = 0

            def transcribe_chunk(self, audio_data, chunk_id):
                # CPU 密集操作的模擬（同步）
                import time
                time.sleep(0.01)
                idx = self._counter
                self._counter += 1
                return [TranscriptSegment(
                    index=idx, start=float(idx * 5), end=float(idx * 5 + 5),
                    text=f"sync segment {idx}", confidence=0.9, chunk_id=chunk_id,
                )]

        transcriber = SyncTranscriberStub()
        corrector = _make_mock_corrector()
        summarizer = _make_mock_summarizer()
        session_mgr = _make_mock_session_manager()

        sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        session = Session(title="sync test")

        received = []
        sp.on_segment = lambda seg: received.append(seg)

        await sp.run(_make_audio_source(3), session)

        # 3 chunks × 1 segment/chunk = 3 segments
        assert len(received) == 3
        assert all(seg.corrected_text.startswith("sync segment") for seg in received)
        # 最終摘要應正常產出
        session_mgr.end_recording.assert_called_once()
        session_mgr.mark_ready.assert_called_once()


# ─────────────────────────────────────────────────────────────
# Bug #16 修法 C — _build_fallback_final F-2 guard（向前找 summary_history 非空版本）
# ─────────────────────────────────────────────────────────────


def _make_summary(version: int, highlights: str) -> SummaryResult:
    return SummaryResult(
        version=version,
        highlights=highlights,
        action_items=[],
        decisions=[],
        keywords=[],
        covered_until=version * 10,
        model="gemma4:e2b",
        generation_time=1.0,
        is_final=False,
    )


class TestBug16FallbackFinalGuard:
    """修法 C：_build_fallback_final 應跳過空 highlights 版本，向前找第一個非空"""

    def test_build_fallback_final_skips_empty_and_finds_non_empty_history(self, config):
        """V2/V3 empty → 應複用 V1（非空）當 final，而非複用最新空的 V3"""
        sp = StreamProcessor(
            _make_mock_transcriber(), _make_mock_corrector(),
            _make_mock_summarizer(), _make_mock_session_manager(), config,
        )
        session = Session(title="fallback guard test")
        # 歷史：V1 有內容，V2/V3 空（模擬 Bug #16 實機場景）
        v1 = _make_summary(1, "V1 實際會議重點")
        v2 = _make_summary(2, "")
        v3 = _make_summary(3, "")
        session.summary_history = [v1, v2, v3]
        session.summary = v3  # 最新（空）

        result = sp._build_fallback_final(session, "ollama_timeout")

        assert result.is_final is True
        assert result.fallback_reason == "ollama_timeout"
        # 關鍵：應複用 V1 非空內容，不是 V3 空
        assert result.highlights == "V1 實際會議重點"
        assert result.version == v1.version + 1

    def test_build_fallback_final_all_empty_returns_placeholder(self, config):
        """summary_history 全空 → 回占位失敗文案 final（保證非 None）"""
        sp = StreamProcessor(
            _make_mock_transcriber(), _make_mock_corrector(),
            _make_mock_summarizer(), _make_mock_session_manager(), config,
        )
        session = Session(title="all empty")
        session.summary_history = [_make_summary(1, ""), _make_summary(2, "")]

        result = sp._build_fallback_final(session, "ollama_failure")

        assert result.is_final is True
        assert result.fallback_reason == "ollama_failure"
        assert "摘要生成失敗" in result.highlights

    def test_build_fallback_final_no_history_returns_placeholder(self, config):
        """summary_history 為空 list → 回占位失敗文案"""
        sp = StreamProcessor(
            _make_mock_transcriber(), _make_mock_corrector(),
            _make_mock_summarizer(), _make_mock_session_manager(), config,
        )
        session = Session(title="no history")
        session.summary_history = []

        result = sp._build_fallback_final(session, "pending_summary_timeout")

        assert result.is_final is True
        assert "摘要生成失敗" in result.highlights


# ─────────────────────────────────────────────────────────────
# Bug #16 修法 D — stop_drain_timeout 必須涵蓋 pending + final（F-1 時序張力）
# ─────────────────────────────────────────────────────────────


class TestBug16StopDrainTimeoutCoversPendingPlusFinal:
    """修法 D (D1)：config default 的 stop_drain_timeout_sec 必須 ≥ pending_wait + final_timeout + buffer"""

    def test_stop_drain_timeout_covers_pending_plus_final(self):
        """讀 repo default config，驗 F-1 時序張力已解除"""
        from pathlib import Path
        default_yaml = Path(__file__).resolve().parents[1] / "config" / "default.yaml"
        cfg = ConfigManager(str(default_yaml))
        pending = cfg.get("streaming.pending_summary_wait_sec", 60)
        final = cfg.get("streaming.final_summary_timeout_sec", 120)
        drain = cfg.get("streaming.stop_drain_timeout_sec", 90)
        buffer = 10

        assert drain >= pending + final + buffer, (
            f"F-1 時序張力未解除：stop_drain({drain}) < pending({pending}) "
            f"+ final({final}) + buffer({buffer}) = {pending + final + buffer}"
        )
