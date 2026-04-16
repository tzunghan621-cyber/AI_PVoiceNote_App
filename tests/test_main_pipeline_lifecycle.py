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


async def _recording_run(processor_run, recorder, on_error, on_reset_idle):
    """main.py on_start_recording._run 的提煉版（移除 Flet 依賴）"""
    completed_normally = False
    try:
        await processor_run()
        completed_normally = True
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        on_error(e)
    finally:
        await recorder.stop()
        if not completed_normally:
            on_reset_idle()


async def _import_run(processor_run, on_error, on_reset_review):
    """main.py on_import_audio._run 的提煉版"""
    completed_normally = False
    try:
        await processor_run()
        completed_normally = True
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        on_error(e)
    finally:
        if not completed_normally:
            on_reset_review()


class _FakeRecorder:
    def __init__(self):
        self.stopped = False

    async def stop(self):
        self.stopped = True


@pytest.mark.asyncio
async def test_recording_normal_completion_does_not_reset_ui():
    """正常完成：不觸發 idle reset（交由 _on_pipeline_done）"""
    recorder = _FakeRecorder()
    errors, idles = [], []

    async def proc():
        await asyncio.sleep(0)  # 模擬 await

    await _recording_run(
        proc, recorder,
        on_error=errors.append,
        on_reset_idle=lambda: idles.append(1),
    )

    assert errors == []
    assert idles == []  # 正常完成不應該 reset idle
    assert recorder.stopped is True  # 但 recorder 仍要停（redundant but safe）


@pytest.mark.asyncio
async def test_recording_exception_resets_to_idle_and_stops_recorder():
    """Bug #9 核心情境：Pipeline 丟例外，finally 必須收尾"""
    recorder = _FakeRecorder()
    errors, idles = [], []

    async def proc():
        raise RuntimeError("simulated pipeline crash")

    await _recording_run(
        proc, recorder,
        on_error=errors.append,
        on_reset_idle=lambda: idles.append(1),
    )

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert idles == [1]  # UI 必須回 idle（避免殭屍）
    assert recorder.stopped is True  # recorder 必須停


@pytest.mark.asyncio
async def test_recording_cancelled_propagates_but_finally_runs():
    """Bug #9 B1：cancel 時 CancelledError 要傳到 task owner，但 finally 必須跑完"""
    recorder = _FakeRecorder()
    errors, idles = [], []

    async def proc():
        await asyncio.sleep(10)  # 會被 cancel 截斷

    async def wrapper():
        await _recording_run(
            proc, recorder,
            on_error=errors.append,
            on_reset_idle=lambda: idles.append(1),
        )

    task = asyncio.create_task(wrapper())
    await asyncio.sleep(0)  # 讓 task 進入 proc 的 await
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert errors == []  # cancel 不走 except Exception
    assert idles == [1]  # 但 finally 必須切回 idle
    assert recorder.stopped is True


@pytest.mark.asyncio
async def test_recording_exception_message_non_empty_for_snackbar():
    """Bug #9 A2：空訊息例外時仍能產生有意義的錯誤文字"""
    errors = []

    async def proc():
        raise RuntimeError()  # 空訊息

    recorder = _FakeRecorder()
    await _recording_run(
        proc, recorder,
        on_error=errors.append,
        on_reset_idle=lambda: None,
    )

    err = errors[0]
    # main.py 的 _show_pipeline_error 取用 type(e).__name__ + str(e)
    err_type = type(err).__name__
    err_msg = str(err) or "(無錯誤訊息)"
    shown = f"錄音處理失敗：{err_type} — {err_msg}"
    assert "RuntimeError" in shown
    assert "(無錯誤訊息)" in shown  # 即使 str(e) 為空，仍能顯示型別與 fallback


@pytest.mark.asyncio
async def test_import_exception_resets_to_review_not_idle():
    """Bug #9 C1：匯入路徑異常時保留部分資料，回 review 而非 idle"""
    errors, reviews = [], []

    async def proc():
        raise ValueError("transcriber blew up mid-import")

    await _import_run(
        proc,
        on_error=errors.append,
        on_reset_review=lambda: reviews.append(1),
    )

    assert len(errors) == 1
    assert reviews == [1]


@pytest.mark.asyncio
async def test_import_normal_completion_no_review_reset():
    """匯入正常完成：交由 _on_pipeline_done，不走 review reset"""
    errors, reviews = [], []

    async def proc():
        await asyncio.sleep(0)

    await _import_run(
        proc,
        on_error=errors.append,
        on_reset_review=lambda: reviews.append(1),
    )

    assert errors == []
    assert reviews == []


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
