"""週期性摘要 — Gemma 4 透過 Ollama 產生會議重點/Actions/決議"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from uuid import uuid4

import httpx

from app.data.config_manager import ConfigManager
from app.core.models import (
    CorrectedSegment, SummaryResult, ActionItem, Participant,
)

logger = logging.getLogger(__name__)


class EmptySummaryError(Exception):
    """Gemma response parse 成功但摘要全空（Bug #16：incremental 中文 key 等情境）。

    stream_processor 應 catch 此例外，走 fallback 複用 summary_history 最近非空版本，
    而非把空 SummaryResult update 到 session 造成空摘要覆蓋。
    """


class Summarizer:
    def __init__(self, config: ConfigManager):
        self.model = config.get("ollama.model", "gemma4:e2b")
        self.base_url = config.get("ollama.base_url", "http://localhost:11434")
        self.options = config.get("ollama.options", {}) or {}
        self._version = 0

    async def generate(
        self,
        segments: list[CorrectedSegment],
        previous_summary: SummaryResult | None = None,
        participants: list[Participant] | None = None,
        is_final: bool = False,
    ) -> SummaryResult:
        """產生或更新摘要"""
        start_time = time.time()

        if previous_summary:
            # [m-1] 用 index 過濾而非 list 切片
            new_segments = [s for s in segments if s.index > previous_summary.covered_until]
            prompt = self._build_incremental_prompt(
                new_segments, previous_summary, participants
            )
        else:
            prompt = self._build_initial_prompt(segments, participants)

        if is_final:
            prompt += "\n這是最終摘要，請全面整合所有內容。"

        response = await self._call_ollama(prompt)
        generation_time = time.time() - start_time

        # [Bug #16 診斷] 打印 Gemma 原始 response（含增量 mode 標記 + 長度 + repr）
        mode = "incremental" if previous_summary else "initial"
        logger.warning(
            "[Bug#16-diag] Gemma raw response "
            "(mode=%s, is_final=%s, prev_ver=%s, new_segs=%d, gen_time=%.1fs, "
            "resp_len=%d):\n%r",
            mode,
            is_final,
            previous_summary.version if previous_summary else None,
            len([s for s in segments if not previous_summary
                 or s.index > previous_summary.covered_until]),
            generation_time,
            len(response) if response else 0,
            response,
        )

        self._version += 1
        covered_until = segments[-1].index if segments else 0

        parsed = self._parse_response(response)
        # [Bug #16 診斷] 打印 parse 結果型別 + dict keys（或 None）
        if parsed is None:
            logger.warning(
                "[Bug#16-diag] _parse_response returned None (JSON decode failed)"
            )
        else:
            logger.warning(
                "[Bug#16-diag] _parse_response dict keys=%s, "
                "highlights_len=%d, action_items_count=%d, "
                "decisions_count=%d, keywords_count=%d",
                list(parsed.keys()),
                len(parsed.get("highlights", "") or ""),
                len(parsed.get("action_items", []) or []),
                len(parsed.get("decisions", []) or []),
                len(parsed.get("keywords", []) or []),
            )
        if parsed is None:
            # [T-1] JSON 解析失敗 fallback
            if previous_summary:
                return SummaryResult(
                    version=self._version,
                    highlights=previous_summary.highlights,
                    action_items=list(previous_summary.action_items),
                    decisions=list(previous_summary.decisions),
                    keywords=list(previous_summary.keywords),
                    covered_until=covered_until,
                    model=self.model,
                    generation_time=generation_time,
                    is_final=is_final,
                )
            else:
                return SummaryResult(
                    version=self._version,
                    highlights="",
                    covered_until=covered_until,
                    model=self.model,
                    generation_time=generation_time,
                    is_final=is_final,
                )

        now = datetime.now().isoformat()
        action_items = []
        for item_data in parsed.get("action_items", []):
            action_items.append(ActionItem(
                id=str(uuid4()),
                content=item_data.get("content", ""),
                owner=item_data.get("owner"),
                deadline=item_data.get("deadline"),
                source_segment=covered_until,
                status=item_data.get("status", "open"),
                priority=item_data.get("priority", "medium"),
                note=None,
                user_edited=False,
                created=now,
                updated=now,
            ))

        highlights = parsed.get("highlights", "") or ""
        decisions = parsed.get("decisions", []) or []
        keywords = parsed.get("keywords", []) or []
        # [Bug #16 修法 B] parse 成功但全空（e.g. Gemma 回中文 key，parsed.get 英文 key 全 miss）
        # → raise 讓 stream_processor 走 fallback，不把空摘要 update 進 session
        if (
            not highlights.strip()
            and not action_items
            and not decisions
            and not keywords
        ):
            raise EmptySummaryError(
                f"Summarizer parsed empty result (raw keys={list(parsed.keys())})"
            )

        result = SummaryResult(
            version=self._version,
            highlights=highlights,
            action_items=action_items,
            decisions=decisions,
            keywords=keywords,
            covered_until=covered_until,
            model=self.model,
            generation_time=generation_time,
            is_final=is_final,
        )
        # [Bug #16 診斷] 最終 SummaryResult 欄位摘要
        logger.warning(
            "[Bug#16-diag] SummaryResult v%d built: "
            "highlights_len=%d, action_items=%d, decisions=%d, keywords=%d, "
            "is_final=%s, gen_time=%.1fs",
            result.version,
            len(result.highlights or ""),
            len(result.action_items),
            len(result.decisions),
            len(result.keywords),
            result.is_final,
            result.generation_time,
        )
        return result

    def _build_initial_prompt(
        self, segments: list[CorrectedSegment],
        participants: list[Participant] | None,
    ) -> str:
        transcript = "\n".join(
            f"[{s.start:.0f}s] {s.corrected_text}" for s in segments
        )
        parts_str = self._format_participants(participants)
        return f"""你是會議摘要助手。請分析以下會議逐字稿，產生結構化摘要。
