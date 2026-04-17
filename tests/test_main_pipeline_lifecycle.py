"""Pipeline Lifecycle — 聚焦 main.py 的 _run / stop 生命週期 + StreamProcessor 併發行為。

此處 CLI 環境無 GUI driver，不模擬完整 Flet runtime，改以獨立 asyncio 驗證：

Bug #9（_run wrapper，由 main.py 提煉）：
1. Pipeline 正常完成 → 不改 UI（交由 _on_pipeline_done 處理 review 切換）
2. Pipeline 丟例外 → logger.exception + SnackBar + finally 保證 recorder.stop + UI 切 idle
3. Pipeline 被外部 cancel → CancelledError 傳遞 + finally 保證 recorder.stop + UI 切 idle

Bug #11（StreamProcessor fire-and-forget summary）：
- I4：summary 執行期間主迴圈仍持續 consume audio_source（transcribe 不凍結）
- C7：summary task 失敗不得炸主迴圈
- §3.4：停止時 pending summary 先等 pending_summary_wait_sec，超時才 cancel

Bug #10（session lifecycle / stop 語意 / aborted status — Step 2 新增）：
- I1：任何路徑（正常/異常/cancel）session 都必須落盤
- I2：正常停止必先完成 final summary 才 UI 轉場
- I3：pipeline_task.cancel() 僅當安全網（超過 stop_drain_timeout_sec 才啟動）
- I5/I6：status 轉換經由 SessionManager.transition，mode 由 status 衍生
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, AsyncMock

import numpy as np
import pytest
import yaml

from app.data.config_manager import ConfigManager
from app.core.stream_processor import StreamProcessor
from app.core.models import (
    TranscriptSegment, CorrectedSegment, SummaryResult, Session,
)


from app.core.session_manager import SessionManager


# ─────────────────────────────────────────────────────────────
# _run 代理（對應 app/main.py 新的 _run 邏輯，I1/I2/I3/I5/I6）
# 驗證 spec 行為而非 pattern：session.status / save 是否發生 / UI 路由是否正確
# ─────────────────────────────────────────────────────────────


class _FakeRecorder:
    def __init__(self):
        self.stop_requested = False

    async def request_stop(self):
        self.stop_requested = True


async def _recording_run(
    processor_run, recorder, session_mgr, session,
    show_error=None, finalize_ui=None, on_pipeline_done=None,
):
    """main.py on_start_recording._run 的提煉版（對應新 _run / I1/I2/I3/I5）"""
    try:
        await processor_run()
        # sp.run 結束 → session.status 已是 ready（可能含 summary.fallback_reason）
    except asyncio.CancelledError:
        if session.status not in ("ready", "aborted"):
            session_mgr.mark_aborted(session, "stop_timeout")
        raise
    except Exception as e:
        if show_error:
            show_error(e)
        if session.status not in ("ready", "aborted"):
            session_mgr.mark_aborted(session, "pipeline_error")
    finally:
        # I1：所有路徑先 save，再 UI 轉場
        session_mgr.save(session)
        await recorder.request_stop()
        if session.status == "ready" and on_pipeline_done is not None:
            on_pipeline_done(session)
        elif session.status != "ready" and finalize_ui is not None:
            finalize_ui(session)


async def _import_run(
    processor_run, session_mgr, session,
    show_error=None, finalize_ui=None, on_pipeline_done=None,
):
    """main.py on_import_audio._run 的提煉版（無 recorder，其餘同）"""
    try:
        await processor_run()
    except asyncio.CancelledError:
        if session.status not in ("ready", "aborted"):
            session_mgr.mark_aborted(session, "stop_timeout")
        raise
    except Exception as e:
        if show_error:
            show_error(e)
        if session.status not in ("ready", "aborted"):
            session_mgr.mark_aborted(session, "pipeline_error")
    finally:
        session_mgr.save(session)
        if session.status == "ready" and on_pipeline_done is not None:
            on_pipeline_done(session)
        elif session.status != "ready" and finalize_ui is not None:
            finalize_ui(session)


@pytest.fixture
def session_mgr(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "sessions": {"dir": str(sessions_dir)},
    }), encoding="utf-8")
    return SessionManager(ConfigManager(str(config_path)))


# ─────────────────────────────────────────────────────────────
# Bug #9 regression — 以 spec 為基準重寫（status + save + UI 路由）
# 避免只驗 pattern（實驗者 V Phase #4 反思）
# ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recording_normal_completion_saves_as_ready(session_mgr):
    """I1+I2：正常完成 → session.status=ready、已落盤、ready 路由走 _on_pipeline_done"""
    recorder = _FakeRecorder()
    session = session_mgr.create("test", "microphone")
    done_calls, idles = [], []

    async def proc():
        # 模擬 StreamProcessor.run 完成 → session.status=ready
        session_mgr.end_recording(session)
        session_mgr.mark_ready(session)

    await _recording_run(
        proc, recorder, session_mgr, session,
        finalize_ui=lambda s: idles.append(s.status),
        on_pipeline_done=done_calls.append,
    )

    assert session.status == "ready"
    assert session.abort_reason is None
    # I1：session 實際落盤
    loaded = session_mgr.load(session.id)
    assert loaded is not None
    assert loaded.status == "ready"
    # ready 路徑走 _on_pipeline_done，不走 finalize_ui
    assert done_calls == [session]
    assert idles == []
    assert recorder.stop_requested is True


@pytest.mark.asyncio
async def test_recording_exception_transitions_aborted_with_reason(session_mgr):
    """I1+G1：pipeline crash → aborted + abort_reason="pipeline_error"，session 落盤"""
    recorder = _FakeRecorder()
    session = session_mgr.create("test", "microphone")
    errors, finalize_calls = [], []

    async def proc():
        raise RuntimeError("simulated pipeline crash")

    await _recording_run(
        proc, recorder, session_mgr, session,
        show_error=errors.append,
        finalize_ui=lambda s: finalize_calls.append((s.status, s.abort_reason)),
    )

    assert isinstance(errors[0], RuntimeError)
    assert session.status == "aborted"
    assert session.abort_reason == "pipeline_error"
    loaded = session_mgr.load(session.id)
    assert loaded.status == "aborted"
    assert loaded.abort_reason == "pipeline_error"
    assert finalize_calls == [("aborted", "pipeline_error")]
    assert recorder.stop_requested is True


@pytest.mark.asyncio
async def test_recording_cancel_transitions_aborted_stop_timeout(session_mgr):
    """I3+G1：cancel（watchdog）→ aborted + abort_reason="stop_timeout"，session 落盤"""
    recorder = _FakeRecorder()
    session = session_mgr.create("test", "microphone")
    finalize_calls = []

    async def proc():
        await asyncio.sleep(10)

    async def wrapper():
        await _recording_run(
            proc, recorder, session_mgr, session,
            finalize_ui=lambda s: finalize_calls.append((s.status, s.abort_reason)),
        )

    task = asyncio.create_task(wrapper())
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert session.status == "aborted"
    assert session.abort_reason == "stop_timeout"
    loaded = session_mgr.load(session.id)
    assert loaded is not None
    assert loaded.abort_reason == "stop_timeout"
    assert finalize_calls == [("aborted", "stop_timeout")]
    assert recorder.stop_requested is True


@pytest.mark.asyncio
async def test_recording_exception_message_non_empty_for_snackbar(session_mgr):
    """Bug #9 A2：空訊息例外時仍能產生有意義的錯誤文字（與新 save/transition 共存）"""
    session = session_mgr.create("test", "microphone")
    errors = []

    async def proc():
        raise RuntimeError()  # 空訊息

    recorder = _FakeRecorder()
    await _recording_run(
        proc, recorder, session_mgr, session,
        show_error=errors.append,
    )

    err = errors[0]
    err_type = type(err).__name__
    err_msg = str(err) or "(無錯誤訊息)"
    shown = f"錄音處理失敗：{err_type} — {err_msg}"
    assert "RuntimeError" in shown
    assert "(無錯誤訊息)" in shown


