"""音檔匯入 — 載入外部音檔，切段送入 Pipeline"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

import numpy as np
from pydub import AudioSegment
from scipy.io import wavfile

from app.data.config_manager import ConfigManager


class AudioImporter:
    def __init__(self, config: ConfigManager):
        self.sample_rate = config.get("audio.sample_rate", 16000)
        self.transcribe_chunk_sec = config.get("streaming.transcribe_chunk_sec", 10)
        self.save_chunk_sec = config.get("streaming.audio_chunk_duration_sec", 600)
        self.temp_dir = Path(config.get("audio.temp_dir", "data/temp"))
        self._temp_paths: list[str] = []

    async def import_file(self, file_path: str) -> AsyncIterator[np.ndarray]:
        """載入音檔 → 統一為 16kHz mono → 切段 yield"""
        self._temp_paths = []
        audio = AudioSegment.from_file(file_path)
        audio = audio.set_frame_rate(self.sample_rate).set_channels(1)
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32) / 32768.0

        transcribe_samples = int(self.transcribe_chunk_sec * self.sample_rate)
        save_samples = int(self.save_chunk_sec * self.sample_rate)
        save_buffer: list[np.ndarray] = []
        save_chunk_id = 0

        for i in range(0, len(samples), transcribe_samples):
            chunk = samples[i:i + transcribe_samples]
            save_buffer.append(chunk)

            yield chunk

            # 檢查是否達到暫存閾值
            save_total = sum(len(b) for b in save_buffer)
            if save_total >= save_samples:
                self._save_temp(np.concatenate(save_buffer), save_chunk_id)
                save_buffer = []
                save_chunk_id += 1

        # flush 殘餘暫存
        if save_buffer:
            self._save_temp(np.concatenate(save_buffer), save_chunk_id)

    def get_duration(self, file_path: str) -> float:
        """回傳音檔時長（秒）"""
        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0

    def get_temp_paths(self) -> list[str]:
        return list(self._temp_paths)

    def _save_temp(self, audio: np.ndarray, chunk_id: int):
        """暫存 WAV"""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        path = self.temp_dir / f"import_chunk_{chunk_id:04d}.wav"
        audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        wavfile.write(str(path), self.sample_rate, audio_int16)
        self._temp_paths.append(str(path))
