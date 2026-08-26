
"""运行时配置。全部走 .env，避免硬编码敏感信息。"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    # 嵌入
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
    EMBEDDING_MODE: str = os.getenv("EMBEDDING_MODE", "semantic")  # semantic | tfidf
    # 分块
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))
    # 检索
    TOP_K: int = int(os.getenv("TOP_K", "5"))
    # LLM（OpenAI 兼容：Ollama / DeepSeek / 本地）
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen2.5:7b")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "ollama")
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120.0"))
    # 向量库
    VECTOR_DB_DIR: str = os.getenv("VECTOR_DB_DIR", "vector_db")
    # 服务
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
