"""Integration smoke tests — 跨模組 wiring 驗證。

V Phase 第六輪反思：contract test 綠燈 ≠ 符合跨模組 wiring。
Bug #15 根因：main.py constructor 階段 `recorder: AudioRecorder | None = None`，
傳給 DashboardView 的 audio_recorder=recorder 是 None；
on_start_recording 時 `recorder = AudioRecorder(...)` 只 rebind main scope 的 name，
dashboard 內部 self._audio_recorder 永遠是 None（Python closure late binding）。

此處驗證：
1. DashboardView.set_audio_recorder setter 存在（公開 API contract）
2. setter 注入後 internal ref 確實更新
3. main.py on_start_recording 確實呼叫 set_audio_recorder（防 regression）
4. Mic Test A1 fallback：_audio_recorder is None 時不 early return

參考：bug_report_flet_api_20260406.md §Bug #15 + devlog_20260417_verifier_vphase6.md
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


# ─── 共用 fixture ───


@pytest.fixture
def fake_page():
    """MagicMock Page — 提供 on_resize / run_task / show_dialog / pop_dialog。"""
    page = MagicMock()
    page.on_resize = None
    page.window = MagicMock()
    page.window.width = 1400
    return page


@pytest.fixture
def minimal_config(tmp_path):
    """最小 ConfigManager — 用真實 config/default.yaml（不寫 temp）。"""
    from app.data.config_manager import ConfigManager
    default_cfg = Path("config/default.yaml")
    if not default_cfg.exists():
        pytest.skip("config/default.yaml 不存在")
    return ConfigManager(str(default_cfg))


@pytest.fixture
def dashboard(fake_page, minimal_config, tmp_path, monkeypatch):
    """建構 DashboardView — 模擬 main.py 第 246-253 行 constructor 階段。

    此時 audio_recorder=None（還沒 on_start_recording），復現 Bug #15 壞狀態。
    """
    from app.core.session_manager import SessionManager
    from app.data.feedback_store import FeedbackStore
    from app.core.exporter import Exporter
    from app.ui.dashboard_view import DashboardView

    # 隔離 sessions/feedback 到 tmp
    monkeypatch.setattr(minimal_config, "get",
                        lambda k, d=None: str(tmp_path / k.split(".")[-1])
                        if k.endswith("_dir") or k == "sessions.dir" or k == "feedback.dir"
                        else minimal_config.__class__.get(minimal_config, k, d))
    session_mgr = SessionManager(minimal_config)
    feedback_store = FeedbackStore(minimal_config)
    exporter = Exporter()

    return DashboardView(
        page=fake_page,
        config=minimal_config,
        session_manager=session_mgr,
        knowledge_base=None,
        feedback_store=feedback_store,
        exporter=exporter,
        audio_recorder=None,  # ← 復現 main.py 當前行為
    )


# ─── Test 1: setter API contract ───


class TestSetAudioRecorderAPI:
    """DashboardView.set_audio_recorder setter 是 Bug #15 修復的公開 API。"""

    def test_set_audio_recorder_method_exists(self):
        """setter 方法必須存在 — 防未來誤刪"""
        from app.ui.dashboard_view import DashboardView
        assert hasattr(DashboardView, 'set_audio_recorder'), (
            "DashboardView.set_audio_recorder 不存在 — Bug #15 修復已被移除？"
        )
        assert callable(DashboardView.set_audio_recorder)

    def test_dashboard_constructor_leaves_audio_recorder_none_when_passed_none(
        self, dashboard,
    ):
        """constructor 傳 None → 內部 _audio_recorder 就是 None（復現 Bug #15 壞狀態）"""
        assert dashboard._audio_recorder is None, (
            "Constructor 沒有把 audio_recorder 存進 _audio_recorder — "
            "Bug #15 壞狀態無法復現"
        )

    def test_set_audio_recorder_updates_internal_ref(
        self, dashboard, minimal_config,
    ):
        """setter 注入後 internal ref 確實更新（Bug #15 修復核心）"""
        from app.core.audio_recorder import AudioRecorder

        recorder = AudioRecorder(minimal_config)
        dashboard.set_audio_recorder(recorder)

        assert dashboard._audio_recorder is recorder, (
            "set_audio_recorder 沒把 recorder 存進 _audio_recorder"
        )

    def test_set_audio_recorder_can_rebind(self, dashboard, minimal_config):
        """二次呼叫 setter 應能重綁（例如使用者錄完再開一場）"""
        from app.core.audio_recorder import AudioRecorder

        rec1 = AudioRecorder(minimal_config)
        rec2 = AudioRecorder(minimal_config)
        dashboard.set_audio_recorder(rec1)
        dashboard.set_audio_recorder(rec2)

        assert dashboard._audio_recorder is rec2