@pytest.mark.asyncio
async def test_import_exception_transitions_aborted_and_saves(session_mgr):
    """匯入路徑異常：I1 仍要 save，aborted+pipeline_error"""
    session = session_mgr.create("test", "import")
    errors, finalize_calls = [], []

    async def proc():
        raise ValueError("transcriber blew up mid-import")

    await _import_run(
        proc, session_mgr, session,
        show_error=errors.append,
        finalize_ui=lambda s: finalize_calls.append((s.status, s.abort_reason)),
    )

    assert isinstance(errors[0], ValueError)
    assert session.status == "aborted"
    assert session.abort_reason == "pipeline_error"
    assert session_mgr.load(session.id) is not None
    assert finalize_calls == [("aborted", "pipeline_error")]


@pytest.mark.asyncio
async def test_import_normal_completion_saves_as_ready(session_mgr):
    """匯入正常完成：ready + 走 _on_pipeline_done"""
    session = session_mgr.create("test", "import")
    done_calls, finalize_calls = [], []

    async def proc():
        session_mgr.end_recording(session)
        session_mgr.mark_ready(session)

    await _import_run(
        proc, session_mgr, session,
        finalize_ui=finalize_calls.append,
        on_pipeline_done=done_calls.append,
    )

    assert session.status == "ready"
    assert finalize_calls == []
    assert done_calls == [session]


