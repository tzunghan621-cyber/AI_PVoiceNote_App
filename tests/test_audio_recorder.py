"""測試 AudioRecorder — 雙層串流、async generator yield、WAV 暫存"""

import asyncio

import numpy as np
import pytest
import yaml
from unittest.mock import patch, MagicMock

from app.data.config_manager import ConfigManager
from app.core.audio_recorder import AudioRecorder


@pytest.fixture
def config(tmp_path):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "temp_dir": str(temp_dir),
        },
        "streaming": {
            "transcribe_chunk_sec": 1,  # 1 秒小區塊（測試用）
            "audio_chunk_duration_sec": 3,  # 3 秒大區塊（測試用）
        },
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


@pytest.fixture
def recorder(config):
    return AudioRecorder(config)


def _simulate_audio_input(recorder, total_sec: float):
    """模擬音訊輸入：在背景 task 中往 queue 送資料，然後 stop"""
    sample_rate = recorder.sample_rate
    # 每次送 0.1 秒的音訊
    chunk_size = int(sample_rate * 0.1)
    total_chunks = int(total_sec / 0.1)

    async def _feed():
        for i in range(total_chunks):
            data = np.random.randn(chunk_size, 1).astype(np.float32) * 0.1
            await recorder._audio_queue.put(data)
            await asyncio.sleep(0.001)
        await asyncio.sleep(0.05)
        await recorder.request_stop()

    return _feed


class TestAudioRecorder:
    def test_init(self, recorder):
        assert recorder.sample_rate == 16000
        assert recorder.transcribe_chunk_sec == 1
        assert recorder.save_chunk_sec == 3

    @pytest.mark.asyncio
    async def test_yields_transcribe_chunks(self, recorder):
        """應每 transcribe_chunk_sec yield 一個小區塊"""
        feed = _simulate_audio_input(recorder, total_sec=2.5)

        chunks = []
        with patch("sounddevice.InputStream"):
            asyncio.create_task(feed())
            async for chunk in recorder.start():
                chunks.append(chunk)

        # 2.5 秒 / 1 秒 = 至少 2 個完整小區塊
        assert len(chunks) >= 2
        for chunk in chunks:
            assert isinstance(chunk, np.ndarray)

    @pytest.mark.asyncio
    async def test_chunk_duration(self, recorder):
        """每個 yield 的小區塊約等於 transcribe_chunk_sec"""
        feed = _simulate_audio_input(recorder, total_sec=3.0)

        chunks = []
        with patch("sounddevice.InputStream"):
            asyncio.create_task(feed())
            async for chunk in recorder.start():
                chunks.append(chunk)

        # 每個完整小區塊約 16000 samples（1秒）
        for chunk in chunks[:-1]:  # 最後一個可能是殘餘
            duration = len(chunk) / recorder.sample_rate
            assert 0.9 <= duration <= 1.2

    @pytest.mark.asyncio
    async def test_wav_temp_files(self, recorder, config):
        """大區塊暫存 WAV 應在 save_chunk_sec 後產出"""
        temp_dir = config.get("audio.temp_dir")
        feed = _simulate_audio_input(recorder, total_sec=4.0)

        with patch("sounddevice.InputStream"):
            asyncio.create_task(feed())
            async for _ in recorder.start():
                pass

        # 4 秒 / 3 秒大區塊 = 至少 1 個完整暫存 + 1 個殘餘
        paths = recorder.get_temp_paths()
        assert len(paths) >= 1

    @pytest.mark.asyncio
    async def test_request_stop(self, recorder):
        """request_stop 後 generator 結束（軟停止）"""
        feed = _simulate_audio_input(recorder, total_sec=1.0)

        chunks = []
        with patch("sounddevice.InputStream"):
            asyncio.create_task(feed())
            async for chunk in recorder.start():
                chunks.append(chunk)

        assert not recorder._recording

    @pytest.mark.asyncio
    async def test_empty_recording(self, recorder):
        """極短錄音不崩潰"""
        feed = _simulate_audio_input(recorder, total_sec=0.3)

        chunks = []
        with patch("sounddevice.InputStream"):
            asyncio.create_task(feed())
            async for chunk in recorder.start():
                chunks.append(chunk)

        # 可能有殘餘 chunk
        assert isinstance(chunks, list)
