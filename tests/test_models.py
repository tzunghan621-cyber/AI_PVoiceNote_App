"""測試資料模型 — 實例化、欄位驗證、JSON 序列化/反序列化"""

import json
from dataclasses import asdict

from app.core.models import (
    TranscriptSegment, Correction, CorrectedSegment,
    ActionItem, SummaryResult, Participant, UserEdits,
    FeedbackEntry, SessionFeedback, Session,
    to_json, from_json,
)


class TestTranscriptSegment:
    def test_create(self):
        seg = TranscriptSegment(index=0, start=0.0, end=2.5, text="測試", confidence=0.9, chunk_id=0)
        assert seg.index == 0
        assert seg.text == "測試"
        assert seg.confidence == 0.9

    def test_json_roundtrip(self):
        seg = TranscriptSegment(index=1, start=1.0, end=3.0, text="hello", confidence=0.85, chunk_id=0)
        j = to_json(seg)
        restored = from_json(TranscriptSegment, j)
        assert restored.index == seg.index
        assert restored.text == seg.text


class TestCorrection:
    def test_create(self):
        c = Correction(segment_index=0, original="寶石四", corrected="Gemma 4", term_id="gemma4", similarity=0.92)
        assert c.original == "寶石四"
        assert c.corrected == "Gemma 4"


class TestCorrectedSegment:
    def test_create_with_corrections(self):
        corr = Correction(segment_index=0, original="寶石四", corrected="Gemma 4", term_id="gemma4", similarity=0.92)
        seg = CorrectedSegment(
            index=0, start=0.0, end=2.5,
            original_text="用寶石四做推理",
            corrected_text="用Gemma 4做推理",
            corrections=[corr],
        )
        assert len(seg.corrections) == 1
        assert seg.corrections[0].term_id == "gemma4"

    def test_empty_corrections(self):
        seg = CorrectedSegment(index=0, start=0.0, end=1.0, original_text="ok", corrected_text="ok")
        assert seg.corrections == []


class TestActionItem:
    def test_create(self):
        item = ActionItem(
            id="ai-001", content="確認 API 文件", owner="John",
            deadline="2026-04-07", source_segment=5,
            status="open", priority="high", note=None,
            user_edited=False,
            created="2026-04-05T10:00:00", updated="2026-04-05T10:00:00",
        )
        assert item.status == "open"
        assert item.user_edited is False

    def test_user_edited_flag(self):
        item = ActionItem(
            id="ai-002", content="test", owner=None, deadline=None,
            source_segment=0, status="open", priority="low", note=None,
            user_edited=True,
            created="2026-04-05T10:00:00", updated="2026-04-05T10:00:00",
        )
        assert item.user_edited is True


class TestSummaryResult:
    def test_create_defaults(self):
        sr = SummaryResult(version=1, highlights="重點內容")
        assert sr.action_items == []
        assert sr.decisions == []
        assert sr.is_final is False

    def test_full_create(self):
        item = ActionItem(
            id="ai-001", content="test", owner=None, deadline=None,
            source_segment=0, status="open", priority="medium", note=None,
            user_edited=False,
            created="2026-04-05T10:00:00", updated="2026-04-05T10:00:00",
        )
        sr = SummaryResult(
            version=2, highlights="重點",
            action_items=[item], decisions=["決議一"],
            keywords=["AI"], covered_until=10,
            model="gemma4:4b", generation_time=5.2, is_final=True,
        )
        assert sr.is_final is True
        assert len(sr.action_items) == 1

    def test_json_roundtrip(self):
        item = ActionItem(
            id="ai-001", content="確認", owner="John", deadline="2026-04-07",
            source_segment=5, status="open", priority="high", note=None,
            user_edited=False,
            created="2026-04-05T10:00:00", updated="2026-04-05T10:00:00",
        )
        sr = SummaryResult(
            version=1, highlights="重點",
            action_items=[item], decisions=["決議"],
            keywords=["AI"], covered_until=10,
            model="gemma4:4b", generation_time=3.0, is_final=False,
        )
        j = to_json(sr)
        restored = from_json(SummaryResult, j)
        assert restored.version == 1
        assert restored.highlights == "重點"
        assert len(restored.action_items) == 1
        assert restored.action_items[0].owner == "John"
        assert restored.action_items[0].user_edited is False