# ─────────────────────────────────────────────────────────────
# Bug #11 — Summarizer fire-and-forget
# 對應 [[pipeline_lifecycle_architecture_20260416]] §1 I4 / §4 C5-C8
# ─────────────────────────────────────────────────────────────


def _bug11_config(tmp_path, *, pending_wait: int = 60):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "streaming": {
            "summary_interval_sec": 0,  # 每個 chunk 後都可觸發
            "summary_min_new_segments": 1,
            "pending_summary_wait_sec": pending_wait,
        },
        "sessions": {"dir": str(sessions_dir)},
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


def _fake_transcriber_one_per_chunk():
    t = MagicMock()
    counter = [0]

    def transcribe_chunk(audio, chunk_id):
        idx = counter[0]
        counter[0] += 1
        return [TranscriptSegment(
            index=idx, start=float(idx), end=float(idx + 1),
            text=f"seg {idx}", confidence=0.9, chunk_id=chunk_id,
        )]

    t.transcribe_chunk = MagicMock(side_effect=transcribe_chunk)
    return t


def _fake_corrector_passthrough():
    c = MagicMock()
    c.correct = MagicMock(side_effect=lambda s: CorrectedSegment(
        index=s.index, start=s.start, end=s.end,
        original_text=s.text, corrected_text=s.text, corrections=[],
    ))
    return c


def _fake_session_mgr():
    m = MagicMock()
    m.add_segment = MagicMock()
    m.update_summary = MagicMock()
    m.end_recording = MagicMock()
    m.mark_ready = MagicMock()
    return m


def _empty_summary(version=1, is_final=False):
    return SummaryResult(
        version=version, highlights="ok", action_items=[],
        decisions=[], keywords=[], covered_until=0, model="mock",
        generation_time=0.0, is_final=is_final,
    )


