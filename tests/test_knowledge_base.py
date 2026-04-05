"""測試 KnowledgeBase — CRUD、向量查詢、批次匯入、stats 更新

需要載入 sentence-transformers 模型，記憶體需求較大。
獨立執行：python -m pytest tests/test_knowledge_base.py -v -m slow
"""

import os
import shutil

import pytest
import yaml
from sentence_transformers import SentenceTransformer

from app.data.config_manager import ConfigManager
from app.core.knowledge_base import KnowledgeBase

pytestmark = pytest.mark.slow

# Session-scoped embedder — 只載入一次，避免記憶體耗盡
@pytest.fixture(scope="session")
def shared_embedder():
    return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


@pytest.fixture
def kb_env(tmp_path):
    """建立臨時知識庫環境"""
    terms_dir = tmp_path / "terms"
    chroma_dir = tmp_path / "chroma"
    terms_dir.mkdir()
    chroma_dir.mkdir()

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump({
        "knowledge_base": {
            "terms_dir": str(terms_dir),
            "chroma_dir": str(chroma_dir),
        },
        "embedding": {
            "model": "paraphrase-multilingual-MiniLM-L12-v2",
        },
    }), encoding="utf-8")

    config = ConfigManager(str(config_path))
    return config, terms_dir, chroma_dir


@pytest.fixture
def kb(kb_env, shared_embedder):
    config, terms_dir, chroma_dir = kb_env
    kb_instance = KnowledgeBase(config, embedder=shared_embedder)
    return kb_instance


@pytest.fixture
def sample_term():
    return {
        "id": "gemma4",
        "term": "Gemma 4",
        "aliases": ["寶石四", "gemma4", "GEMMA"],
        "category": "技術/AI模型",
        "context": "Google 開源本地端 LLM",
        "source": "學習筆記_Gemma.md",
        "origin": "obsidian_sync",
        "created": "2026-04-04",
        "updated": "2026-04-04",
        "stats": {
            "hit_count": 0,
            "correction_count": 0,
            "success_count": 0,
            "fail_count": 0,
        },
    }


class TestCRUD:
    def test_add_and_get(self, kb, sample_term):
        kb.add_term(sample_term)
        got = kb.get_term("gemma4")
        assert got is not None
        assert got["term"] == "Gemma 4"
        assert got["aliases"] == ["寶石四", "gemma4", "GEMMA"]

    def test_add_persists_yaml(self, kb, sample_term, kb_env):
        _, terms_dir, _ = kb_env
        kb.add_term(sample_term)
        yaml_path = terms_dir / "gemma4.yaml"
        assert yaml_path.exists()
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["term"] == "Gemma 4"

    def test_update_term(self, kb, sample_term):
        kb.add_term(sample_term)
        kb.update_term("gemma4", {"context": "Updated context"})
        got = kb.get_term("gemma4")
        assert got["context"] == "Updated context"

    def test_delete_term(self, kb, sample_term, kb_env):
        _, terms_dir, _ = kb_env
        kb.add_term(sample_term)
        kb.delete_term("gemma4")
        assert kb.get_term("gemma4") is None
        assert not (terms_dir / "gemma4.yaml").exists()

    def test_list_terms(self, kb, sample_term):
        kb.add_term(sample_term)
        kb.add_term({
            "id": "chromadb", "term": "ChromaDB",
            "aliases": ["chroma"], "origin": "manual",
            "created": "2026-04-04", "updated": "2026-04-04",
            "stats": {"hit_count": 0, "correction_count": 0, "success_count": 0, "fail_count": 0},
        })
        terms = kb.list_terms()
        assert len(terms) == 2

    def test_list_terms_by_category(self, kb, sample_term):
        kb.add_term(sample_term)
        kb.add_term({
            "id": "chromadb", "term": "ChromaDB",
            "aliases": ["chroma"], "category": "技術/資料庫",
            "origin": "manual",
            "created": "2026-04-04", "updated": "2026-04-04",
            "stats": {"hit_count": 0, "correction_count": 0, "success_count": 0, "fail_count": 0},
        })
        terms = kb.list_terms(category="技術/AI模型")
        assert len(terms) == 1
        assert terms[0]["id"] == "gemma4"

    def test_get_nonexistent(self, kb):
        assert kb.get_term("nonexistent") is None


