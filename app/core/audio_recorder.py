"""麥克風錄音 — 雙層串流輸出 + Mic Live 指示器 level API"""

from __future__ import annotations

import asyncio
import math
from collections import deque
from pathlib import Path
from typing import AsyncIterator

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

from app.data.config_manager import ConfigManager


class AudioRecorder:
    def __init__(self, config: ConfigManager):
        self.sample_rate = config.get("audio.sample_rate", 16000)
        self.channels = config.get("audio.channels", 1)
        self.temp_dir = Path(config.get("audio.temp_dir", "data/temp"))
        self.transcribe_chunk_sec = config.get("streaming.transcribe_chunk_sec", 10)
        self.save_chunk_sec = config.get("streaming.audio_chunk_duration_sec", 600)
        self._recording = False
        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._temp_paths: list[str] = []
        # Mic Live 指示器：rolling buffer 最近 200ms RMS
        poll_ms = config.get("ui.mic_indicator.poll_interval_ms", 200)
        self._level_buffer_samples = int(self.sample_rate * poll_ms / 1000)
        self._level_ring: deque[float] = deque(maxlen=self._level_buffer_samples)
        self._current_dbfs: float = -80.0
        # Mic Test 純量測模式
        self._probe_running = False
        self._probe_stream: sd.InputStream | None = None

    def _audio_callback(self, indata, frames, time_info, status):
        """sounddevice 回呼，把音訊資料放入 queue + 更新 level ring"""
        data = indata.copy()
        self._audio_queue.put_nowait(data)
        self._update_level(data)

    def _probe_callback(self, indata, frames, time_info, status):
        """Mic Test 純量測回呼，只更新 level 不送 queue"""
        self._update_level(indata)

    def _update_level(self, indata: np.ndarray):
        """更新 rolling RMS → dBFS"""
        flat = indata.flatten()
        self._level_ring.extend(flat.tolist())
        if len(self._level_ring) > 0:
            arr = np.array(self._level_ring, dtype=np.float64)
            rms = np.sqrt(np.mean(arr ** 2))
            if rms > 0:
                self._current_dbfs = max(20 * math.log10(rms), -80.0)
            else:
                self._current_dbfs = -80.0

    def get_current_level(self) -> float:
        """回傳當前 RMS 的 dBFS（-80 ~ 0）。給 Mic Live 指示器 UI poll 用。"""
        return self._current_dbfs

    def start_level_probe(self):
        """啟動 Mic Test 純量測模式 — 不建 session、不寫 WAV、不送 queue。"""
        if self._probe_running:
            return
        self._probe_running = True
        self._level_ring.clear()
        self._current_dbfs = -80.0
        self._probe_stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=self._probe_callback,
        )
        self._probe_stream.start()

    def stop_level_probe(self):
        """停止 Mic Test 純量測模式。"""
        self._probe_running = False
        if self._probe_stream is not None:
            self._probe_stream.stop()
            self._probe_stream.close()
            self._probe_stream = None
        self._level_ring.clear()
        self._current_dbfs = -80.0

    async def start(self) -> AsyncIterator[np.ndarray]:
        """
        啟動麥克風錄音。
        - 每 transcribe_chunk_sec 秒 yield 一個小區塊給 Transcriber
        - 每 save_chunk_sec 秒背景存一個大區塊 WAV
        """
        self._recording = True
        self._temp_paths = []
        self._level_ring.clear()
        self._current_dbfs = -80.0

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=self._audio_callback,
        )
        stream.start()

        transcribe_buffer: list[np.ndarray] = []
        save_buffer: list[np.ndarray] = []
        save_chunk_id = 0

        try:
            while self._recording:
                try:
                    data = await asyncio.wait_for(self._audio_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                # 攤平為 1D
                flat = data.flatten()
                transcribe_buffer.append(flat)
                save_buffer.append(flat)

                # 層 1：小區塊 yield
                if self._buffer_duration(transcribe_buffer) >= self.transcribe_chunk_sec:
                    yield np.concatenate(transcribe_buffer)
                    transcribe_buffer = []

                # 層 2：大區塊暫存 WAV
                if self._buffer_duration(save_buffer) >= self.save_chunk_sec:
                    self._save_temp(np.concatenate(save_buffer), save_chunk_id)
                    save_buffer = []
                    save_chunk_id += 1

            # I7：flush 殘餘於 while 退出後、finally 前（正常停止路徑）
            # GeneratorExit / exception 路徑會跳過本區塊直接進 finally，不產生新 yield
            if transcribe_buffer:
                yield np.concatenate(transcribe_buffer)
        finally:
            stream.stop()
            stream.close()
            # WAV flush 不產生 yield — 放 finally 安全
            if save_buffer:
                self._save_temp(np.concatenate(save_buffer), save_chunk_id)

    async def request_stop(self):
        """軟停止錄音（G5）— 設旗標，start() 的 while 迴圈於下一輪自然退出。

        消費者應 drain generator 而非靠 task.cancel（見 I3 invariant）。
        """
        self._recording = False

    def _buffer_duration(self, buffer: list[np.ndarray]) -> float:
        total_samples = sum(b.shape[0] for b in buffer)
        return total_samples / self.sample_rate

    def _save_temp(self, audio: np.ndarray, chunk_id: int):
        """暫存 WAV"""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        path = self.temp_dir / f"chunk_{chunk_id:04d}.wav"
        # 轉為 int16 存檔
        audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        wavfile.write(str(path), self.sample_rate, audio_int16)
        self._temp_paths.append(str(path))

    def get_temp_paths(self) -> list[str]:
        return list(self._temp_paths)
