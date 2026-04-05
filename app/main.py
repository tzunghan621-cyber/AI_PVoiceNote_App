"""Flet App 進入點 — 初始化所有模組，啟動 UI"""

from __future__ import annotations

import asyncio
import logging

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

    # ── UI 建構 ──
    main_view = MainView(config)

    # Dashboard 回呼
    def on_start_recording(title, participants):
        nonlocal kb, transcriber, corrector, summarizer, processor, recorder
        _ensure_ml_modules()

        session = session_mgr.create(title, "microphone", participants)
        dashboard.set_mode("live", session)

        recorder = AudioRecorder(config)

        processor = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        processor.on_segment = dashboard.on_new_segment
        processor.on_summary = dashboard.on_new_summary
        processor.on_status_change = lambda s: _on_pipeline_done(session) if s == "ready" else None

        async def _run():
            try:
                await processor.run(recorder.start(), session)
            except Exception as e:
                logger.error(f"Pipeline error: {e}")
                page.snack_bar = ft.SnackBar(content=ft.Text(f"處理失敗：{e}"))
                page.snack_bar.open = True
                page.update()

        page.run_task(_run)

    def on_import_audio(title, participants, file_path):
        nonlocal kb, transcriber, corrector, summarizer, processor
        _ensure_ml_modules()

        session = session_mgr.create(title, "import", participants)
        dashboard.set_mode("live", session)

        importer = AudioImporter(config)

        processor = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        processor.on_segment = dashboard.on_new_segment
        processor.on_summary = dashboard.on_new_summary
        processor.on_status_change = lambda s: _on_pipeline_done(session) if s == "ready" else None

        async def _run():
            try:
                await processor.run(importer.import_file(file_path), session)
            except Exception as e:
                logger.error(f"Pipeline error: {e}")
                page.snack_bar = ft.SnackBar(content=ft.Text(f"處理失敗：{e}"))
                page.snack_bar.open = True
                page.update()

        page.run_task(_run)

    def on_stop_recording():
        nonlocal recorder
        if recorder:
            asyncio.ensure_future(recorder.stop())

    def _on_pipeline_done(session: Session):
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
    ft.app(target=main)
