"""Flet App 進入點 — 初始化所有模組，啟動 UI"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future

import flet as ft

from app.data.config_manager import ConfigManager
from app.core.knowledge_base import KnowledgeBase
from app.core.transcriber import Transcriber
from app.core.audio_recorder import AudioRecorder
from app.core.audio_importer import AudioImporter
from app.core.rag_corrector import RAGCorrector
from app.core.summarizer import Summarizer
from app.core.session_manager import SessionManager
from app.core.exporter import Exporter
from app.core.stream_processor import StreamProcessor
from app.data.feedback_store import FeedbackStore
from app.core.models import Participant, Session

from app.ui.main_view import MainView
from app.ui.dashboard_view import DashboardView
from app.ui.settings_view import SettingsView
from app.ui.terms_view import TermsView
from app.ui.feedback_view import FeedbackView

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(page: ft.Page):
    # ── 設定 ──
    config = ConfigManager("config/default.yaml")

    # ── 核心模組初始化 ──
    session_mgr = SessionManager(config)
    feedback_store = FeedbackStore(config)
    exporter = Exporter()

    # ML 模組延遲初始化（啟動時不阻塞 UI）
    kb: KnowledgeBase | None = None
    transcriber: Transcriber | None = None
    corrector: RAGCorrector | None = None
    summarizer: Summarizer | None = None
    processor: StreamProcessor | None = None
    recorder: AudioRecorder | None = None
    # Bug #13：page.run_task 回傳 concurrent.futures.Future（非 asyncio.Task）
    pipeline_task: Future | None = None

    # ── UI 建構 ──
    main_view = MainView(config)

    def _show_pipeline_error(err: BaseException, origin: str):
        """彈出使用者可見的 Pipeline 錯誤提示（Bug #9 A2：訊息保證非空 + 長停留）"""
        err_type = type(err).__name__
        err_msg = str(err) or "(無錯誤訊息)"
        text = f"{origin}失敗：{err_type} — {err_msg}"
        try:
            page.show_dialog(ft.SnackBar(
                content=ft.Text(text),
                duration=30000,  # 30 秒，避免甲方錯過
            ))
            page.update()
        except Exception:
            logger.exception("Failed to show error SnackBar")

    stop_drain_timeout_sec = config.get("streaming.stop_drain_timeout_sec", 90)

    def _finalize_ui(session: Session):
        """根據 session.status（SSoT，I5）決定 UI 模態：
        - ready → review（正常完成路徑，_on_pipeline_done 已走過；此處保險再觸發一次）
        - aborted：有 segments → review(partial)；無 segments → idle
        """
        try:
            if session.status == "ready":
                dashboard.set_mode("review", session)
            elif session.status == "aborted":
                if session.segments:
                    dashboard.set_mode("review", session)
                else:
                    dashboard.set_mode("idle", None)
            main_view.status_bar.set_meeting_mode(False)
            page.update()
        except Exception:
            logger.exception("Dashboard finalize UI failed")

    def _persist_session(session: Session):
        """I1：任何離開 recording/processing 的路徑都必須先落盤"""
        try:
            session_mgr.save(session)
        except Exception:
            logger.exception("Session save failed (I1 violation risk)")

    # Dashboard 回呼
    def on_start_recording(title, participants):
        nonlocal kb, transcriber, corrector, summarizer, processor, recorder, pipeline_task
        _ensure_ml_modules()

        session = session_mgr.create(title, "microphone", participants)
        dashboard.set_mode("live", session)

        recorder = AudioRecorder(config)
        # Bug #15：把新建 recorder 注入 dashboard（constructor 階段 recorder is None）
        dashboard.set_audio_recorder(recorder)
        local_recorder = recorder  # finally 區塊用，避免 nonlocal 在過程中被覆蓋

        processor = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        processor.on_segment = dashboard.on_new_segment
        processor.on_summary = dashboard.on_new_summary
        processor.on_status_change = lambda s: _on_pipeline_done(session) if s == "ready" else None

        async def _run():
            # I1/I2/I3：正常 → ready；cancel → aborted(stop_timeout)；crash → aborted(pipeline_error)
            try:
                await processor.run(local_recorder.start(), session)
                # sp.run 結束 → session.status 已是 ready（可能含 summary.fallback_reason）
            except asyncio.CancelledError:
                logger.info("Recording pipeline cancelled (watchdog / force stop)")
                if session.status not in ("ready", "aborted"):
                    session_mgr.mark_aborted(session, "stop_timeout")
                raise
            except Exception as e:
                logger.exception("Recording pipeline error")
                _show_pipeline_error(e, "錄音處理")
                if session.status not in ("ready", "aborted"):
                    session_mgr.mark_aborted(session, "pipeline_error")
            finally:
                # I1：所有路徑先 save（冪等：_on_pipeline_done 可能已存一次）
                _persist_session(session)
                try:
                    await local_recorder.request_stop()
                except Exception:
                    logger.exception("Recorder request_stop failed in finally")
                # UI 轉場（ready 由 _on_pipeline_done 負責，aborted 由 _finalize_ui 處理）
                if session.status != "ready":
                    _finalize_ui(session)

        pipeline_task = page.run_task(_run)

    def on_import_audio(title, participants, file_path):
        nonlocal kb, transcriber, corrector, summarizer, processor, pipeline_task
        _ensure_ml_modules()

        session = session_mgr.create(title, "import", participants)
        dashboard.set_mode("live", session)

        importer = AudioImporter(config)

        processor = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        processor.on_segment = dashboard.on_new_segment
        processor.on_summary = dashboard.on_new_summary
        processor.on_status_change = lambda s: _on_pipeline_done(session) if s == "ready" else None

        async def _run():
            # I1：匯入路徑異常也必須先落盤，再 UI 轉場
            try:
                await processor.run(importer.import_file(file_path), session)
            except asyncio.CancelledError:
                logger.info("Import pipeline cancelled")
                if session.status not in ("ready", "aborted"):
                    session_mgr.mark_aborted(session, "stop_timeout")
                raise
            except Exception as e:
                logger.exception("Import pipeline error")
                _show_pipeline_error(e, "音檔匯入處理")
                if session.status not in ("ready", "aborted"):
                    session_mgr.mark_aborted(session, "pipeline_error")
            finally:
                _persist_session(session)
                if session.status != "ready":
                    _finalize_ui(session)

        pipeline_task = page.run_task(_run)

    async def _stop_recording_async():
        """正常停止路徑（I3）：軟停 recorder → drain pipeline → 超時才 cancel。

        Bug #13 fix：pipeline_task 是 concurrent.futures.Future（page.run_task 回傳），
        不能 asyncio.shield / wait_for / await。改用 .done() 輪詢（方案 A）。
        cf.Future.cancel() 在 run_coroutine_threadsafe 特化下會 propagate 到底層 asyncio task（OK）。
        """
        nonlocal recorder, pipeline_task
        if recorder is not None:
            try:
                await recorder.request_stop()
            except Exception:
                logger.exception("recorder.request_stop failed in on_stop_recording")

        task = pipeline_task
        if task is None or task.done():
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + stop_drain_timeout_sec

        # Phase 1：等 pipeline 自然 drain（recorder 已設 stop flag，async gen 會自然收尾）
        while not task.done():
            if loop.time() >= deadline:
                logger.warning(
                    "Pipeline drain exceeded %ss — forcing cancel (watchdog safety net)",
                    stop_drain_timeout_sec,
                )
                task.cancel()
                break
            await asyncio.sleep(0.2)

        # Phase 2：cancel 後等 task 真正完成（_run finally 需跑完 save + UI 轉場）
        if not task.done():
            cancel_deadline = loop.time() + 10
            while not task.done():
                if loop.time() >= cancel_deadline:
                    logger.error(
                        "Pipeline task still not done 10s after cancel — giving up"
                    )
                    break
                await asyncio.sleep(0.2)

    def on_stop_recording():
        # Flet 回呼為同步；將軟停 + drain + watchdog 邏輯丟到 event loop
        page.run_task(_stop_recording_async)

    def _on_pipeline_done(session: Session):
        # I2：save → review → status_bar → page.update（順序固定，避免 race）
        session_mgr.save(session)
        dashboard.set_mode("review", session)
        main_view.status_bar.set_meeting_mode(False)
        page.update()

    def _ensure_ml_modules():
        nonlocal kb, transcriber, corrector, summarizer
        if transcriber is None:
            main_view.status_bar.update_ollama(False, loading=True)
            page.update()

            kb = KnowledgeBase(config)
            transcriber = Transcriber(config)
            corrector = RAGCorrector(kb)
            summarizer = Summarizer(config)

            main_view.status_bar.update_ollama(True)
            main_view.status_bar.update_term_count(len(kb.list_terms()))
            page.update()

    # ── 各頁面 ──
    dashboard = DashboardView(
        page=page, config=config, session_manager=session_mgr,
        knowledge_base=None, feedback_store=feedback_store, exporter=exporter,
        audio_recorder=recorder,
        on_start_recording=on_start_recording,
        on_import_audio=on_import_audio,
        on_stop_recording=on_stop_recording,
    )

    settings_view = SettingsView(config)

    # terms_view 和 feedback_view 需要 kb，延遲建構
    class LazyTermsView(ft.Container):
        def __init__(self):
            super().__init__(expand=True)

        def build(self):
            _ensure_ml_modules()
            return TermsView(page, kb)

        def did_mount(self):
            _ensure_ml_modules()
            self.content = TermsView(page, kb)
            self.update()

    class LazyFeedbackView(ft.Container):
        def __init__(self):
            super().__init__(expand=True)

        def did_mount(self):
            _ensure_ml_modules()
            self.content = FeedbackView(kb, feedback_store)
            self.update()

    # ── 組裝主視窗 ──
    main_view.dashboard_view = dashboard
    main_view.terms_view = LazyTermsView()
    main_view.feedback_view = LazyFeedbackView()
    main_view.settings_view = settings_view

    main_view.build(page)

    # 初始狀態列
    main_view.status_bar.update_temp_usage()


if __name__ == "__main__":
    ft.run(main)
