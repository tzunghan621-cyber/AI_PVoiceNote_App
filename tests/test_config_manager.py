"""測試 ConfigManager — get/set/save 迴圈"""

import os
import tempfile
import shutil

import pytest
import yaml

from app.data.config_manager import ConfigManager


@pytest.fixture
def config_dir(tmp_path):
    """建立臨時 config 目錄，複製 default.yaml"""
    src = os.path.join(os.path.dirname(__file__), "..", "config", "default.yaml")
    dst = tmp_path / "default.yaml"
    shutil.copy(src, dst)
    return tmp_path


@pytest.fixture
def config(config_dir):
    return ConfigManager(str(config_dir / "default.yaml"))


class TestGet:
    def test_top_level(self, config):
        assert isinstance(config.get("whisper"), dict)

    def test_dotted_key(self, config):
        assert config.get("whisper.model") == "small"
        assert config.get("whisper.language") == "zh"
        assert config.get("whisper.device") == "cpu"

    def test_deep_key(self, config):
        assert config.get("streaming.transcribe_chunk_sec") == 10
        assert config.get("streaming.audio_chunk_duration_sec") == 600
        assert config.get("streaming.summary_interval_sec") == 180

    def test_default_for_missing(self, config):
        assert config.get("nonexistent.key") is None
        assert config.get("nonexistent.key", "fallback") == "fallback"

    def test_all_spec_keys_exist(self, config):
        """驗證 data_schema#8 定義的所有 key 都存在"""
        expected_keys = [
            "whisper.model", "whisper.language", "whisper.device",
            "ollama.model", "ollama.base_url",
            "embedding.model",
            "knowledge_base.terms_dir", "knowledge_base.chroma_dir",
            "streaming.transcribe_chunk_sec", "streaming.audio_chunk_duration_sec",
            "streaming.summary_interval_sec", "streaming.summary_min_new_segments",
            "audio.sample_rate", "audio.channels", "audio.temp_dir",
            "export.default_dir", "export.include_raw_transcript", "export.include_corrections",
            "feedback.dir",
            "sessions.dir",
        ]
        for key in expected_keys:
            val = config.get(key)
            assert val is not None, f"Config key '{key}' should exist but got None"


class TestSet:
    def test_set_existing(self, config):
        config.set("whisper.model", "tiny")
        assert config.get("whisper.model") == "tiny"

    def test_set_nested(self, config):
        config.set("streaming.summary_interval_sec", 300)
        assert config.get("streaming.summary_interval_sec") == 300


class TestSave:
    def test_save_and_reload(self, config_dir):
        config_path = str(config_dir / "default.yaml")
        config = ConfigManager(config_path)

        config.set("whisper.model", "medium")
        config.save()

        # reload
        config2 = ConfigManager(config_path)
        assert config2.get("whisper.model") == "medium"

    def test_save_preserves_other_keys(self, config_dir):
        config_path = str(config_dir / "default.yaml")
        config = ConfigManager(config_path)

        original_lang = config.get("whisper.language")
        config.set("whisper.model", "medium")
        config.save()

        config2 = ConfigManager(config_path)
        assert config2.get("whisper.language") == original_lang
