"""串流管線控制器 — 協調 錄音→轉錄→校正→週期摘要"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator, Callable

import numpy as np

from app.data.config_manager import ConfigManager
from app.core.models import CorrectedSegment, SummaryResult, Session

logger = logging.getLogger(__name__)


class StreamProcessor:
    def __init__(self, transcriber, rag_corrector, summarizer,
                 session_manager, config: ConfigManager):
        self.transcriber = transcriber
        self.corrector = rag_corrector
        self.summarizer = summarizer
        self.session_mgr = session_manager
        self.summary_interval = config.get("streaming.summary_interval_sec", 180)
        self.min_new_segments = config.get("streaming.summary_min_new_segments", 10)
        self.pending_summary_wait_sec = config.get(
            "streaming.pending_summary_wait_sec", 60
        )
        self.final_summary_timeout_sec = config.get(
            "streaming.final_summary_timeout_sec", 120
        )
        self._summarizing = False
        # I4：週期 summary 以 background task 執行，主迴圈不 await
        self._summary_task: asyncio.Task | None = None

        # 事件回呼（UI 綁定用）
        self.on_segment: Callable[[CorrectedSegment], None] | None = None
        self.on_summary: Callable[[SummaryResult], None] | None = None
        self.on_status_change: Callable[[str], None] | None = None

    async def _run_summary_async(
        self,
        session: Session,
        segments_snapshot: list[CorrectedSegment],
        previous_summary: SummaryResult | None,
    ):
        """週期 summary fire-and-forget 執行體（I4：不阻塞 audio_source consume）"""
        try:
            summary = await self.summarizer.generate(
                segments_snapshot,
                previous_summary=previous_summary,
                participants=session.participants,
            )
            self.session_mgr.update_summary(session, summary)
            if self.on_summary:
                self.on_summary(summary)
        except asyncio.CancelledError:
            raise
        except Exception:
            # C7：summary task 內部例外不可 propagate，否則主迴圈死掉（Bug #9 重現）
            logger.exception("Periodic summary generation failed")
        finally:
            self._summarizing = False

    async def _drain_pending_summary(self) -> bool:
        """等 pending 週期 summary 完成（最多 pending_summary_wait_sec），超時 cancel。

        Returns: True 若 pending summary 被 timeout cancel（供 final fallback 紀錄原因）
        """
        task = self._summary_task
        if task is None or task.done():
            return False
        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                timeout=self.pending_summary_wait_sec,
            )
            return False
        except asyncio.TimeoutError:
            logger.warning(
                "Pending periodic summary exceeded %ss — cancelling",
                self.pending_summary_wait_sec,
            )
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            return True

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

            # 3. 週期摘要觸發（I4：fire-and-forget，主迴圈不 await summary）
            elapsed = time.time() - last_summary_time
            if (elapsed >= self.summary_interval
                    and segments_since_summary >= self.min_new_segments
                    and not self._summarizing):
                self._summarizing = True
                # Snapshot：fire 下一個 task 前固定 segments + previous_summary，
                # 避免 task 執行期間主迴圈改到同一份 state
                segments_snapshot = list(session.segments)
                previous_snapshot = session.summary
                self._summary_task = asyncio.create_task(
                    self._run_summary_async(
                        session, segments_snapshot, previous_snapshot,
                    )
                )
                last_summary_time = time.time()
                segments_since_summary = 0

        # 錄音結束：等 pending 週期 summary（最多 pending_summary_wait_sec）後再跑 final
        pending_cancelled = await self._drain_pending_summary()

        # 產生最終摘要
        self.session_mgr.end_recording(session)
        if self.on_status_change:
            self.on_status_change("processing")

        # G2：final summary 有 timeout / Ollama 失敗的 fallback（對應 I1 資料保全優先）
        final_summary = await self._run_final_summary(session, pending_cancelled)
        self.session_mgr.update_summary(session, final_summary)
        # 不論 fallback 與否皆進 ready（降級而非崩潰 — system_overview §6 原則 2）
        self.session_mgr.mark_ready(session)

        if self.on_summary:
            self.on_summary(final_summary)
        if self.on_status_change:
            self.on_status_change("ready")

    async def _run_final_summary(
        self, session: Session, pending_timeout: bool,
    ) -> SummaryResult:
        """final summary 帶 timeout 與 fallback（G2）。

        - timeout → 用最近週期 summary 當 final，標 fallback_reason="ollama_timeout"
        - Ollama 失敗 → 同上但 fallback_reason="ollama_failure"
        - 若 pending 週期 summary 超時被 cancel，用 fallback_reason="pending_summary_timeout"
        - 皆仍 transition 進 ready（對應 system_overview §6 原則 2：降級而非崩潰）
        """
        try:
            return await asyncio.wait_for(
                self.summarizer.generate(
                    session.segments,
                    previous_summary=session.summary,
                    participants=session.participants,
                    is_final=True,
                ),
                timeout=self.final_summary_timeout_sec,
            )
        except asyncio.CancelledError:
            # main.py watchdog 的 cancel 走這裡 — 讓它傳上去由 _run 處理 aborted
            raise
        except asyncio.TimeoutError:
            logger.warning(
                "Final summary timed out after %ss — using fallback",
                self.final_summary_timeout_sec,
            )
            return self._build_fallback_final(session, "ollama_timeout")
        except Exception:
            logger.exception("Final summary failed — using fallback")
            reason = "pending_summary_timeout" if pending_timeout else "ollama_failure"
            return self._build_fallback_final(session, reason)

    def _build_fallback_final(
        self, session: Session, reason: str,
    ) -> SummaryResult:
        """fallback：有最近週期 summary → 複用並標 is_final；無則產空殼 final"""
        last = session.summary
        if last is not None:
            return SummaryResult(
                version=last.version + 1,
                highlights=last.highlights,
                action_items=list(last.action_items),
                decisions=list(last.decisions),
                keywords=list(last.keywords),
                covered_until=last.covered_until,
                model=last.model,
                generation_time=0.0,
                is_final=True,
                fallback_reason=reason,
            )
        return SummaryResult(
            version=1,
            highlights="(摘要生成失敗，已保留逐字稿供手動整理)",
            is_final=True,
            fallback_reason=reason,
        )
