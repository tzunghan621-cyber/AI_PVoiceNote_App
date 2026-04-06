"""測試 SessionManager — 生命週期、save/load 一致性、delete_audio"""

import pytest
import yaml

from app.data.config_manager import ConfigManager
from app.core.session_manager import SessionManager
from app.core.models import (
    CorrectedSegment, Correction, SummaryResult, ActionItem,
    Participant, UserEdits, Session,
)


@pytest.fixture
def config(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "sessions": {"dir": str(sessions_dir)},
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


@pytest.fixture
def mgr(config):
    return SessionManager(config)


def _make_segment(index=0):
    return CorrectedSegment(
        index=index, start=float(index * 10), end=float(index * 10 + 10),
        original_text=f"原始文字 {index}",
        corrected_text=f"校正文字 {index}",
        corrections=[Correction(
            segment_index=index, original="原始", corrected="校正",
            term_id="t1", similarity=0.9,
        )] if index % 2 == 0 else [],
    )


def _make_summary(version=1, is_final=False):
    return SummaryResult(
        version=version, highlights=f"重點 v{version}",
        action_items=[ActionItem(
            id=f"ai-{version}", content=f"待辦 {version}", owner="John",
            deadline="2026-04-07", source_segment=0, status="open",
            priority="high", note=None, user_edited=False,
            created="2026-04-05T10:00:00", updated="2026-04-05T10:00:00",
        )],
        decisions=[f"決議 {version}"], keywords=["key"],
        covered_until=version * 5, model="gemma3:4b",
        generation_time=2.0, is_final=is_final,
    )


class TestLifecycle:
    def test_create(self, mgr):
        s = mgr.create("週會", "microphone", [Participant(name="John")])
        assert s.title == "週會"
        assert s.mode == "live"
        assert s.status == "recording"
        assert s.audio_source == "microphone"
        assert len(s.participants) == 1

    def test_create_default_title(self, mgr):
        s = mgr.create(None, "microphone")
        assert "會議" in s.title

    def test_add_segment(self, mgr):
        s = mgr.create("test", "microphone")
        seg = _make_segment(0)
        mgr.add_segment(s, seg)
        assert len(s.segments) == 1
        assert s.segments[0].index == 0

    def test_update_summary(self, mgr):
        s = mgr.create("test", "microphone")
        summary = _make_summary(1)
        mgr.update_summary(s, summary)
        assert s.summary == summary
        assert len(s.summary_history) == 1

    def test_multiple_summaries(self, mgr):
        s = mgr.create("test", "microphone")
        mgr.update_summary(s, _make_summary(1))
        mgr.update_summary(s, _make_summary(2))
        assert len(s.summary_history) == 2
        assert s.summary.version == 2

    def test_end_recording(self, mgr):
        s = mgr.create("test", "microphone")
        mgr.end_recording(s)
        assert s.status == "processing"
        assert s.ended is not None

    def test_mark_ready(self, mgr):
        s = mgr.create("test", "microphone")
        mgr.end_recording(s)
        mgr.mark_ready(s)
        assert s.status == "ready"
        assert s.mode == "review"

    def test_save_user_edits(self, mgr):
        s = mgr.create("test", "microphone")
        edits = UserEdits(
            highlights_edited="使用者修改", decisions_edited=["新決議"],
            edited_at="2026-04-05T12:00:00",
        )
        mgr.save_user_edits(s, edits)
        assert s.user_edits.highlights_edited == "使用者修改"

    def test_full_lifecycle(self, mgr):
        """完整生命週期：create → segments → summaries → end → ready"""
        s = mgr.create("週會", "microphone", [Participant(name="John")])
        assert s.status == "recording"

        for i in range(5):
            mgr.add_segment(s, _make_segment(i))
        assert len(s.segments) == 5

        mgr.update_summary(s, _make_summary(1))
        mgr.update_summary(s, _make_summary(2, is_final=True))

        mgr.end_recording(s)
        assert s.status == "processing"

        mgr.mark_ready(s)
        assert s.status == "ready"
        assert s.mode == "review"


class TestSaveLoad:
    def test_save_and_load(self, mgr):
        """[T-2] save → load 一致性"""
        s = mgr.create("test session", "microphone",
                        [Participant(name="John", role="PM")])
        for i in range(3):
            mgr.add_segment(s, _make_segment(i))
        mgr.update_summary(s, _make_summary(1))
        mgr.save_user_edits(s, UserEdits(
            highlights_edited="修改版", edited_at="2026-04-05T12:00:00",
        ))
        mgr.save(s)

        loaded = mgr.load(s.id)
        assert loaded is not None
        assert loaded.id == s.id
        assert loaded.title == "test session"
        assert len(loaded.segments) == 3
        assert loaded.segments[0].corrected_text == "校正文字 0"
        assert loaded.segments[0].corrections[0].term_id == "t1"
        assert loaded.summary.version == 1
        assert loaded.summary.action_items[0].owner == "John"
        assert loaded.user_edits.highlights_edited == "修改版"
        assert len(loaded.participants) == 1
        assert loaded.participants[0].name == "John"

    def test_load_nonexistent(self, mgr):
        assert mgr.load("nonexistent") is None

    def test_list_sessions(self, mgr):
        s1 = mgr.create("會議一", "microphone")
        s2 = mgr.create("會議二", "import")
        mgr.save(s1)
        mgr.save(s2)

        sessions = mgr.list_sessions()
        assert len(sessions) == 2
        titles = {s["title"] for s in sessions}
        assert "會議一" in titles
        assert "會議二" in titles


class TestDeleteAudio:
    def test_delete_audio(self, mgr, tmp_path):
        """[M-1] delete_audio 刪除暫存音檔"""
        # 建立假音檔
        f1 = tmp_path / "chunk_0000.wav"
        f2 = tmp_path / "chunk_0001.wav"
        f1.write_bytes(b"fake wav")
        f2.write_bytes(b"fake wav")

        s = mgr.create("test", "microphone")
        s.audio_paths = [str(f1), str(f2)]

        mgr.delete_audio(s)

        assert s.audio_paths == []
        assert not f1.exists()
        assert not f2.exists()

    def test_delete_audio_missing_files(self, mgr):
        """刪除不存在的檔案不崩潰"""
        s = mgr.create("test", "microphone")
        s.audio_paths = ["/nonexistent/path.wav"]
        mgr.delete_audio(s)
        assert s.audio_paths == []
