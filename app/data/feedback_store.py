"""回饋紀錄讀寫"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

from app.data.config_manager import ConfigManager
from app.core.models import FeedbackEntry, SessionFeedback


class FeedbackStore:
    def __init__(self, config: ConfigManager):
        self.feedback_dir = Path(config.get("feedback.dir", "data/feedback"))
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_feedback: SessionFeedback):
        """儲存回饋紀錄"""
        path = self.feedback_dir / f"{session_feedback.session_id}.json"
        data = asdict(session_feedback)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, session_id: str) -> SessionFeedback | None:
        """載入單一 session 的回饋"""
        path = self.feedback_dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionFeedback(
            session_id=data["session_id"],
            created=data["created"],
            entries=[FeedbackEntry(**e) for e in data.get("entries", [])],
            summary_rating=data.get("summary_rating", 0),
            summary_note=data.get("summary_note"),
        )

    def list_all(self) -> list[SessionFeedback]:
        """載入全部回饋"""
        results = []
        for path in sorted(self.feedback_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            results.append(SessionFeedback(
                session_id=data["session_id"],
                created=data["created"],
                entries=[FeedbackEntry(**e) for e in data.get("entries", [])],
                summary_rating=data.get("summary_rating", 0),
                summary_note=data.get("summary_note"),
            ))
        return results

    def get_term_stats(self) -> dict[str, dict]:
        """彙整每個 term_id 的回饋統計"""
        all_fb = self.list_all()
        if not all_fb:
            return {}
        stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"correct": 0, "wrong": 0, "missed": 0}
        )
        for fb in all_fb:
            for entry in fb.entries:
                if entry.term_id:
                    stats[entry.term_id][entry.type] += 1
        return dict(stats)

    def get_high_frequency_misses(self, threshold: int = 3) -> list[str]:
        """回傳高頻遺漏的期望值文字（用於 auto_suggest 候選）"""
        all_fb = self.list_all()
        miss_counts: dict[str, int] = defaultdict(int)
        for fb in all_fb:
            for entry in fb.entries:
                if entry.type == "missed" and entry.expected:
                    miss_counts[entry.expected] += 1
        return [text for text, count in miss_counts.items() if count >= threshold]