class TestParticipant:
    def test_manual(self):
        p = Participant(name="John", role="PM", source="manual")
        assert p.source == "manual"

    def test_ai_inferred(self):
        p = Participant(name="Mary", source="ai_inferred")
        assert p.role is None


class TestUserEdits:
    def test_defaults(self):
        ue = UserEdits()
        assert ue.highlights_edited is None
        assert ue.decisions_edited is None

    def test_with_edits(self):
        ue = UserEdits(
            highlights_edited="修改後重點",
            decisions_edited=["新決議"],
            edited_at="2026-04-05T11:00:00",
        )
        assert ue.highlights_edited == "修改後重點"


class TestFeedbackEntry:
    def test_correct(self):
        fe = FeedbackEntry(segment_index=0, correction_index=0, type="correct", term_id="gemma4")
        assert fe.type == "correct"

    def test_missed(self):
        fe = FeedbackEntry(segment_index=5, correction_index=-1, type="missed", expected="Ollama")
        assert fe.correction_index == -1
        assert fe.expected == "Ollama"


class TestSessionFeedback:
    def test_create(self):
        entry = FeedbackEntry(segment_index=0, correction_index=0, type="correct", term_id="gemma4")
        sf = SessionFeedback(
            session_id="sess-001", created="2026-04-05T12:00:00",
            entries=[entry], summary_rating=4, summary_note="不錯",
        )
        assert sf.summary_rating == 4
        assert len(sf.entries) == 1

    def test_json_roundtrip(self):
        entry = FeedbackEntry(
            segment_index=0, correction_index=0, type="correct",
            term_id="gemma4", timestamp="2026-04-05T12:00:00",
        )
        sf = SessionFeedback(
            session_id="sess-001", created="2026-04-05T12:00:00",
            entries=[entry], summary_rating=4,
        )
        j = to_json(sf)
        restored = from_json(SessionFeedback, j)
        assert restored.session_id == "sess-001"
        assert len(restored.entries) == 1
        assert restored.entries[0].type == "correct"


class TestSession:
    def test_create_defaults(self):
        s = Session()
        assert s.mode == "live"
        assert s.status == "recording"
        assert s.segments == []
        assert s.summary is None

    def test_full_create(self):
        p = Participant(name="John")
        s = Session(
            title="週會", participants=[p],
            audio_source="microphone",
        )
        assert s.title == "週會"
        assert len(s.participants) == 1

    def test_json_roundtrip(self):
        p = Participant(name="John", role="PM")
        item = ActionItem(
            id="ai-001", content="task", owner="John", deadline=None,
            source_segment=0, status="open", priority="medium", note=None,
            user_edited=False,
            created="2026-04-05T10:00:00", updated="2026-04-05T10:00:00",
        )
        summary = SummaryResult(
            version=1, highlights="hi", action_items=[item],
            decisions=["d1"], keywords=["k1"], covered_until=5,
            model="gemma4:4b", generation_time=2.0, is_final=True,
        )
        seg = CorrectedSegment(
            index=0, start=0.0, end=1.0,
            original_text="test", corrected_text="test",
        )
        s = Session(
            title="test session", participants=[p],
            segments=[seg], summary=summary, summary_history=[summary],
        )
        j = to_json(s)
        data = json.loads(j)
        assert data["title"] == "test session"
        assert len(data["participants"]) == 1
        assert data["summary"]["version"] == 1
        assert len(data["segments"]) == 1

        restored = from_json(Session, j)
        assert restored.title == "test session"
        assert len(restored.participants) == 1
        assert restored.summary.version == 1
        assert restored.summary.action_items[0].owner == "John"
