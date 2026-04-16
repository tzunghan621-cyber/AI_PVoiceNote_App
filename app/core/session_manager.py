"""會議生命週期管理"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.data.config_manager import ConfigManager
from app.core.models import (
    Session, CorrectedSegment, SummaryResult, Participant,
    UserEdits, Correction, ActionItem, from_json,
)

logger = logging.getLogger(__name__)

# 合法的 status 值（G1：新增 aborted）
_VALID_STATUSES = {"recording", "processing", "ready", "exported", "aborted"}


class SessionManager:
    def __init__(self, config: ConfigManager):
        self.sessions_dir = Path(config.get("sessions.dir", "data/sessions"))
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self, title: str | None, audio_source: str,
        participants: list[Participant] | None = None,
    ) -> Session:
        return Session(
            id=str(uuid4()),
            title=title or f"會議 {datetime.now():%Y-%m-%d %H:%M}",
            created=datetime.now().isoformat(),
            ended=None,
            participants=participants or [],
            status="recording",
            abort_reason=None,
            audio_paths=[],
            audio_source=audio_source,
            audio_duration=0.0,
            segments=[],
            summary_history=[],
            summary=None,
            user_edits=None,
            feedback=None,
            export_path=None,
        )

    def add_segment(self, session: Session, segment: CorrectedSegment):
        session.segments.append(segment)

    def update_summary(self, session: Session, summary: SummaryResult):
        session.summary_history.append(summary)
        session.summary = summary

    def transition(
        self,
        session: Session,
        new_status: str,
        abort_reason: str | None = None,
    ):
        """原子化狀態轉換（I6：status 變更唯一入口，UI/main.py 不可直接改 session.status）

        新增 aborted 狀態時需帶 abort_reason；其餘 status 會清空 abort_reason。
        進入 aborted/ready 狀態時若尚未 end_recording 則補時間戳（I1 保證可審閱）。
        """
        if new_status not in _VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")
        if new_status == "aborted" and not abort_reason:
            raise ValueError("abort_reason is required when transitioning to aborted")

        old_status = session.status
        session.status = new_status
        session.abort_reason = abort_reason if new_status == "aborted" else None

        # 進入 processing/ready/aborted 時若未設 ended，補時間戳
        if new_status in ("processing", "ready", "aborted") and session.ended is None:
            session.ended = datetime.now().isoformat()

        logger.info(
            "Session %s transition: %s → %s (abort_reason=%s)",
            session.id, old_status, new_status, abort_reason,
        )

    def end_recording(self, session: Session):
        """錄音主迴圈結束 → processing（透過 transition 統一走）"""
        self.transition(session, "processing")

    def mark_ready(self, session: Session):
        """final summary 完成 → ready（mode 由 status 衍生）"""
        self.transition(session, "ready")

    def mark_aborted(self, session: Session, reason: str):
        """異常路徑收尾 → aborted（I1：已有 segments 應配合 save 落盤）"""
        self.transition(session, "aborted", abort_reason=reason)

    def save_user_edits(self, session: Session, edits: UserEdits):
        session.user_edits = edits

    def save(self, session: Session):
        """落盤為 JSON（冪等：多次呼叫同一 session 不出錯）"""
        path = self.sessions_dir / f"{session.id}.json"
        data = asdict(session)
        # mode 為 @property，asdict 不會包含 — 手動寫入供外部檢視
        data["mode"] = session.mode
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self, session_id: str) -> Session | None:
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._dict_to_session(data)

    def list_sessions(self) -> list[dict]:
        """輕量清單（id, title, date, status, mode — mode 由 status 衍生）"""
        results = []
        for path in sorted(self.sessions_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            status = data["status"]
            mode = "live" if status in ("recording", "processing") else "review"
            results.append({
                "id": data["id"],
                "title": data["title"],
                "created": data["created"],
                "status": status,
                "mode": mode,
            })
        return results

    def delete_audio(self, session: Session):
        """[M-1] UI 確認後呼叫，刪除暫存音檔"""
        for p in session.audio_paths:
            Path(p).unlink(missing_ok=True)
        session.audio_paths = []

    def _dict_to_session(self, data: dict) -> Session:
        """從 dict 還原 Session（含巢狀物件）"""
        participants = [
            Participant(**p) for p in data.get("participants", [])
        ]
        segments = [
            CorrectedSegment(
                index=s["index"], start=s["start"], end=s["end"],
                original_text=s["original_text"],
                corrected_text=s["corrected_text"],
                corrections=[Correction(**c) for c in s.get("corrections", [])],
            )
            for s in data.get("segments", [])
        ]
        summary_history = [
            self._dict_to_summary(sh)
            for sh in data.get("summary_history", [])
        ]
        summary = (
            self._dict_to_summary(data["summary"])
            if data.get("summary") else None
        )
        user_edits = (
            UserEdits(**data["user_edits"])
            if data.get("user_edits") else None
        )

        return Session(
            id=data["id"],
            title=data["title"],
            created=data["created"],
            ended=data.get("ended"),
            participants=participants,
            status=data["status"],
            abort_reason=data.get("abort_reason"),
            audio_paths=data.get("audio_paths", []),
            audio_source=data.get("audio_source", "microphone"),
            audio_duration=data.get("audio_duration", 0.0),
            segments=segments,
            summary_history=summary_history,
            summary=summary,
            user_edits=user_edits,
            feedback=None,
            export_path=data.get("export_path"),
        )

    def _dict_to_summary(self, data: dict) -> SummaryResult:
        action_items = [
            ActionItem(**ai) for ai in data.get("action_items", [])
        ]
        return SummaryResult(
            version=data["version"],
            highlights=data["highlights"],
            action_items=action_items,
            decisions=data.get("decisions", []),
            keywords=data.get("keywords", []),
            covered_until=data.get("covered_until", 0),
            model=data.get("model", ""),
            generation_time=data.get("generation_time", 0.0),
            is_final=data.get("is_final", False),
            fallback_reason=data.get("fallback_reason"),
        )
