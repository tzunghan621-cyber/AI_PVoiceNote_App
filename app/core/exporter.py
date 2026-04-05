"""Markdown 匯出 — 依 data_schema#7 格式"""

from __future__ import annotations

from pathlib import Path

from app.core.models import Session


class Exporter:
    def export(self, session: Session, output_path: str):
        """匯出 Markdown，不刪除音檔（M-1）"""
        md = self._build_markdown(session)
        Path(output_path).write_text(md, encoding="utf-8")
        session.status = "exported"
        session.export_path = output_path

    def _build_markdown(self, session: Session) -> str:
        parts: list[str] = []

        # ── Frontmatter ──
        duration = self._format_duration(session.audio_duration)
        participant_names = [p.name for p in session.participants]
        parts.append("---")
        parts.append(f"title: 會議摘要 — {session.title}")
        parts.append(f"date: {session.created[:10]}")
        parts.append(f"duration: {duration}")
        parts.append(f"participants: [{', '.join(participant_names)}]")
        parts.append("source: AI_PVoiceNote_App")
        parts.append("tags:")
        parts.append("  - 會議摘要")
        parts.append("---")
        parts.append("")

        # ── 標題 ──
        parts.append(f"# 會議摘要 — {session.title}")
        parts.append("")

        # ── 與會人員 ──
        parts.append("## 與會人員")
        parts.append("")
        for p in session.participants:
            role_str = f"（{p.role}）" if p.role else ""
            parts.append(f"- {p.name}{role_str}")
        parts.append("")

        # ── 摘要（優先 user_edits）──
        highlights = self._get_highlights(session)
        parts.append("## 摘要")
        parts.append("")
        parts.append(highlights)
        parts.append("")

        # ── 待辦事項 ──
        parts.append("## 待辦事項")
        parts.append("")
        action_items = (
            session.summary.action_items if session.summary else []
        )
        for item in action_items:
            checkbox = "x" if item.status == "done" else " "
            detail = f"（負責人：{item.owner or '未指定'}，期限：{item.deadline or '未定'}，優先級：{item.priority}）"
            parts.append(f"- [{checkbox}] {item.content}{detail}")
        parts.append("")

        # ── 決議事項（優先 user_edits）──
        decisions = self._get_decisions(session)
        parts.append("## 決議事項")
        parts.append("")
        for d in decisions:
            parts.append(f"- {d}")
        parts.append("")

        # ── 關鍵詞 ──
        keywords = session.summary.keywords if session.summary else []
        parts.append("## 關鍵詞")
        parts.append("")
        parts.append(", ".join(keywords))
        parts.append("")

        # ── 逐字稿 ──
        parts.append("---")
        parts.append("")
        parts.append("## 逐字稿")
        parts.append("")
        for seg in session.segments:
            timestamp = self._format_timestamp(seg.start)
            parts.append(f"### [{timestamp}]")
            parts.append(seg.corrected_text)
            # 校正標記
            for c in seg.corrections:
                parts.append(
                    f"~~{c.original}~~ → **{c.corrected}**（校正：{c.term_id}）"
                )
            parts.append("")

        return "\n".join(parts)

    def _get_highlights(self, session: Session) -> str:
        if session.user_edits and session.user_edits.highlights_edited:
            return session.user_edits.highlights_edited
        if session.summary:
            return session.summary.highlights
        return ""

    def _get_decisions(self, session: Session) -> list[str]:
        if session.user_edits and session.user_edits.decisions_edited:
            return session.user_edits.decisions_edited
        if session.summary:
            return session.summary.decisions
        return []

    def _format_duration(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _format_timestamp(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
