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
    pipeline_task: asyncio.Task | None = None  # Bug #9: 保留 _run handle 供 stop 取消

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

    # Dashboard 回呼
    def on_start_recording(title, participants):
        nonlocal kb, transcriber, corrector, summarizer, processor, recorder, pipeline_task
        _ensure_ml_modules()

        session = session_mgr.create(title, "microphone", participants)
        dashboard.set_mode("live", session)

        recorder = AudioRecorder(config)
        local_recorder = recorder  # finally 區塊用，避免 nonlocal 在過程中被覆蓋

        processor = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
        processor.on_segment = dashboard.on_new_segment
        processor.on_summary = dashboard.on_new_summary
        processor.on_status_change = lambda s: _on_pipeline_done(session) if s == "ready" else None

        async def _run():
            # Bug #9 A1+C1: CancelledError 分流 + logger.exception + finally 保證 recorder 停 + UI 回 idle
            completed_normally = False
            try:
                await processor.run(local_recorder.start(), session)
                completed_normally = True  # 正常完成 → _on_pipeline_done 已切到 review
            except asyncio.CancelledError:
                logger.info("Recording pipeline cancelled by user")
                raise
            except Exception as e:
                logger.exception("Recording pipeline error")
                _show_pipeline_error(e, "錄音處理")
            finally:
                try:
                    await local_recorder.stop()
                except Exception:
                    logger.exception("Recorder stop failed in finally")
                if not completed_normally:
                    # 異常或取消 → 錄音 session 資料不完整，回 idle（bug report C1 決策）
                    try:
                        dashboard.set_mode("idle", None)
                        main_view.status_bar.set_meeting_mode(False)
                        page.update()
                    except Exception:
                        logger.exception("Dashboard reset to idle failed")

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
            # Bug #9 A3+C1: 匯入路徑同 A1，但異常時進 review（已 yield 的部分 segments 可保留）
            completed_normally = False
            try:
                await processor.run(importer.import_file(file_path), session)
                completed_normally = True
            except asyncio.CancelledError:
                logger.info("Import pipeline cancelled by user")
                raise
            except Exception as e:
                logger.exception("Import pipeline error")
                _show_pipeline_error(e, "音檔匯入處理")
            finally:
                if not completed_normally:
                    try:
                        dashboard.set_mode("review", session)
                        main_view.status_bar.set_meeting_mode(False)
                        page.update()
                    except Exception:
                        logger.exception("Dashboard reset to review failed")

        pipeline_task = page.run_task(_run)

    def on_stop_recording():
        # Bug #9 B1: 先請 recorder 停（讓 generator 自然收尾走 final summary），
        # 同時 cancel pipeline_task 當作卡死安全網（已 done 時為 no-op）。
        nonlocal recorder, pipeline_task
        if recorder:
            # recorder.stop() 只是設旗標，用 page.run_task 確保跑在 event loop 上
            page.run_task(recorder.stop)
        if pipeline_task is not None and not pipeline_task.done():
            pipeline_task.cancel()

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
    ft.run(main)