@pytest.mark.asyncio
async def test_summarizer_does_not_block_transcription(tmp_path):
    """I4：summary 推理期間主迴圈仍持續 consume audio_source。

    驗證方式：讓第一次週期 summary 卡 slow_sec 秒；期間主迴圈應繼續處理後續 chunks，
    而非停在 summary await。
    """
    config = _bug11_config(tmp_path)
    transcriber = _fake_transcriber_one_per_chunk()
    corrector = _fake_corrector_passthrough()
    session_mgr = _fake_session_mgr()

    summary_started = asyncio.Event()
    release_summary = asyncio.Event()

    summarizer = MagicMock()

    async def slow_generate(segments, previous_summary=None,
                            participants=None, is_final=False):
        if not is_final:
            summary_started.set()
            # 卡到測試放行為止，模擬 Gemma 30-60s 推理
            await release_summary.wait()
        return _empty_summary(is_final=is_final)

    summarizer.generate = AsyncMock(side_effect=slow_generate)

    sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
    session = Session(title="i4 test")

    received_segments: list[CorrectedSegment] = []
    sp.on_segment = lambda seg: received_segments.append(seg)

    segments_at_summary_start: list[int] = []

    async def audio_source():
        for i in range(10):
            yield np.zeros(16000, dtype=np.float32)
            # 讓出 event loop，觸發 summary task 起跑 + 檢查主迴圈是否仍前進
            await asyncio.sleep(0.02)
            if summary_started.is_set() and not segments_at_summary_start:
                segments_at_summary_start.append(len(received_segments))

    run_task = asyncio.create_task(sp.run(audio_source(), session))
    # 等 slow summary 啟動
    await asyncio.wait_for(summary_started.wait(), timeout=2.0)
    # 放行 summary 讓 pipeline 收尾
    release_summary.set()
    await asyncio.wait_for(run_task, timeout=5.0)

    # I4 核心斷言：summary 啟動後主迴圈仍推進過至少一個新 segment
    assert segments_at_summary_start, "summary_started 從未觀察到（timing 問題）"
    segments_during_summary = len(received_segments) - segments_at_summary_start[0]
    assert segments_during_summary >= 1, (
        f"主迴圈在 summary 執行期間凍結 — "
        f"summary 起跑時 {segments_at_summary_start[0]} segments，"
        f"跑完後 {len(received_segments)} segments"
    )


@pytest.mark.asyncio
async def test_summarizer_failure_does_not_crash_pipeline(tmp_path):
    """C7：summary task 內部例外不可 propagate，pipeline 應繼續跑到 final summary"""
    config = _bug11_config(tmp_path)
    transcriber = _fake_transcriber_one_per_chunk()
    corrector = _fake_corrector_passthrough()
    session_mgr = _fake_session_mgr()

    call_count = [0]
    summarizer = MagicMock()

    async def generate(segments, previous_summary=None,
                       participants=None, is_final=False):
        call_count[0] += 1
        if not is_final and call_count[0] == 1:
            raise RuntimeError("Ollama exploded mid-stream")
        return _empty_summary(version=call_count[0], is_final=is_final)

    summarizer.generate = AsyncMock(side_effect=generate)

    sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
    session = Session(title="c7 test")

    async def audio_source():
        for _ in range(3):
            yield np.zeros(16000, dtype=np.float32)
            await asyncio.sleep(0.01)

    # 不應 raise
    await sp.run(audio_source(), session)

    # final summary 仍被呼叫 + pipeline 收尾
    session_mgr.end_recording.assert_called_once()
    session_mgr.mark_ready.assert_called_once()
    # summarizer.generate 至少被呼叫 2 次（1 次炸 + 1 次 final）
    assert call_count[0] >= 2


