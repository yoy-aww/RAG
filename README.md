RAG 智能问答服务

详细快速开始见 PLAN.md

## 命令
main.py serve | ingest <文件/目录> | ask <问题> | search <关键词> | info | clear

## 接口
POST /ingest/file /ingest/dir | /ask | /search
GET /info | DELETE /clear

## 架构
src/rag/core: config chunker embedder vector_store generator retriever
src/rag/api: app.py (FastAPI)

## 配置
.env.example 为模板。EMBEDDING_MODE=tfidf 兜底立即可跑，=semantic 用 bge 中文语义检索(需GPU)。
LLM 默认 Ollama 本地，离线时/ask优雅降级。

## 多租户
每个客户一个 Retriever 实例，doc_id 隔离向量空间与文档。
