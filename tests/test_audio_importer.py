"""測試 AudioImporter — 音檔匯入、切段、WAV 暫存"""

import asyncio

import numpy as np
import pytest
import yaml
from scipy.io import wavfile

from app.data.config_manager import ConfigManager
from app.core.audio_importer import AudioImporter


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
            "transcribe_chunk_sec": 2,  # 2 秒一段
            "audio_chunk_duration_sec": 6,  # 6 秒存 WAV
        },
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


@pytest.fixture
def importer(config):
    return AudioImporter(config)


def _create_wav(path, duration_sec: float, sample_rate: int = 16000):
    """建立測試 WAV 檔"""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), dtype=np.float32)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    wavfile.write(str(path), sample_rate, audio)
    return path


class TestAudioImporter:
    def test_init(self, importer):
        assert importer.transcribe_chunk_sec == 2
        assert importer.save_chunk_sec == 6

    @pytest.mark.asyncio
    async def test_import_wav(self, importer, tmp_path):
        """匯入 WAV 應 yield numpy 區塊"""
        wav_path = _create_wav(tmp_path / "test.wav", 5.0)
        chunks = []
        async for chunk in importer.import_file(str(wav_path)):
            chunks.append(chunk)
            assert isinstance(chunk, np.ndarray)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_chunk_count(self, importer, tmp_path):
        """10 秒音檔 / 2 秒 = 5 個區塊"""
        wav_path = _create_wav(tmp_path / "test.wav", 10.0)
        chunks = []
        async for chunk in importer.import_file(str(wav_path)):
            chunks.append(chunk)
        assert len(chunks) == 5

    @pytest.mark.asyncio
    async def test_chunk_size(self, importer, tmp_path):
        """每個區塊約 2 秒 = 32000 samples"""
        wav_path = _create_wav(tmp_path / "test.wav", 6.0)
        chunks = []
        async for chunk in importer.import_file(str(wav_path)):
            chunks.append(chunk)
        for chunk in chunks:
            # 每段約 32000 samples（2 秒 * 16000）
            assert abs(len(chunk) - 32000) <= 100

    @pytest.mark.asyncio
    async def test_wav_temp_saved(self, importer, tmp_path, config):
        """暫存 WAV 應產出"""
        wav_path = _create_wav(tmp_path / "test.wav", 8.0)
        async for _ in importer.import_file(str(wav_path)):
            pass
        paths = importer.get_temp_paths()
        assert len(paths) >= 1

    @pytest.mark.asyncio
    async def test_get_duration(self, importer, tmp_path):
        """應回傳正確時長"""
        wav_path = _create_wav(tmp_path / "test.wav", 5.0)
        dur = importer.get_duration(str(wav_path))
        assert abs(dur - 5.0) < 0.5

    @pytest.mark.asyncio
    async def test_short_file(self, importer, tmp_path):
        """短於一個 chunk 的音檔仍應 yield"""
        wav_path = _create_wav(tmp_path / "short.wav", 0.5)
        chunks = []
        async for chunk in importer.import_file(str(wav_path)):
            chunks.append(chunk)
        assert len(chunks) == 1
