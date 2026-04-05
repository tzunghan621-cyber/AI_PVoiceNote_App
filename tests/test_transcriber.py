"""測試 Transcriber — 音訊轉錄產出 segments，index 遞增

需要載入 faster-whisper 模型，記憶體需求較大。
獨立執行：python -m pytest tests/test_transcriber.py -v -m slow
"""

import numpy as np
import pytest
import yaml

pytestmark = pytest.mark.slow

from app.data.config_manager import ConfigManager
from app.core.transcriber import Transcriber
from app.core.models import TranscriptSegment


@pytest.fixture
def config(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "whisper": {
            "model": "tiny",  # 用 tiny 加速測試
            "language": "zh",
            "device": "cpu",
        },
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


@pytest.fixture
def transcriber(config):
    return Transcriber(config)


def _make_sine_audio(duration_sec: float, sample_rate: int = 16000, freq: float = 440.0) -> np.ndarray:
    """產生正弦波測試音訊"""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), dtype=np.float32)
    return 0.5 * np.sin(2 * np.pi * freq * t)


def _make_speech_like_audio(duration_sec: float, sample_rate: int = 16000) -> np.ndarray:
    """產生類語音音訊（多頻率混合 + 振幅包絡）"""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), dtype=np.float32)
    signal = np.zeros_like(t)
    for freq in [200, 400, 800, 1200, 2000]:
        signal += 0.1 * np.sin(2 * np.pi * freq * t)
    # 振幅包絡模擬語音節奏
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * t)
    return (signal * envelope).astype(np.float32)


class TestTranscriber:
    def test_init(self, transcriber):
        assert transcriber is not None

    def test_transcribe_returns_segments(self, transcriber):
        """轉錄應回傳 TranscriptSegment list"""
        audio = _make_speech_like_audio(3.0)
        segments = transcriber.transcribe_chunk(audio, chunk_id=0)
        assert isinstance(segments, list)
        for seg in segments:
            assert isinstance(seg, TranscriptSegment)

    def test_segment_fields(self, transcriber):
        """每個 segment 欄位型別正確"""
        audio = _make_speech_like_audio(3.0)
        segments = transcriber.transcribe_chunk(audio, chunk_id=0)
        for seg in segments:
            assert isinstance(seg.index, int)
            assert isinstance(seg.start, float)
            assert isinstance(seg.end, float)
            assert isinstance(seg.text, str)
            assert isinstance(seg.confidence, float)
            assert seg.chunk_id == 0

    def test_index_increments(self, transcriber):
        """多次呼叫，index 全局遞增"""
        audio1 = _make_speech_like_audio(3.0)
        audio2 = _make_speech_like_audio(3.0)
        segs1 = transcriber.transcribe_chunk(audio1, chunk_id=0)
        segs2 = transcriber.transcribe_chunk(audio2, chunk_id=1)

        if segs1 and segs2:
            last_idx_1 = segs1[-1].index
            first_idx_2 = segs2[0].index
            assert first_idx_2 > last_idx_1

    def test_chunk_id_assigned(self, transcriber):
        """chunk_id 正確分配"""
        audio = _make_speech_like_audio(3.0)
        segs = transcriber.transcribe_chunk(audio, chunk_id=42)
        for seg in segs:
            assert seg.chunk_id == 42

    def test_reset(self, transcriber):
        """reset 後 index 歸零"""
        audio = _make_speech_like_audio(3.0)
        transcriber.transcribe_chunk(audio, chunk_id=0)
        transcriber.reset()
        segs = transcriber.transcribe_chunk(audio, chunk_id=0)
        if segs:
            assert segs[0].index == 0

    def test_silent_audio(self, transcriber):
        """靜音音訊不應崩潰"""
        silent = np.zeros(16000 * 3, dtype=np.float32)
        segs = transcriber.transcribe_chunk(silent, chunk_id=0)
        assert isinstance(segs, list)  # 可能空，但不崩潰
