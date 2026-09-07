
"""双模式 embedding。

- semantic: sentence-transformers + 中文模型 (bge)，效果好，需下载 ~1GB
- tfidf:   零下载兜底，中文用 char n-gram

生产用 semantic。首次加载模型需联网（走 HF 镜像），之后本地缓存秒级启动。
"""
import os
import numpy as np

if not os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"  # 清华镜像：HF 官方被墙，必须用镜像
if not os.getenv("HF_HUB_DISABLE_SYMLINKS_WARNING"):
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
if not os.getenv("HF_HUB_ENABLE_HF_TRANSFER"):
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"  # 多进程高速下载（自动启用）


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5", mode: str = "semantic"):
        self.mode = mode
        if mode == "tfidf":
            from sklearn.feature_extraction.text import TfidfVectorizer
            import os
            self.dim = 1024  # 与 bge-large-zh 维度一致
            self._tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 2),
                                          max_features=self.dim)
            # 懒 fit：首次 embed_batch 时用真实入库数据建词表，
            # 并持久化到磁盘，避免重启后重新 fit 把查询词当语料。
            # 旧版硬编码 fit 语料（人工智能/光伏）与商城数据字面完全不重叠，
            # 导致所有查询返回全 0 向量、检索结果雷同。
            self._tfidf_vocab_path = os.path.join(
                os.environ.get("VECTOR_DB_DIR", "vector_db"), "tfidf_vectorizer.pkl")
            self._tfidf_fitted = self._load_tfidf()
            return
        from sentence_transformers import SentenceTransformer
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.dim = self.model.get_embedding_dimension()

    def embed(self, text: str) -> np.ndarray:
        if self.mode == "tfidf":
            return self._tfidf_embed(text)
        vec = self.model.encode(text, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32).flatten()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if self.mode == "tfidf":
            if not self._tfidf_fitted and texts:
                # 首次入库：用真实数据建词表，并持久化
                self._tfidf.fit(texts)
                self._tfidf_fitted = True
                self._save_tfidf()
            return np.stack([self._tfidf_embed(t) for t in texts])
        vecs = self.model.encode(texts, normalize_embeddings=True,
                                 batch_size=batch_size, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)

    def _tfidf_embed(self, text: str) -> np.ndarray:
        if not self._tfidf_fitted:
            # 还没 fit 就来了查询：用这条查询自己兜底 fit（不持久化，
            # 等真正 ingest 时会被真实数据覆盖）
            self._tfidf.fit([text])
            self._tfidf_fitted = True
        vec = self._tfidf.transform([text]).toarray().flatten()
        return np.pad(vec, (0, self.dim - len(vec))) if len(vec) < self.dim else vec[:self.dim]

    def _load_tfidf(self) -> bool:
        """从磁盘加载已 fit 的 vectorizer。返回是否成功加载。"""
        import pickle
        try:
            if os.path.exists(self._tfidf_vocab_path):
                with open(self._tfidf_vocab_path, "rb") as f:
                    self._tfidf = pickle.load(f)
                self.dim = self._tfidf.max_features or self.dim
                return True
        except Exception as e:
            print(f"[WARN] 加载 tfidf vectorizer 失败: {e}，将重新 fit")
        return False

    def _save_tfidf(self):
        """持久化 vectorizer，下次启动直接 load。"""
        import pickle
        os.makedirs(os.path.dirname(self._tfidf_vocab_path), exist_ok=True)
        try:
            with open(self._tfidf_vocab_path, "wb") as f:
                pickle.dump(self._tfidf, f)
        except Exception as e:
            print(f"[WARN] 保存 tfidf vectorizer 失败: {e}")


# ---------- 单例缓存：多租户共享同一个模型 ----------
# bge 模型约 1GB+，若每个租户各加载一份，显存/内存会线性爆炸。
# 所有租户用同一 (model, mode)，共享同一 Embedder 实例。
_EMBEDDER_CACHE: dict[tuple[str, str], Embedder] = {}


def get_embedder(model_name: str = "BAAI/bge-large-zh-v1.5", mode: str = "semantic") -> Embedder:
    key = (model_name, mode)
    if key not in _EMBEDDER_CACHE:
        _EMBEDDER_CACHE[key] = Embedder(model_name, mode)
    return _EMBEDDER_CACHE[key]
