"""測試 FeedbackStore — save/load、get_term_stats、get_high_frequency_misses"""

import pytest
import yaml

from app.data.config_manager import ConfigManager
from app.data.feedback_store import FeedbackStore
from app.core.models import FeedbackEntry, SessionFeedback


@pytest.fixture
def config(tmp_path):
    fb_dir = tmp_path / "feedback"
    fb_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "feedback": {"dir": str(fb_dir)},
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


@pytest.fixture
def store(config):
    return FeedbackStore(config)


def _make_feedback(session_id: str, entries: list[FeedbackEntry]) -> SessionFeedback:
    return SessionFeedback(
        session_id=session_id,
        created="2026-04-05T12:00:00",
        entries=entries,
        summary_rating=4,
        summary_note="ok",
    )


class TestSaveLoad:
    def test_save_and_load(self, store):
        entry = FeedbackEntry(
            segment_index=0, correction_index=0, type="correct",
            term_id="gemma4", timestamp="2026-04-05T12:00:00",
        )
        fb = _make_feedback("sess-001", [entry])
        store.save(fb)

        loaded = store.load("sess-001")
        assert loaded is not None
        assert loaded.session_id == "sess-001"
        assert len(loaded.entries) == 1
        assert loaded.entries[0].type == "correct"
        assert loaded.entries[0].term_id == "gemma4"

    def test_load_nonexistent(self, store):
        assert store.load("nonexistent") is None

    def test_save_overwrite(self, store):
        entry1 = FeedbackEntry(segment_index=0, correction_index=0, type="correct", term_id="gemma4")
        fb1 = _make_feedback("sess-001", [entry1])
        store.save(fb1)

        entry2 = FeedbackEntry(segment_index=1, correction_index=0, type="wrong", term_id="gemma4")
        fb2 = _make_feedback("sess-001", [entry1, entry2])
        store.save(fb2)

        loaded = store.load("sess-001")
        assert len(loaded.entries) == 2

    def test_roundtrip_preserves_fields(self, store):
        entry = FeedbackEntry(
            segment_index=5, correction_index=-1, type="missed",
            term_id=None, expected="Ollama", note="常遺漏",
            timestamp="2026-04-05T12:00:00",
        )
        fb = _make_feedback("sess-002", [entry])
        fb.summary_rating = 2
        fb.summary_note = "摘要漏很多"
        store.save(fb)

        loaded = store.load("sess-002")
        assert loaded.summary_rating == 2
        assert loaded.summary_note == "摘要漏很多"
        assert loaded.entries[0].expected == "Ollama"
        assert loaded.entries[0].correction_index == -1


class TestListAll:
    def test_list_all(self, store):
        for i in range(3):
            entry = FeedbackEntry(segment_index=0, correction_index=0, type="correct", term_id="t1")
            store.save(_make_feedback(f"sess-{i:03d}", [entry]))
        all_fb = store.list_all()
        assert len(all_fb) == 3


class TestTermStats:
    def test_get_term_stats(self, store):
        entries_1 = [
            FeedbackEntry(segment_index=0, correction_index=0, type="correct", term_id="gemma4"),
            FeedbackEntry(segment_index=1, correction_index=0, type="correct", term_id="gemma4"),
            FeedbackEntry(segment_index=2, correction_index=0, type="wrong", term_id="chromadb"),
        ]
        entries_2 = [
            FeedbackEntry(segment_index=0, correction_index=0, type="wrong", term_id="gemma4"),
            FeedbackEntry(segment_index=1, correction_index=-1, type="missed", term_id="chromadb"),
        ]
        store.save(_make_feedback("sess-001", entries_1))
        store.save(_make_feedback("sess-002", entries_2))

        stats = store.get_term_stats()
        assert stats["gemma4"]["correct"] == 2
        assert stats["gemma4"]["wrong"] == 1
        assert stats["chromadb"]["wrong"] == 1
        assert stats["chromadb"]["missed"] == 1

    def test_empty_stats(self, store):
        stats = store.get_term_stats()
        assert stats == {}


class TestHighFrequencyMisses:
    def test_high_frequency_misses(self, store):
        entries = [
            FeedbackEntry(segment_index=i, correction_index=-1, type="missed",
                          expected="歐拉瑪", note=None)
            for i in range(5)
        ]
        store.save(_make_feedback("sess-001", entries))

        misses = store.get_high_frequency_misses(threshold=3)
        assert "歐拉瑪" in misses

    def test_below_threshold(self, store):
        entries = [
            FeedbackEntry(segment_index=0, correction_index=-1, type="missed", expected="飛特"),
        ]
        store.save(_make_feedback("sess-001", entries))

        misses = store.get_high_frequency_misses(threshold=3)
        assert "飛特" not in misses
