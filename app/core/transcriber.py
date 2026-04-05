"""語音轉文字 — faster-whisper 即時轉錄"""

from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel

from app.data.config_manager import ConfigManager
from app.core.models import TranscriptSegment


class Transcriber:
    def __init__(self, config: ConfigManager):
        self.model = WhisperModel(
            config.get("whisper.model", "small"),
            device=config.get("whisper.device", "cpu"),
            compute_type="int8",
        )
        self.language = config.get("whisper.language", "zh")
        self._segment_counter = 0

    def transcribe_chunk(self, audio_data: np.ndarray, chunk_id: int) -> list[TranscriptSegment]:
        """轉錄單一音訊區塊，回傳 TranscriptSegment list"""
        segments_iter, info = self.model.transcribe(
            audio_data,
            language=self.language,
            vad_filter=True,
        )

        result = []
        for seg in segments_iter:
            # 將 avg_logprob 轉為 0-1 信心分數（logprob 通常為負數）
            confidence = max(0.0, min(1.0, 1.0 + seg.avg_logprob))
            ts = TranscriptSegment(
                index=self._segment_counter,
                start=seg.start,
                end=seg.end,
                text=seg.text.strip(),
                confidence=confidence,
                chunk_id=chunk_id,
            )
            self._segment_counter += 1
            result.append(ts)

        return result

    def reset(self):
        """重置 segment 計數器"""
        self._segment_counter = 0
