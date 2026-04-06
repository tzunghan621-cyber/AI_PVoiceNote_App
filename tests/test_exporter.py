"""測試 Exporter — Markdown 匯出格式、user_edits 優先、不刪音檔"""

import pytest

from app.core.exporter import Exporter
from app.core.models import (
    Session, CorrectedSegment, Correction, SummaryResult, ActionItem,
    Participant, UserEdits,
)


def _make_session(with_edits=False, with_corrections=True) -> Session:
    corrections = []
    if with_corrections:
        corrections = [Correction(
            segment_index=0, original="寶石四", corrected="Gemma 4",
            term_id="gemma4", similarity=0.92,
        )]

    segments = [
        CorrectedSegment(
            index=0, start=0.0, end=10.0,
            original_text="我們用寶石四來做推理",
            corrected_text="我們用Gemma 4來做推理",
            corrections=corrections,
        ),
        CorrectedSegment(
            index=1, start=10.0, end=20.0,
            original_text="John 負責確認 API 文件",
            corrected_text="John 負責確認 API 文件",
            corrections=[],
        ),
    ]

    action_items = [ActionItem(
        id="ai-001", content="確認 API 文件", owner="John",
        deadline="2026-04-07", source_segment=1, status="open",
        priority="high", note=None, user_edited=False,
        created="2026-04-05T10:00:00", updated="2026-04-05T10:00:00",
    )]

    summary = SummaryResult(
        version=1, highlights="討論了 Gemma 4 部署方案",
        action_items=action_items, decisions=["採用 Gemma 4 4B"],
        keywords=["Gemma 4", "API"], covered_until=1,
        model="gemma4:e4b", generation_time=3.0, is_final=True,
    )

    user_edits = None
    if with_edits:
        user_edits = UserEdits(
            highlights_edited="使用者修改的重點摘要",
            decisions_edited=["使用者修改的決議"],
            edited_at="2026-04-05T11:00:00",
        )

    return Session(
        id="sess-001", title="週會 2026-04-05",
        created="2026-04-05T10:00:00", ended="2026-04-05T11:00:00",
        participants=[
            Participant(name="John", role="PM"),
            Participant(name="Mary", role="工程師"),
        ],
        mode="review", status="ready",
        audio_source="microphone", audio_duration=1200.0,
        segments=segments, summary_history=[summary], summary=summary,
        user_edits=user_edits, audio_paths=["/tmp/chunk.wav"],
    )


@pytest.fixture
def exporter():
    return Exporter()


class TestExport:
    def test_creates_markdown_file(self, exporter, tmp_path):
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        assert output.exists()

    def test_sets_status_exported(self, exporter, tmp_path):
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        assert session.status == "exported"
        assert session.export_path == str(output)

    def test_does_not_delete_audio(self, exporter, tmp_path):
        """[M-1] Exporter 不刪除音檔"""
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        # audio_paths 不應被清空
        assert len(session.audio_paths) == 1


class TestMarkdownFormat:
    def test_frontmatter(self, exporter, tmp_path):
        """YAML frontmatter 正確"""
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert md.startswith("---\n")
        assert "title:" in md
        assert "date:" in md
        assert "participants:" in md
        assert "source: AI_PVoiceNote_App" in md

    def test_participants_section(self, exporter, tmp_path):
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "## 與會人員" in md
        assert "John" in md
        assert "PM" in md
        assert "Mary" in md

    def test_highlights_section(self, exporter, tmp_path):
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "## 摘要" in md
        assert "Gemma 4 部署方案" in md

    def test_action_items_section(self, exporter, tmp_path):
        """Action Items 含 owner/deadline/priority"""
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "## 待辦事項" in md
        assert "確認 API 文件" in md
        assert "John" in md
        assert "2026-04-07" in md
        assert "high" in md

    def test_decisions_section(self, exporter, tmp_path):
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "## 決議事項" in md
        assert "採用 Gemma 4 4B" in md

    def test_keywords_section(self, exporter, tmp_path):
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "## 關鍵詞" in md
        assert "Gemma 4" in md

    def test_transcript_section(self, exporter, tmp_path):
        session = _make_session()
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "## 逐字稿" in md
        assert "Gemma 4" in md

    def test_correction_marks(self, exporter, tmp_path):
        """校正標記：~~原始~~ → **校正**"""
        session = _make_session(with_corrections=True)
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "~~寶石四~~" in md
        assert "**Gemma 4**" in md
        assert "gemma4" in md


class TestUserEdits:
    def test_prefers_user_edits(self, exporter, tmp_path):
        """有 user_edits 時使用編輯版本"""
        session = _make_session(with_edits=True)
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "使用者修改的重點摘要" in md
        assert "使用者修改的決議" in md

    def test_falls_back_to_ai_summary(self, exporter, tmp_path):
        """無 user_edits 時使用 AI 摘要"""
        session = _make_session(with_edits=False)
        output = tmp_path / "output.md"
        exporter.export(session, str(output))
        md = output.read_text(encoding="utf-8")

        assert "Gemma 4 部署方案" in md
        assert "採用 Gemma 4 4B" in md
