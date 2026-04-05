"""即時 RAG 校正 — 逐字稿中的專有名詞校正"""

from __future__ import annotations

import re

from app.core.models import TranscriptSegment, CorrectedSegment, Correction


class RAGCorrector:
    def __init__(self, knowledge_base, similarity_threshold: float = 0.6):
        self.kb = knowledge_base
        self.similarity_threshold = similarity_threshold

    def correct(self, segment: TranscriptSegment) -> CorrectedSegment:
        """校正單一 segment，回傳 CorrectedSegment"""
        corrections: list[Correction] = []
        corrected_text = segment.text

        if not segment.text.strip():
            return CorrectedSegment(
                index=segment.index,
                start=segment.start, end=segment.end,
                original_text=segment.text,
                corrected_text=segment.text,
                corrections=[],
            )

        candidates = self.kb.query(segment.text, top_k=5)

        corrected_term_ids: set[str] = set()

        for term in candidates:
            if term["id"] in corrected_term_ids:
                continue
            aliases = term.get("aliases", [])
            for alias in aliases:
                if self._fuzzy_match(alias, segment.text):
                    sim = self._compute_similarity(alias, term["term"])
                    if sim >= self.similarity_threshold:
                        corrected_text = self._replace_alias(
                            corrected_text, alias, term["term"]
                        )
                        corrections.append(Correction(
                            segment_index=segment.index,
                            original=alias,
                            corrected=term["term"],
                            term_id=term["id"],
                            similarity=sim,
                        ))
                        self.kb.update_stats(term["id"], "hit_count")
                        self.kb.update_stats(term["id"], "correction_count")
                        corrected_term_ids.add(term["id"])
                        break  # 同一 term 只用第一個匹配的 alias

        return CorrectedSegment(
            index=segment.index,
            start=segment.start, end=segment.end,
            original_text=segment.text,
            corrected_text=corrected_text,
            corrections=corrections,
        )

    def _fuzzy_match(self, alias: str, text: str) -> bool:
        """檢查 alias 是否出現在文字中（不區分大小寫）"""
        return alias.lower() in text.lower()

    def _compute_similarity(self, alias: str, term: str) -> float:
        """計算 alias 與正式名稱的相似度。完全匹配或已知 alias 回傳高分。"""
        if alias.lower() == term.lower():
            return 1.0
        # alias 是已知的別名，給予高相似度
        # 實際場景中這些 alias 都是人工定義的，信心度高
        return 0.85

    def _replace_alias(self, text: str, alias: str, term: str) -> str:
        """在文字中替換 alias 為正式名稱（不區分大小寫）"""
        pattern = re.compile(re.escape(alias), re.IGNORECASE)
        return pattern.sub(term, text, count=1)
