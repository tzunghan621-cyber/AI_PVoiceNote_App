"""測試 Summarizer — mock Ollama, 結構驗證, 增量摘要, JSON fallback"""

import json

import pytest
import yaml
from unittest.mock import AsyncMock, patch, MagicMock

from app.data.config_manager import ConfigManager
from app.core.summarizer import Summarizer
from app.core.models import (
    CorrectedSegment, SummaryResult, ActionItem, Participant,
)


@pytest.fixture
def config(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "ollama": {
            "model": "gemma4:4b",
            "base_url": "http://localhost:11434",
        },
    }), encoding="utf-8")
    return ConfigManager(str(config_path))


def _mock_ollama_response():
    """標準的 Ollama JSON 回應"""
    return json.dumps({
        "highlights": "決定採用 Gemma 4 進行本地推理",
        "action_items": [
            {
                "content": "確認 API 文件",
                "owner": "John",
                "deadline": "2026-04-07",
                "priority": "high",
                "status": "open",
            }
        ],
        "decisions": ["採用 Gemma 4 4B 量化版"],
        "keywords": ["Gemma 4", "API", "部署"],
    }, ensure_ascii=False)


def _make_segments(n: int, start_index: int = 0) -> list[CorrectedSegment]:
    return [
        CorrectedSegment(
            index=start_index + i,
            start=float(i * 10), end=float(i * 10 + 10),
            original_text=f"段落 {start_index + i} 的內容",
            corrected_text=f"段落 {start_index + i} 的內容",
            corrections=[],
        )
        for i in range(n)
    ]


class TestGenerate:
    @pytest.mark.asyncio
    async def test_initial_summary(self, config):
        """首次摘要回傳完整 SummaryResult"""
        summarizer = Summarizer(config)
        segments = _make_segments(5)

        with patch.object(summarizer, '_call_ollama', new_callable=AsyncMock,
                          return_value=_mock_ollama_response()):
            result = await summarizer.generate(segments)

        assert isinstance(result, SummaryResult)
        assert result.version == 1
        assert result.highlights != ""
        assert len(result.action_items) >= 1
        assert result.covered_until == 4
        assert result.is_final is False
        assert result.model == "gemma4:4b"
        assert result.generation_time >= 0

    @pytest.mark.asyncio
    async def test_summary_fields_complete(self, config):
        """ActionItem 欄位完整"""
        summarizer = Summarizer(config)
        segments = _make_segments(5)

        with patch.object(summarizer, '_call_ollama', new_callable=AsyncMock,
                          return_value=_mock_ollama_response()):
            result = await summarizer.generate(segments)

        item = result.action_items[0]
        assert isinstance(item, ActionItem)
        assert item.content == "確認 API 文件"
        assert item.owner == "John"
        assert item.priority == "high"
        assert item.status == "open"
        assert item.user_edited is False

    @pytest.mark.asyncio
    async def test_final_summary(self, config):
        """最終摘要 is_final=True"""
        summarizer = Summarizer(config)
        segments = _make_segments(5)

        with patch.object(summarizer, '_call_ollama', new_callable=AsyncMock,
                          return_value=_mock_ollama_response()):
            result = await summarizer.generate(segments, is_final=True)

        assert result.is_final is True


class TestIncremental:
    @pytest.mark.asyncio
    async def test_incremental_uses_index_filter(self, config):
        """[m-1] 增量摘要應用 index 過濾，非 list 切片"""
        summarizer = Summarizer(config)
        segments = _make_segments(10)
        prev = SummaryResult(
            version=1, highlights="前次重點",
            action_items=[], decisions=[], keywords=[],
            covered_until=4,  # 前次涵蓋到 index 4
            model="gemma4:4b", generation_time=1.0, is_final=False,
        )

        call_args = {}

        async def capture_prompt(prompt):
            call_args['prompt'] = prompt
            return _mock_ollama_response()

        with patch.object(summarizer, '_call_ollama', side_effect=capture_prompt):
            result = await summarizer.generate(segments, previous_summary=prev)

        # prompt 中應只包含 index > 4 的段落
        prompt = call_args['prompt']
        assert "段落 5" in prompt
        assert "段落 9" in prompt
        # 不應包含 index <= 4 的段落
        assert "段落 0 " not in prompt
        assert "段落 4 " not in prompt

    @pytest.mark.asyncio
    async def test_version_increments(self, config):
        """版本號遞增"""
        summarizer = Summarizer(config)
        segments = _make_segments(5)

        with patch.object(summarizer, '_call_ollama', new_callable=AsyncMock,
                          return_value=_mock_ollama_response()):
            r1 = await summarizer.generate(segments)
            r2 = await summarizer.generate(segments)

        assert r1.version == 1
        assert r2.version == 2

    @pytest.mark.asyncio
    async def test_with_participants(self, config):
        """帶與會人員的摘要"""
        summarizer = Summarizer(config)
        segments = _make_segments(5)
        participants = [Participant(name="John", role="PM")]

        call_args = {}

        async def capture_prompt(prompt):
            call_args['prompt'] = prompt
            return _mock_ollama_response()

        with patch.object(summarizer, '_call_ollama', side_effect=capture_prompt):
            await summarizer.generate(segments, participants=participants)

        assert "John" in call_args['prompt']


class TestFallback:
    @pytest.mark.asyncio
    async def test_json_parse_failure_fallback(self, config):
        """[T-1] Gemma 回傳非 JSON 時，fallback 保留前次摘要不崩潰"""
        summarizer = Summarizer(config)
        segments = _make_segments(5)
        prev = SummaryResult(
            version=1, highlights="前次重點",
            action_items=[], decisions=["前次決議"], keywords=["前次"],
            covered_until=2,
            model="gemma4:4b", generation_time=1.0, is_final=False,
        )

        with patch.object(summarizer, '_call_ollama', new_callable=AsyncMock,
                          return_value="這不是 JSON，只是一段文字"):
            result = await summarizer.generate(segments, previous_summary=prev)

        # 應 fallback：保留前次摘要的內容 + version 遞增
        assert isinstance(result, SummaryResult)
        assert result.version == 1  # 第一次呼叫 generate，version 從 0 → 1
        assert result.highlights == "前次重點"
        assert result.decisions == ["前次決議"]

    @pytest.mark.asyncio
    async def test_json_parse_failure_no_previous(self, config):
        """無前次摘要時 JSON 解析失敗，回傳空摘要"""
        summarizer = Summarizer(config)
        segments = _make_segments(5)

        with patch.object(summarizer, '_call_ollama', new_callable=AsyncMock,
                          return_value="not json"):
            result = await summarizer.generate(segments)

        assert isinstance(result, SummaryResult)
        assert result.highlights == ""


class TestReset:
    def test_reset_version(self, config):
        summarizer = Summarizer(config)
        summarizer._version = 5
        summarizer.reset()
        assert summarizer._version == 0
