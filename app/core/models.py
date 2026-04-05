"""資料模型 — 完全對齊 data_schema spec"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from uuid import uuid4


# ── 2. 轉錄 Segment ──

@dataclass
class TranscriptSegment:
    index: int
    start: float
    end: float
    text: str
    confidence: float
    chunk_id: int


# ── 3. 校正結果 ──

@dataclass
class Correction:
    segment_index: int
    original: str
    corrected: str
    term_id: str
    similarity: float


@dataclass
class CorrectedSegment:
    index: int
    start: float
    end: float
    original_text: str
    corrected_text: str
    corrections: list[Correction] = field(default_factory=list)


# ── 4. 摘要結果 ──

@dataclass
class ActionItem:
    id: str
    content: str
    owner: str | None
    deadline: str | None
    source_segment: int
    status: str  # "open" | "done" | "dropped"
    priority: str  # "high" | "medium" | "low"
    note: str | None
    user_edited: bool  # True 時 AI 週期更新不覆蓋
    created: str
    updated: str


@dataclass
class SummaryResult:
    version: int
    highlights: str
    action_items: list[ActionItem] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    covered_until: int = 0
    model: str = ""
    generation_time: float = 0.0
    is_final: bool = False


# ── 5. Session ──

@dataclass
class Participant:
    name: str
    role: str | None = None
    source: str = "manual"  # "manual" | "ai_inferred"


@dataclass
class UserEdits:
    highlights_edited: str | None = None
    decisions_edited: list[str] | None = None
    edited_at: str = ""


# ── 6. 回饋紀錄 ──

@dataclass
class FeedbackEntry:
    segment_index: int
    correction_index: int  # -1 表示遺漏回報
    type: str  # "correct" | "wrong" | "missed"
    term_id: str | None = None
    expected: str | None = None
    note: str | None = None
    timestamp: str = ""


@dataclass
class SessionFeedback:
    session_id: str
    created: str
    entries: list[FeedbackEntry] = field(default_factory=list)
    summary_rating: int = 0  # 1-5
    summary_note: str | None = None


# ── 5. Session（完整定義）──

@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    ended: str | None = None
    participants: list[Participant] = field(default_factory=list)
    mode: str = "live"  # "live" | "review"
    status: str = "recording"  # recording | processing | ready | exported
    audio_paths: list[str] = field(default_factory=list)
    audio_source: str = "microphone"  # "microphone" | "import"
    audio_duration: float = 0.0
    segments: list[CorrectedSegment] = field(default_factory=list)
    summary_history: list[SummaryResult] = field(default_factory=list)
    summary: SummaryResult | None = None
    user_edits: UserEdits | None = None
    feedback: list[FeedbackEntry] | None = None
    export_path: str | None = None


# ── 序列化工具 ──

def to_json(obj) -> str:
    """dataclass → JSON string"""
    return json.dumps(asdict(obj), ensure_ascii=False, indent=2)


def from_json(cls, json_str: str):
    """JSON string → dataclass（支援巢狀）"""
    data = json.loads(json_str)
    return _from_dict(cls, data)


def _from_dict(cls, data: dict):
    """遞迴還原 dataclass"""
    import dataclasses
    if not dataclasses.is_dataclass(cls):
        return data

    field_types = {f.name: f.type for f in dataclasses.fields(cls)}
    kwargs = {}
    for key, val in data.items():
        if key not in field_types:
            continue
        ft = field_types[key]
        resolved = _resolve_type(ft, val)
        kwargs[key] = resolved
    return cls(**kwargs)


def _resolve_type(type_hint, val):
    """根據 type hint 決定如何還原值"""
    if val is None:
        return None

    # 處理 str 型態的 type hint（如 "list[ActionItem]"）
    if isinstance(type_hint, str):
        # list[X]
        if type_hint.startswith("list["):
            inner = type_hint[5:-1]
            inner_cls = _get_model_class(inner)
            if inner_cls and isinstance(val, list):
                return [_from_dict(inner_cls, item) if isinstance(item, dict) else item
                        for item in val]
            return val
        # X | None
        if " | None" in type_hint:
            base = type_hint.replace(" | None", "")
            base_cls = _get_model_class(base)
            if base_cls and isinstance(val, dict):
                return _from_dict(base_cls, val)
            return val
        return val

    return val


def _get_model_class(name: str):
    """從模組內找 dataclass"""
    import sys
    module = sys.modules[__name__]
    cls = getattr(module, name, None)
    import dataclasses
    if cls and dataclasses.is_dataclass(cls):
        return cls
    return None