# ─── Test 2: main.py wiring contract ───


class TestMainWiringContract:
    """驗證 main.py on_start_recording 確實呼叫 dashboard.set_audio_recorder。

    這是 V6 反思的直接回應：contract test 綠燈不夠，要驗跨模組 wiring。
    """

    def test_main_on_start_recording_calls_set_audio_recorder(self):
        """main.py 原始碼內 on_start_recording 函式必須呼叫 dashboard.set_audio_recorder"""
        from app import main as main_mod

        source = inspect.getsource(main_mod)
        # 定位 on_start_recording 函式區塊
        assert "def on_start_recording" in source, "main.py on_start_recording 不存在"

        # 粗略切出 on_start_recording 函式 body（到下一個 def 前）
        idx = source.index("def on_start_recording")
        # 取到下一個同層 def（def on_import_audio）
        next_def = source.index("\n    def on_import_audio", idx)
        on_start_block = source[idx:next_def]

        assert "dashboard.set_audio_recorder" in on_start_block, (
            "main.py on_start_recording 沒有呼叫 dashboard.set_audio_recorder — "
            "Bug #15 修復已被移除？Mic Live/Mic Test 會回到 dead 狀態"
        )


# ─── Test 3: Mic Test A1 fallback ───


class TestMicTestFallback:
    """Bug #15 A1：idle 階段 _audio_recorder is None 時，_handle_mic_test
    應臨時建 AudioRecorder 而非 silent early return。"""

    def test_handle_mic_test_no_longer_short_circuits_on_none_recorder(
        self, dashboard, monkeypatch,
    ):
        """_audio_recorder is None 時 _handle_mic_test 不得直接 return。

        成功條件：臨時 recorder 被建立（AudioRecorder constructor 被呼叫）
        """
        # 先進 idle 模式以建立 _mic_test_container
        dashboard.set_mode("idle")

        # 用 counter mock 掉 AudioRecorder 建構，避免真的 open sounddevice
        construct_count = {"n": 0}
        original_cls = None

        # 只 mock dashboard_view 模組引用的 AudioRecorder（避免影響其他模組）
        from app.ui import dashboard_view as dv_mod

        class _FakeRecorder:
            def __init__(self, config):
                construct_count["n"] += 1
                self.started = False

            def start_level_probe(self):
                self.started = True

            def stop_level_probe(self):
                self.started = False

            def get_current_level(self):
                return -50.0

        monkeypatch.setattr(dv_mod, "AudioRecorder", _FakeRecorder)

        # 也 mock run_task 避免真的排入 event loop
        dashboard._page_ref.run_task = MagicMock()

        assert dashboard._audio_recorder is None  # 前置條件：Bug #15 壞狀態
        dashboard._handle_mic_test(e=None)

        assert construct_count["n"] == 1, (
            "_handle_mic_test 在 _audio_recorder is None 時沒有建立 temp recorder — "
            "Bug #15 A1 fallback 失效，Mic Test 仍 dead"
        )
        # 應該已啟動 probe（走到 active_recorder.start_level_probe()）
        assert dashboard._mic_test_temp_recorder is not None
        assert dashboard._mic_test_temp_recorder.started is True