與會人員：{parts_str}

逐字稿：
{transcript}

請以 JSON 格式回傳，包含以下欄位：
- highlights: 會議重點摘要（字串）
- action_items: 待辦事項列表，每項包含 content, owner, deadline, priority, status
- decisions: 決議事項列表（字串列表）
- keywords: 關鍵詞列表

回傳格式：JSON"""

    def _build_incremental_prompt(
        self, new_segments: list[CorrectedSegment],
        prev_summary: SummaryResult,
        participants: list[Participant] | None,
    ) -> str:
        transcript = "\n".join(
            f"[{s.start:.0f}s] {s.corrected_text}" for s in new_segments
        )
        return f"""前次摘要結果：
重點：{prev_summary.highlights}
Action Items：{self._format_actions(prev_summary.action_items)}
決議：{prev_summary.decisions}
與會人員：{self._format_participants(participants)}

新增逐字稿段落：
{transcript}

請更新會議摘要。保留仍然有效的項目，新增或修改有變化的項目。
回傳 JSON，必須使用以下英文 key（不可翻譯為中文 key）：
- "highlights": 會議重點摘要（字串，繁體中文內容）
- "action_items": 待辦事項陣列，每項物件含英文 key content, owner, deadline, priority, status
- "decisions": 決議事項陣列（字串陣列）
- "keywords": 關鍵詞陣列（字串陣列）

回傳格式：JSON"""

    async def _call_ollama(self, prompt: str) -> str:
        """HTTP POST to Ollama /api/generate"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": self.options,
                },
            )
            resp.raise_for_status()
            return resp.json().get("response", "")

    def _parse_response(self, response: str) -> dict | None:
        """解析 JSON 回應，失敗回傳 None"""
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        return None

    def _format_actions(self, actions: list[ActionItem]) -> str:
        if not actions:
            return "（無）"
        return "\n".join(
            f"- {a.content}（負責人：{a.owner or '未指定'}，"
            f"期限：{a.deadline or '未定'}，優先級：{a.priority}）"
            for a in actions
        )

    def _format_participants(self, participants: list[Participant] | None) -> str:
        if not participants:
            return "（未提供）"
        return ", ".join(
            f"{p.name}{'(' + p.role + ')' if p.role else ''}"
            for p in participants
        )

    def reset(self):
        self._version = 0
