"""串流管線控制器 — 協調 錄音→轉錄→校正→週期摘要"""

from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Callable

import numpy as np

from app.data.config_manager import ConfigManager
from app.core.models import CorrectedSegment, SummaryResult, Session


class StreamProcessor:
    def __init__(self, transcriber, rag_corrector, summarizer,
                 session_manager, config: ConfigManager):
        self.transcriber = transcriber
        self.corrector = rag_corrector
        self.summarizer = summarizer
        self.session_mgr = session_manager
        self.summary_interval = config.get("streaming.summary_interval_sec", 180)
        self.min_new_segments = config.get("streaming.summary_min_new_segments", 10)
        self._summarizing = False

        # 事件回呼（UI 綁定用）
        self.on_segment: Callable[[CorrectedSegment], None] | None = None
        self.on_summary: Callable[[SummaryResult], None] | None = None
        self.on_status_change: Callable[[str], None] | None = None

    async def run(self, audio_source: AsyncIterator[np.ndarray],
                  session: Session):
        """主迴圈：消費音訊串流，驅動整條 pipeline"""
        last_summary_time = time.time()
        segments_since_summary = 0
        chunk_id = 0

        async for audio_chunk in audio_source:
            # 1. 轉錄（to_thread 避免 CPU 密集操作阻塞 event loop）
            new_segments = await asyncio.to_thread(
                self.transcriber.transcribe_chunk, audio_chunk, chunk_id
            )
            chunk_id += 1

            # 2. 逐條校正 + 送 UI
            for seg in new_segments:
                corrected = self.corrector.correct(seg)
                self.session_mgr.add_segment(session, corrected)
                if self.on_segment:
                    self.on_segment(corrected)
                segments_since_summary += 1

            # 3. 檢查是否觸發週期摘要
            elapsed = time.time() - last_summary_time
            if (elapsed >= self.summary_interval
                    and segments_since_summary >= self.min_new_segments
                    and not self._summarizing):
                self._summarizing = True
                summary = await self.summarizer.generate(
                    session.segments,
                    previous_summary=session.summary,
                    participants=session.participants,
                )
                self.session_mgr.update_summary(session, summary)
                if self.on_summary:
                    self.on_summary(summary)
                last_summary_time = time.time()
                segments_since_summary = 0
                self._summarizing = False

        # 錄音結束：產生最終摘要
        self.session_mgr.end_recording(session)
        if self.on_status_change:
            self.on_status_change("processing")

        final_summary = await self.summarizer.generate(
            session.segments,
            previous_summary=session.summary,
            participants=session.participants,
            is_final=True,
        )
        self.session_mgr.update_summary(session, final_summary)
        self.session_mgr.mark_ready(session)

        if self.on_summary:
            self.on_summary(final_summary)
        if self.on_status_change:
            self.on_status_change("ready")