class TestVectorQuery:
    def test_query_top1_hit(self, kb, sample_term):
        kb.add_term(sample_term)
        kb.add_term({
            "id": "chromadb", "term": "ChromaDB",
            "aliases": ["chroma", "克羅馬"], "context": "向量資料庫",
            "origin": "manual",
            "created": "2026-04-04", "updated": "2026-04-04",
            "stats": {"hit_count": 0, "correction_count": 0, "success_count": 0, "fail_count": 0},
        })
        results = kb.query("寶石四 模型", top_k=1)
        assert len(results) >= 1
        assert results[0]["id"] == "gemma4"

    def test_query_returns_multiple(self, kb, sample_term):
        kb.add_term(sample_term)
        kb.add_term({
            "id": "chromadb", "term": "ChromaDB",
            "aliases": ["chroma"], "context": "向量資料庫",
            "origin": "manual",
            "created": "2026-04-04", "updated": "2026-04-04",
            "stats": {"hit_count": 0, "correction_count": 0, "success_count": 0, "fail_count": 0},
        })
        results = kb.query("資料庫 向量", top_k=5)
        assert len(results) >= 1

    def test_query_empty_kb(self, kb):
        results = kb.query("anything", top_k=5)
        assert results == []


class TestBatchImport:
    def test_import_yaml_batch(self, kb):
        yaml_content = yaml.dump([
            {
                "id": "ollama", "term": "Ollama",
                "aliases": ["歐拉瑪"], "origin": "manual",
                "created": "2026-04-04", "updated": "2026-04-04",
                "stats": {"hit_count": 0, "correction_count": 0, "success_count": 0, "fail_count": 0},
            },
            {
                "id": "flet", "term": "Flet",
                "aliases": ["飛特"], "origin": "manual",
                "created": "2026-04-04", "updated": "2026-04-04",
                "stats": {"hit_count": 0, "correction_count": 0, "success_count": 0, "fail_count": 0},
            },
        ], allow_unicode=True)
        count = kb.import_yaml_batch(yaml_content)
        assert count == 2
        assert kb.get_term("ollama") is not None
        assert kb.get_term("flet") is not None


class TestStats:
    def test_update_stats(self, kb, sample_term):
        kb.add_term(sample_term)
        kb.update_stats("gemma4", "hit_count")
        kb.update_stats("gemma4", "hit_count")
        kb.update_stats("gemma4", "correction_count")
        got = kb.get_term("gemma4")
        assert got["stats"]["hit_count"] == 2
        assert got["stats"]["correction_count"] == 1

    def test_update_stats_persists(self, kb, sample_term, kb_env):
        _, terms_dir, _ = kb_env
        kb.add_term(sample_term)
        kb.update_stats("gemma4", "success_count", 3)
        with open(terms_dir / "gemma4.yaml", "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["stats"]["success_count"] == 3


class TestLoadExisting:
    def test_load_terms_on_init(self, kb_env, shared_embedder):
        config, terms_dir, _ = kb_env
        # 預先放一個 YAML 詞條
        term = {
            "id": "preexist", "term": "PreExist",
            "aliases": ["pre"], "origin": "manual",
            "created": "2026-04-04", "updated": "2026-04-04",
            "stats": {"hit_count": 5, "correction_count": 3, "success_count": 2, "fail_count": 1},
        }
        with open(terms_dir / "preexist.yaml", "w", encoding="utf-8") as f:
            yaml.dump(term, f, allow_unicode=True)

        # 初始化 KB 應自動載入
        kb = KnowledgeBase(config, embedder=shared_embedder)
        got = kb.get_term("preexist")
        assert got is not None
        assert got["term"] == "PreExist"
        assert got["stats"]["hit_count"] == 5
