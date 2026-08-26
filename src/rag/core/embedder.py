
"""双模式 embedding。

- semantic: sentence-transformers + 中文模型 (bge)，效果好，需下载 ~1GB
- tfidf:   零下载兜底，中文用 char n-gram

生产用 semantic。首次加载模型需联网（走 HF 镜像），之后本地缓存秒级启动。
"""
import os
import numpy as np

if not os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
if not os.getenv("HF_HUB_DISABLE_SYMLINKS_WARNING"):
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


class Embedder:
    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5", mode: str = "semantic"):
        self.mode = mode
        self.dim = 4096
        if mode == "tfidf":
            self._tfidf = None
            return
        from sentence_transformers import SentenceTransformer
        _torch = __import__("torch")
        device = "cuda" if _torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> np.ndarray:
        if self.mode == "tfidf":
            return self._tfidf_embed(text)
        vec = self.model.encode(text, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32).flatten()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        if self.mode == "tfidf":
            return np.stack([self.embed(t) for t in texts])
        vecs = self.model.encode(texts, normalize_embeddings=True,
                                 batch_size=batch_size, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)

    def _tfidf_embed(self, text: str) -> np.ndarray:
        from sklearn.feature_extraction.text import TfidfVectorizer
        if self._tfidf is None:
            self._tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 2),
                                          max_features=self.dim)
            self._tfidf.fit(["人工智能 深度学习 机器学习",
                             "产品手册 售后服务 安装调试", text])
        vec = self._tfidf.transform([text]).toarray().flatten()
        return np.pad(vec, (0, self.dim - len(vec))) if len(vec) < self.dim else vec[:self.dim]
