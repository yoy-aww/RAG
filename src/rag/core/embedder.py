
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
            self.dim = 1024  # 与 bge-large-zh 维度一致
            self._tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 2),
                                          max_features=self.dim)
            # 初始化时固定词汇表，后续只 transform 不 fit，保证向量空间一致
            self._tfidf.fit([
                "人工智能 深度学习 机器学习 自然语言处理",
                "产品手册 售后服务 安装调试 操作说明",
                "光伏组件 额定功率 系统配置 技术参数",
            ])
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
            return np.stack([self.embed(t) for t in texts])
        vecs = self.model.encode(texts, normalize_embeddings=True,
                                 batch_size=batch_size, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)

    def _tfidf_embed(self, text: str) -> np.ndarray:
        vec = self._tfidf.transform([text]).toarray().flatten()
        return np.pad(vec, (0, self.dim - len(vec))) if len(vec) < self.dim else vec[:self.dim]
