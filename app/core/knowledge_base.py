"""App 自有知識庫 — 詞條管理 + ChromaDB 向量索引"""

from __future__ import annotations

from pathlib import Path
from glob import glob

import yaml
import chromadb
from sentence_transformers import SentenceTransformer

from app.data.config_manager import ConfigManager


class KnowledgeBase:
    def __init__(self, config: ConfigManager, embedder: SentenceTransformer | None = None):
        self.terms_dir = Path(config.get("knowledge_base.terms_dir"))
        chroma_dir = config.get("knowledge_base.chroma_dir")
        self.chroma = chromadb.PersistentClient(path=chroma_dir)
        self.collection = self.chroma.get_or_create_collection(
            name="terms",
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = embedder or SentenceTransformer(config.get("embedding.model"))
        self._terms: dict[str, dict] = {}
        self._load_all_terms()

    def _load_all_terms(self):
        """掃描 terms_dir 下所有 .yaml，載入並同步向量索引"""
        for yaml_path in sorted(self.terms_dir.glob("*.yaml")):
            with open(yaml_path, "r", encoding="utf-8") as f:
                term = yaml.safe_load(f)
            if term and "id" in term:
                self._terms[term["id"]] = term
                self._upsert_vector(term)

    def _upsert_vector(self, term: dict):
        """將詞條嵌入向量索引"""
        aliases = term.get("aliases", [])
        context = term.get("context", "")
        embed_text = f"{term['term']} {' '.join(aliases)} {context}"
        embedding = self.embedder.encode(embed_text).tolist()
        self.collection.upsert(
            ids=[term["id"]],
            embeddings=[embedding],
            documents=[embed_text],
            metadatas=[{
                "term": term["term"],
                "category": term.get("category", ""),
            }],
        )

    def query(self, text: str, top_k: int = 5) -> list[dict]:
        """向量查詢，回傳最相似的詞條"""
        if self.collection.count() == 0:
            return []
        n = min(top_k, self.collection.count())
        embedding = self.embedder.encode(text).tolist()
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n,
        )
        out = []
        for tid in results["ids"][0]:
            if tid in self._terms:
                out.append(self._terms[tid])
        return out

    def add_term(self, term_dict: dict):
        """新增詞條（寫 YAML + 更新記憶體 + 向量索引）"""
        tid = term_dict["id"]
        # 確保 stats 存在
        if "stats" not in term_dict:
            term_dict["stats"] = {
                "hit_count": 0, "correction_count": 0,
                "success_count": 0, "fail_count": 0,
            }
        self._terms[tid] = term_dict
        self._save_yaml(term_dict)
        self._upsert_vector(term_dict)

    def update_term(self, term_id: str, updates: dict):
        """更新詞條欄位"""
        if term_id not in self._terms:
            return
        self._terms[term_id].update(updates)
        self._save_yaml(self._terms[term_id])
        self._upsert_vector(self._terms[term_id])

    def delete_term(self, term_id: str):
        """刪除詞條"""
        if term_id not in self._terms:
            return
        del self._terms[term_id]
        yaml_path = self.terms_dir / f"{term_id}.yaml"
        if yaml_path.exists():
            yaml_path.unlink()
        try:
            self.collection.delete(ids=[term_id])
        except Exception:
            pass

    def get_term(self, term_id: str) -> dict | None:
        return self._terms.get(term_id)

    def list_terms(self, category: str | None = None) -> list[dict]:
        terms = list(self._terms.values())
        if category:
            terms = [t for t in terms if t.get("category") == category]
        return terms

    def update_stats(self, term_id: str, field: str, increment: int = 1):
        """更新詞條效能統計"""
        if term_id not in self._terms:
            return
        term = self._terms[term_id]
        if "stats" not in term:
            term["stats"] = {
                "hit_count": 0, "correction_count": 0,
                "success_count": 0, "fail_count": 0,
            }
        term["stats"][field] = term["stats"].get(field, 0) + increment
        self._save_yaml(term)

    def import_yaml_batch(self, yaml_content: str) -> int:
        """批次匯入 YAML（list of terms）"""
        terms = yaml.safe_load(yaml_content)
        if not isinstance(terms, list):
            return 0
        count = 0
        for term in terms:
            if "id" in term:
                self.add_term(term)
                count += 1
        return count

    def _save_yaml(self, term: dict):
        """將詞條寫入 YAML 檔案"""
        self.terms_dir.mkdir(parents=True, exist_ok=True)
        path = self.terms_dir / f"{term['id']}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(term, f, allow_unicode=True, default_flow_style=False)
