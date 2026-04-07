"""端對端整合測試 — 跑真實錄音檔走完整 Pipeline

執行方式：
    python -m pytest -m real_audio -v -s

需求：
    - tests/fixtures/audio/ 底下有 .wav / .mp3 / .m4a
    - Ollama 已啟動且模型已 pull（預設 gemma4:e2b）
    - faster-whisper 模型可載入

Pipeline：
    AudioImporter → Transcriber → RAGCorrector → Summarizer → Exporter
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import yaml

from app.data.config_manager import ConfigManager
from app.core.audio_importer import AudioImporter
from app.core.transcriber import Transcriber
from app.core.knowledge_base import KnowledgeBase
from app.core.rag_corrector import RAGCorrector
from app.core.summarizer import Summarizer
from app.core.exporter import Exporter
from app.core.models import Session, SummaryResult


pytestmark = pytest.mark.real_audio


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "audio"
SUPPORTED_EXTS = {".wav", ".mp3", ".m4a"}


def _discover_audio_files() -> list[Path]:
    if not FIXTURES_DIR.exists():
        return []
    return sorted(
        p for p in FIXTURES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS
    )


def _rss_mb() -> float:
    """回傳當前 process RSS（MB），psutil 缺席時回 0"""
    try:
        import psutil  # type: ignore
        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0


@pytest.fixture(scope="module")
def e2e_config(tmp_path_factory):
    """獨立的測試 config — Whisper tiny 加速、知識庫指向 tmp、Ollama 走預設"""
    tmp = tmp_path_factory.mktemp("e2e_real_audio")
    terms_dir = tmp / "terms"
    terms_dir.mkdir()
    chroma_dir = tmp / "chroma"
    temp_dir = tmp / "audio_temp"

    config_path = tmp / "config.yaml"
    config_path.write_text(yaml.dump({
        "whisper": {
            "model": "tiny",  # 真實檔案夠多時用 tiny 加速
            "language": "zh",
            "device": "cpu",
        },
        "ollama": {
            "model": "gemma4:e2b",
            "base_url": "http://localhost:11434",
            "options": {"num_ctx": 8192, "temperature": 0.3},
        },
        "embedding": {
            "model": "paraphrase-multilingual-MiniLM-L12-v2",
        },
        "knowledge_base": {
            "terms_dir": str(terms_dir),
            "chroma_dir": str(chroma_dir),
        },
        "streaming": {
            "transcribe_chunk_sec": 10,
            "audio_chunk_duration_sec": 600,
        },
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "temp_dir": str(temp_dir),
        },
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


AUDIO_FILES = _discover_audio_files()


@pytest.mark.skipif(
    not AUDIO_FILES,
    reason=f"無真實錄音素材；請放檔到 {FIXTURES_DIR}（見該目錄 README.md）",
)
@pytest.mark.parametrize(
    "audio_path",
    AUDIO_FILES,
    ids=[p.name for p in AUDIO_FILES],
)
@pytest.mark.asyncio
async def test_full_pipeline_real_audio(audio_path: Path, e2e_config, tmp_path):
    """對每個 fixture 音檔跑完整 Pipeline 並驗證每階段產出"""
    print(f"\n{'='*60}")
    print(f"🎙️  測試檔案：{audio_path.name}")
    print(f"{'='*60}")
    print(f"  RSS 起始：{_rss_mb():.1f} MB")

    # ── Stage 1: AudioImporter ──
    t0 = time.time()
    importer = AudioImporter(e2e_config)
    duration = importer.get_duration(str(audio_path))
    print(f"  ⏱  音檔時長：{duration:.1f}s")
    assert duration > 0, "音檔時長應 > 0"

    chunks: list[np.ndarray] = []
    async for chunk in importer.import_file(str(audio_path)):
        chunks.append(chunk)
    t_import = time.time() - t0
    assert len(chunks) > 0, "AudioImporter 應產出至少一個 chunk"
    print(f"  ✅ AudioImporter：{len(chunks)} chunks，{t_import:.2f}s，RSS {_rss_mb():.1f} MB")

    # ── Stage 2: Transcriber ──
    t0 = time.time()
    transcriber = Transcriber(e2e_config)
    transcriber.reset()
    all_segments = []
    for chunk_id, chunk in enumerate(chunks):
        segs = transcriber.transcribe_chunk(chunk, chunk_id)
        all_segments.extend(segs)
    t_transcribe = time.time() - t0
    assert len(all_segments) > 0, "Transcriber 應產出至少一個 segment（音檔可能為靜音？）"
    print(f"  ✅ Transcriber：{len(all_segments)} segments，{t_transcribe:.2f}s，RSS {_rss_mb():.1f} MB")
    print(f"     首段：{all_segments[0].text[:40]}...")

    # ── Stage 3: RAGCorrector ──
    t0 = time.time()
    kb = KnowledgeBase(e2e_config)
    corrector = RAGCorrector(kb)
    corrected = [corrector.correct(seg) for seg in all_segments]
    t_correct = time.time() - t0
    assert len(corrected) == len(all_segments), "校正後段數應與原始一致"
    hits = sum(len(c.corrections) for c in corrected)
    print(f"  ✅ RAGCorrector：{hits} 命中校正，{t_correct:.2f}s")

    # ── Stage 4: Summarizer ──
    t0 = time.time()
    summarizer = Summarizer(e2e_config)
    try:
        summary = await summarizer.generate(corrected, is_final=True)
    except Exception as ex:
        pytest.skip(f"Ollama 不可用或模型未下載：{ex}")
    t_summarize = time.time() - t0
    assert isinstance(summary, SummaryResult)
    assert summary.highlights is not None  # 即使 fallback 也應有欄位
    print(f"  ✅ Summarizer：{t_summarize:.2f}s，RSS {_rss_mb():.1f} MB")
    print(f"     highlights：{summary.highlights[:60]}...")
    print(f"     action_items：{len(summary.action_items)} 筆")
    print(f"     decisions：{len(summary.decisions)} 筆")

    # ── Stage 5: Exporter ──
    t0 = time.time()
    session = Session(
        title=f"e2e_{audio_path.stem}",
        created=datetime.now().isoformat(),
        audio_paths=[str(audio_path)],
        audio_source="import",
        audio_duration=duration,
        segments=corrected,
        summary=summary,
        summary_history=[summary],
    )
    output_path = tmp_path / f"{audio_path.stem}.md"
    exporter = Exporter()
    exporter.export(session, str(output_path))
    t_export = time.time() - t0
    assert output_path.exists(), "Exporter 應產出 Markdown 檔"
    md_content = output_path.read_text(encoding="utf-8")
    assert "# 會議摘要" in md_content
    assert "## 逐字稿" in md_content
    print(f"  ✅ Exporter：{output_path.name}（{len(md_content)} 字元），{t_export:.2f}s")

    # ── 總結 ──
    total = t_import + t_transcribe + t_correct + t_summarize + t_export
    rtf = total / duration if duration > 0 else 0
    print(f"\n  📊 總耗時 {total:.2f}s（音檔 {duration:.1f}s，RTF={rtf:.2f}x）")
    print(f"     RSS 結束：{_rss_mb():.1f} MB")