@pytest.mark.asyncio
async def test_stop_during_summarization_waits_for_pending(tmp_path):
    """§3.4 rule 1：audio_source 結束時 pending summary 正跑 → 等 pending 完成再跑 final"""
    config = _bug11_config(tmp_path, pending_wait=5)
    transcriber = _fake_transcriber_one_per_chunk()
    corrector = _fake_corrector_passthrough()
    session_mgr = _fake_session_mgr()

    summary_started = asyncio.Event()
    pending_done = asyncio.Event()
    summarizer = MagicMock()

    async def generate(segments, previous_summary=None,
                       participants=None, is_final=False):
        if not is_final:
            summary_started.set()
            # 模擬 pending summary 要跑 0.3 秒才完成
            await asyncio.sleep(0.3)
            pending_done.set()
        return _empty_summary(is_final=is_final)

    summarizer.generate = AsyncMock(side_effect=generate)

    sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
    session = Session(title="drain test")

    async def audio_source():
        # 只 yield 一個 chunk 即停，確保 pending summary 在主迴圈結束後仍在跑
        yield np.zeros(16000, dtype=np.float32)
        await asyncio.sleep(0.01)

    await sp.run(audio_source(), session)

    # pending summary 必須被等到完成
    assert pending_done.is_set(), "pending summary 被 drain 前提早 cancel"
    # final summary 也必須跑
    session_mgr.mark_ready.assert_called_once()


@pytest.mark.asyncio
async def test_stop_drain_timeout_cancels_pending_summary(tmp_path):
    """§3.4 rule 2：pending summary 超過 pending_summary_wait_sec 仍沒好 → cancel，仍進 final"""
    config = _bug11_config(tmp_path, pending_wait=0)  # 立即 timeout
    transcriber = _fake_transcriber_one_per_chunk()
    corrector = _fake_corrector_passthrough()
    session_mgr = _fake_session_mgr()

    summarizer = MagicMock()
    summary_cancelled = asyncio.Event()

    async def generate(segments, previous_summary=None,
                       participants=None, is_final=False):
        if not is_final:
            try:
                await asyncio.sleep(10)  # 遠大於 pending_summary_wait_sec
            except asyncio.CancelledError:
                summary_cancelled.set()
                raise
        return _empty_summary(is_final=is_final)

    summarizer.generate = AsyncMock(side_effect=generate)

    sp = StreamProcessor(transcriber, corrector, summarizer, session_mgr, config)
    session = Session(title="timeout test")

    async def audio_source():
        yield np.zeros(16000, dtype=np.float32)
        await asyncio.sleep(0.01)

    await sp.run(audio_source(), session)

    # pending summary 必須被 cancel 而非無限等
    assert summary_cancelled.is_set(), "pending summary 未被 cancel，drain 逾時未生效"
    # 但 final summary 仍要完成，pipeline 走完 mark_ready
    session_mgr.mark_ready.assert_called_once()


# ─────────────────────────────────────────────────────────────
# Bug #10 — Session lifecycle / stop 語意 / aborted status
# 對應 [[pipeline_lifecycle_architecture_20260416]] §1 I1/I2/I3/I5/I6 / §2 C1-C4
# 使用真 SessionManager + 真 StreamProcessor，驗行為結果而非 pattern
# ─────────────────────────────────────────────────────────────


