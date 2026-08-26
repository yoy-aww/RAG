
"""FAISS 向量库 + 元数据持久化。

IndexFlatIP（内积）—— 因为向量已 L2 归一化，内积 = 余弦相似度。
多租户隔离：每个 chunk 带 doc_id，检索时按 doc_id 过滤，
不同客户的数据在同一 index 中但永不串扰。
"""
import os
import pickle
import numpy as np
import faiss

from .chunker import Chunk
from .embedder import Embedder


class VectorStore:
    def __init__(self, embedder: Embedder, db_dir: str, doc_id: str):
        self.embedder = embedder
        self.db_dir = db_dir
        self.doc_id = doc_id        # 本实例服务单一客户/文档域
        self.dim = embedder.dim
        os.makedirs(db_dir, exist_ok=True)
        self.index = faiss.IndexFlatIP(self.dim)  # 内积（归一化向量）
        self.chunks: list[Chunk] = []
        self._load()

    # ---- 构建 / 追加 ----
    def build(self, chunks: list[Chunk]):
        if not chunks:
            return
        self.index.reset()
        self.chunks = list(chunks)
        self._add(chunks)

    def add_chunks(self, chunks: list[Chunk]):
        if not chunks:
            return
        self.chunks.extend(chunks)
        self._add(chunks)

    def _add(self, chunks: list[Chunk]):
        vecs = self.embedder.embed_batch([c.content for c in chunks])
        vecs = np.ascontiguousarray(vecs, dtype=np.float32)
        assert vecs.shape[1] == self.dim, f"维度不匹配: {vecs.shape[1]} vs {self.dim}"
        self.index.add(vecs)

    # ---- 检索 ----
    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        qvec = np.asarray([self.embedder.embed(query)], dtype=np.float32)
        k = min(top_k, self.index.ntotal)
        if k <= 0:
            return []
        scores, idx = self.index.search(qvec, k)
        results = []
        for s, i in zip(scores[0], idx[0]):
            if i < 0:
                continue
            c = self.chunks[int(i)]
            results.append((c, float(s)))
        return results

    # ---- 持久化 ----
    def save(self):
        faiss.write_index(self.index, os.path.join(self.db_dir, f"index_{self.doc_id}.faiss"))
        with open(os.path.join(self.db_dir, f"meta_{self.doc_id}.pkl"), "wb") as f:
            pickle.dump(self.chunks, f)

    def _load(self):
        idx_path = os.path.join(self.db_dir, f"index_{self.doc_id}.faiss")
        meta_path = os.path.join(self.db_dir, f"meta_{self.doc_id}.pkl")
        if os.path.exists(idx_path) and os.path.exists(meta_path):
            self.index = faiss.read_index(idx_path)
            with open(meta_path, "rb") as f:
                self.chunks = pickle.load(f)

    def clear(self):
        self.index.reset()
        self.chunks.clear()
        self.save()

    @property
    def count(self) -> int:
        return self.index.ntotal
