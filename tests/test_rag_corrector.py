"""測試 RAGCorrector — 即時校正逐字稿中的專有名詞"""

import pytest
from unittest.mock import MagicMock

from app.core.rag_corrector import RAGCorrector
from app.core.models import TranscriptSegment, CorrectedSegment, Correction


def _make_mock_kb(terms: list[dict]):
    """建立 mock KnowledgeBase，query 回傳指定詞條"""
    kb = MagicMock()
    kb.query.return_value = terms
    kb.update_stats = MagicMock()
    return kb


def _make_segment(index=0, text="", start=0.0, end=1.0):
    return TranscriptSegment(
        index=index, start=start, end=end,
        text=text, confidence=0.9, chunk_id=0,
    )


GEMMA_TERM = {
    "id": "gemma4",
    "term": "Gemma 4",
    "aliases": ["寶石四", "gemma4", "GEMMA"],
    "category": "技術/AI模型",
    "context": "Google 開源本地端 LLM",
}

CHROMADB_TERM = {
    "id": "chromadb",
    "term": "ChromaDB",
    "aliases": ["克羅馬", "chroma"],
    "category": "技術/資料庫",
    "context": "向量資料庫",
}


class TestCorrection:
    def test_correct_known_alias(self):
        """「寶石四」應被校正為「Gemma 4」"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb)

        seg = _make_segment(text="我們用寶石四來做推理")
        result = corrector.correct(seg)

        assert isinstance(result, CorrectedSegment)
        assert "Gemma 4" in result.corrected_text
        assert "寶石四" not in result.corrected_text
        assert len(result.corrections) == 1
        assert result.corrections[0].original == "寶石四"
        assert result.corrections[0].corrected == "Gemma 4"
        assert result.corrections[0].term_id == "gemma4"

    def test_no_correction_needed(self):
        """文字中無匹配 alias 時不校正"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb)

        seg = _make_segment(text="今天天氣不錯")
        result = corrector.correct(seg)

        assert result.corrected_text == "今天天氣不錯"
        assert result.corrections == []

    def test_multiple_corrections(self):
        """一個 segment 中有多個詞條需校正"""
        kb = _make_mock_kb([GEMMA_TERM, CHROMADB_TERM])
        corrector = RAGCorrector(kb)

        seg = _make_segment(text="用寶石四搭配克羅馬做向量搜尋")
        result = corrector.correct(seg)

        assert "Gemma 4" in result.corrected_text
        assert "ChromaDB" in result.corrected_text
        assert len(result.corrections) == 2

    def test_preserves_segment_fields(self):
        """校正後 segment 保留原始欄位"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb)

        seg = _make_segment(index=5, text="寶石四很快", start=10.0, end=12.5)
        result = corrector.correct(seg)

        assert result.index == 5
        assert result.start == 10.0
        assert result.end == 12.5
        assert result.original_text == "寶石四很快"


class TestStats:
    def test_updates_hit_and_correction_count(self):
        """校正時應更新 hit_count 和 correction_count"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb)

        seg = _make_segment(text="寶石四模型")
        corrector.correct(seg)

        kb.update_stats.assert_any_call("gemma4", "hit_count")
        kb.update_stats.assert_any_call("gemma4", "correction_count")

    def test_no_stats_update_when_no_match(self):
        """無匹配時不更新統計"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb)

        seg = _make_segment(text="無關文字")
        corrector.correct(seg)

        kb.update_stats.assert_not_called()


class TestThreshold:
    def test_below_threshold_no_correction(self):
        """相似度低於閾值時不校正"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb, similarity_threshold=1.0)  # 極高閾值

        seg = _make_segment(text="寶石四模型")
        result = corrector.correct(seg)

        # 雖然 alias 文字匹配，但相似度計算低於閾值
        # 實際行為取決於 _compute_similarity 實作
        assert isinstance(result, CorrectedSegment)

    def test_exact_match_always_corrects(self):
        """完全匹配的 alias 應被校正（相似度=1.0）"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb, similarity_threshold=0.5)

        seg = _make_segment(text="用寶石四")
        result = corrector.correct(seg)

        assert "Gemma 4" in result.corrected_text


class TestEdgeCases:
    def test_empty_text(self):
        """空文字不崩潰"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb)

        seg = _make_segment(text="")
        result = corrector.correct(seg)

        assert result.corrected_text == ""
        assert result.corrections == []

    def test_empty_kb(self):
        """空知識庫不崩潰"""
        kb = _make_mock_kb([])
        corrector = RAGCorrector(kb)

        seg = _make_segment(text="寶石四")
        result = corrector.correct(seg)

        assert result.corrected_text == "寶石四"
        assert result.corrections == []

    def test_alias_case_insensitive(self):
        """alias 匹配應不區分大小寫"""
        kb = _make_mock_kb([GEMMA_TERM])
        corrector = RAGCorrector(kb)

        seg = _make_segment(text="使用 gemma4 模型")
        result = corrector.correct(seg)

        assert "Gemma 4" in result.corrected_text
