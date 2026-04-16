"""Bug #9 Pipeline Lifecycle — 聚焦 main.py 的 _run / stop 生命週期修復邏輯。

此處不模擬完整 Flet runtime（CLI 無 GUI driver），改為以獨立 asyncio 驗證
`_run` 模式在以下三種情境下的行為：
1. Pipeline 正常完成 → 不改 UI（交由 _on_pipeline_done 處理 review 切換）
2. Pipeline 丟例外 → logger.exception + SnackBar + finally 保證 recorder.stop + UI 切 idle
3. Pipeline 被外部 cancel → CancelledError 傳遞 + finally 保證 recorder.stop + UI 切 idle
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest


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
