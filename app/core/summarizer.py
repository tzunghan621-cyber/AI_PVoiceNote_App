"""週期性摘要 — Gemma 4 透過 Ollama 產生會議重點/Actions/決議"""

from __future__ import annotations

import json
import time
from datetime import datetime
from uuid import uuid4

import httpx

from app.data.config_manager import ConfigManager
from app.core.models import (
    CorrectedSegment, SummaryResult, ActionItem, Participant,
)


class Summarizer:
    def __init__(self, config: ConfigManager):
        self.model = config.get("ollama.model", "gemma4:e4b")
        self.base_url = config.get("ollama.base_url", "http://localhost:11434")
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

        self._version += 1
        covered_until = segments[-1].index if segments else 0

        parsed = self._parse_response(response)
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

        return SummaryResult(
            version=self._version,
            highlights=parsed.get("highlights", ""),
            action_items=action_items,
            decisions=parsed.get("decisions", []),
            keywords=parsed.get("keywords", []),
            covered_until=covered_until,
            model=self.model,
            generation_time=generation_time,
            is_final=is_final,
        )

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

請更新會議重點、Action Items、決議事項。
保留仍然有效的項目，新增或修改有變化的項目。
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