def _bug10_config(tmp_path, **streaming_overrides):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    streaming = {
        "summary_interval_sec": 0,
        "summary_min_new_segments": 1,
        "pending_summary_wait_sec": 5,
        "final_summary_timeout_sec": 5,
        "stop_drain_timeout_sec": 5,
    }
    streaming.update(streaming_overrides)
    config_path.write_text(yaml.dump({
        "streaming": streaming,
        "sessions": {"dir": str(sessions_dir)},
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


@pytest.mark.asyncio
async def test_stop_recording_saves_session_to_disk(tmp_path):
    """I1：甲方按停止後 data/sessions/{id}.json 必須存在且可 load 回來"""
    config = _bug10_config(tmp_path)
    real_session_mgr = SessionManager(config)

    transcriber = _fake_transcriber_one_per_chunk()
    corrector = _fake_corrector_passthrough()

    summarizer = MagicMock()
    summarizer.generate = AsyncMock(return_value=_empty_summary(is_final=True))

    sp = StreamProcessor(transcriber, corrector, summarizer, real_session_mgr, config)
    session = real_session_mgr.create("i1 test", "microphone")

    async def audio_source():
        for _ in range(3):
            yield np.zeros(16000, dtype=np.float32)
            await asyncio.sleep(0.01)

    await sp.run(audio_source(), session)
    real_session_mgr.save(session)  # 模擬 _on_pipeline_done 的 save

    # I1 核心斷言
    loaded = real_session_mgr.load(session.id)
    assert loaded is not None
    assert loaded.status == "ready"
    assert loaded.abort_reason is None


@pytest.mark.asyncio
async def test_stop_recording_transitions_to_review_mode(tmp_path):
    """I2+I5：正常停止 → session.mode=review 由 status 衍生（不走 idle）"""
    config = _bug10_config(tmp_path)
    real_session_mgr = SessionManager(config)
    transcriber = _fake_transcriber_one_per_chunk()
    corrector = _fake_corrector_passthrough()
    summarizer = MagicMock()
    summarizer.generate = AsyncMock(return_value=_empty_summary(is_final=True))

    sp = StreamProcessor(transcriber, corrector, summarizer, real_session_mgr, config)
    session = real_session_mgr.create("i2 test", "microphone")

    async def audio_source():
        yield np.zeros(16000, dtype=np.float32)
        await asyncio.sleep(0.01)

    await sp.run(audio_source(), session)

    assert session.status == "ready"
    # mode 是 @property，由 status 衍生（不是獨立欄位）
    assert session.mode == "review"


@pytest.mark.asyncio
async def test_stop_recording_produces_final_summary(tmp_path):
    """spec L139：停止 → is_final=True 摘要存在 summary_history，session.summary 為 final"""
    config = _bug10_config(tmp_path)
    real_session_mgr = SessionManager(config)
    transcriber = _fake_transcriber_one_per_chunk()
    corrector = _fake_corrector_passthrough()

    summarizer = MagicMock()
    summarizer.generate = AsyncMock(return_value=_empty_summary(version=1, is_final=True))

    sp = StreamProcessor(transcriber, corrector, summarizer, real_session_mgr, config)
    session = real_session_mgr.create("final test", "microphone")

    async def audio_source():
        yield np.zeros(16000, dtype=np.float32)
        await asyncio.sleep(0.01)

    await sp.run(audio_source(), session)

    assert session.summary is not None
    assert session.summary.is_final is True
    assert any(s.is_final for s in session.summary_history)


@pytest.mark.asyncio
async def test_final_summary_timeout_falls_back_to_ready_not_aborted(tmp_path):
    """G2：final summary timeout → 用最近週期版當 final + fallback_reason，仍進 ready（不 aborted）"""
    config = _bug10_config(tmp_path, final_summary_timeout_sec=0)  # 立即 timeout
    real_session_mgr = SessionManager(config)
    transcriber = _fake_transcriber_one_per_chunk()
    corrector = _fake_corrector_passthrough()

    # 先預設一個週期 summary（fake：第一次非 final 回傳正常；第二次 final 卡到 timeout）
    summarizer = MagicMock()

    async def generate(segments, previous_summary=None, participants=None, is_final=False):
        if is_final:
            await asyncio.sleep(10)  # 超過 final_summary_timeout_sec=0
        return _empty_summary(version=1, is_final=False)

    summarizer.generate = AsyncMock(side_effect=generate)

    sp = StreamProcessor(transcriber, corrector, summarizer, real_session_mgr, config)
    session = real_session_mgr.create("g2 test", "microphone")

    async def audio_source():
        # 多個 chunks，讓週期 summary 有機會先完成一次
        for _ in range(3):
            yield np.zeros(16000, dtype=np.float32)
            await asyncio.sleep(0.02)

    await sp.run(audio_source(), session)

    # status 仍 ready（降級而非崩潰）
    assert session.status == "ready"
    # final summary 標了 fallback_reason
    assert session.summary is not None
    assert session.summary.is_final is True
    assert session.summary.fallback_reason == "ollama_timeout"


@pytest.mark.asyncio
async def test_pipeline_crash_transitions_aborted_and_saves(tmp_path):
    """I1+C3+G1：pipeline 主迴圈 crash → session 被 main.py _run 轉 aborted 並落盤"""
    config = _bug10_config(tmp_path)
    real_session_mgr = SessionManager(config)
    session = real_session_mgr.create("crash test", "microphone")

    # 先塞幾個 segments 進 session，證明「partial 也要保」
    from app.core.models import CorrectedSegment
    for i in range(5):
        real_session_mgr.add_segment(session, CorrectedSegment(
            index=i, start=float(i), end=float(i + 1),
            original_text=f"s{i}", corrected_text=f"s{i}", corrections=[],
        ))

    recorder = _FakeRecorder()

    async def proc_that_crashes():
        raise RuntimeError("transcriber died")

    errors, finalize_calls = [], []
    await _recording_run(
        proc_that_crashes, recorder, real_session_mgr, session,
        show_error=errors.append,
        finalize_ui=finalize_calls.append,
    )

    # I1：落盤
    loaded = real_session_mgr.load(session.id)
    assert loaded is not None
    assert loaded.status == "aborted"
    assert loaded.abort_reason == "pipeline_error"
    # 原本已處理的 segments 保留
    assert len(loaded.segments) == 5
    # UI 應以 status 驅動轉 review（有 segments）
    assert session.status == "aborted"


@pytest.mark.asyncio
async def test_stop_timeout_transitions_aborted_stop_timeout_and_saves(tmp_path):
    """I3+T8+G1：stop drain 超時 cancel → aborted + abort_reason=stop_timeout，save 已處理 segments"""
    config = _bug10_config(tmp_path)
    real_session_mgr = SessionManager(config)
    session = real_session_mgr.create("timeout test", "microphone")

    from app.core.models import CorrectedSegment
    for i in range(3):
        real_session_mgr.add_segment(session, CorrectedSegment(
            index=i, start=float(i), end=float(i + 1),
            original_text=f"s{i}", corrected_text=f"s{i}", corrections=[],
        ))

    recorder = _FakeRecorder()

    async def hung_proc():
        await asyncio.sleep(10)

    async def wrapper():
        await _recording_run(
            hung_proc, recorder, real_session_mgr, session,
        )

    task = asyncio.create_task(wrapper())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    loaded = real_session_mgr.load(session.id)
    assert loaded.status == "aborted"
    assert loaded.abort_reason == "stop_timeout"
    assert len(loaded.segments) == 3  # partial 不丟


@pytest.mark.asyncio
async def test_session_mode_is_derived_from_status(tmp_path):
    """I5+G4：Session.mode 是 @property，狀態變化即時反映"""
    config = _bug10_config(tmp_path)
    mgr = SessionManager(config)
    session = mgr.create("mode test", "microphone")

    assert session.status == "recording"
    assert session.mode == "live"

    mgr.end_recording(session)
    assert session.status == "processing"
    assert session.mode == "live"  # processing 仍為 live

    mgr.mark_ready(session)
    assert session.status == "ready"
    assert session.mode == "review"

    # aborted 也應是 review（部分資料可審閱）
    session2 = mgr.create("mode test 2", "microphone")
    mgr.mark_aborted(session2, "pipeline_error")
    assert session2.status == "aborted"
    assert session2.mode == "review"


@pytest.mark.asyncio
async def test_transition_rejects_invalid_status_and_requires_abort_reason(tmp_path):
    """I6：transition 拒絕不合法 status；aborted 必須帶 abort_reason"""
    config = _bug10_config(tmp_path)
    mgr = SessionManager(config)
    session = mgr.create("transition test", "microphone")

    with pytest.raises(ValueError):
        mgr.transition(session, "nonsense_status")

    with pytest.raises(ValueError):
        mgr.transition(session, "aborted")  # 少 abort_reason

    # 正常帶 reason 應成功
    mgr.transition(session, "aborted", abort_reason="stop_timeout")
    assert session.abort_reason == "stop_timeout"


# ─────────────────────────────────────────────────────────────
# Bug #13 — cf.Future-aware stop drain 輪詢
# 對應 [[flet_0.84_async_lifecycle_20260417]] §5 方案 A（輪詢）
# pipeline_task 是 concurrent.futures.Future（page.run_task 回傳），
# 不能 asyncio.shield / wait_for / await — 只用 .done() / .cancel()
# ─────────────────────────────────────────────────────────────


class _FakeCfFuture:
    """模擬 concurrent.futures.Future 的最小介面（無 __await__）。

    重點：拔掉 __await__ 證明被測 code 不走 asyncio 語法。
    cf.Future 在 run_coroutine_threadsafe 下 .cancel() 會 propagate 到底層 task（§1.3）。
    """

    def __init__(self):
        self._done = False
        self._cancelled = False

    def done(self):
        return self._done or self._cancelled

    def cancel(self):
        self._cancelled = True
        return True

    def set_done(self):
        """測試用：模擬 task 自然完成"""
        self._done = True


async def _stop_drain_poll(task, timeout_sec: float, poll_interval: float = 0.05):
    """main.py _stop_recording_async 的 drain+cancel 核心邏輯提煉（方案 A 輪詢）。

    只用 task.done() / task.cancel()，不碰 asyncio.shield / wait_for / await task。
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_sec

    while not task.done():
        if loop.time() >= deadline:
            task.cancel()
            break
        await asyncio.sleep(poll_interval)

    if not task.done():
        cancel_deadline = loop.time() + 2
        while not task.done():
            if loop.time() >= cancel_deadline:
                break
            await asyncio.sleep(poll_interval)


@pytest.mark.asyncio
async def test_stop_drain_cf_future_normal_completion():
    """C9+C10：cf.Future 自然完成（pipeline drain 成功）→ 不觸發 cancel"""
    future = _FakeCfFuture()

    async def mark_done():
        await asyncio.sleep(0.1)
        future.set_done()

    asyncio.create_task(mark_done())
    await _stop_drain_poll(future, timeout_sec=5)

    assert future.done()
    assert not future._cancelled, "正常完成路徑不該觸發 cancel"


@pytest.mark.asyncio
async def test_stop_drain_cf_future_timeout_triggers_cancel():
    """C9+C10+I3：cf.Future 永不完成 → 超時 → cancel（watchdog safety net）"""
    future = _FakeCfFuture()  # 永不 set_done

    await _stop_drain_poll(future, timeout_sec=0.2)

    assert future._cancelled, "超時路徑必須觸發 task.cancel()"
    assert future.done(), "cancel 後 done() 應回 True"


@pytest.mark.asyncio
async def test_stop_drain_cf_future_already_done_returns_immediately():
    """C9：task 已 done → _stop_recording_async 不多等（已 done 才進來的場景）"""
    future = _FakeCfFuture()
    future.set_done()

    import time
    start = time.monotonic()
    await _stop_drain_poll(future, timeout_sec=10)
    elapsed = time.monotonic() - start

    assert elapsed < 0.5, f"已 done 的 task 不應等待，但花了 {elapsed:.1f}s"
    assert not future._cancelled


@pytest.mark.asyncio
async def test_stop_drain_does_not_use_asyncio_await_on_cf_future():
    """C9 核心：被測 code 不對 cf.Future 做 asyncio.shield / wait_for / await。

    _FakeCfFuture 沒有 __await__，若 _stop_drain_poll 嘗試 await 它會 TypeError。
    此 test 能通過就證明 code path 安全。
    """
    future = _FakeCfFuture()
    assert not hasattr(future, "__await__"), "fake 不應有 __await__"

    # 模擬短暫後完成
    async def mark_done():
        await asyncio.sleep(0.05)
        future.set_done()

    asyncio.create_task(mark_done())
    # 不 raise TypeError = code 沒嘗試 await cf.Future
    await _stop_drain_poll(future, timeout_sec=5)
