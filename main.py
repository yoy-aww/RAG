
#!/usr/bin/env python3
"""RAG 服务 CLI 入口 + 服务启动。

用法：
  python main.py serve          启动 REST 服务（默认 0.0.0.0:8000）
  python main.py ingest <路径>  入库（文件 of 目录）
  python main.py ask "问题"      问答
  python main.py search "关键词" 纯检索
  python main.py info           知识库状态
  python main.py clear          清空知识库
"""
import sys
from pathlib import Path

from src.rag.core.config import Config
from src.rag.core.retriever import Retriever


def main():
    cfg = Config()
    retriever = Retriever(doc_id="tenant_001", cfg=cfg)
    args = sys.argv[1:]
    if not args:
        _usage(); return 1

    cmd = args[0]
    if cmd == "serve":
        from fastapi import FastAPI
        from src.rag.api.app import app
        import uvicorn
        print(f"启动 RAG 服务 http://{cfg.HOST}:{cfg.PORT}")
        print(f"文档: http://{cfg.HOST}:{cfg.PORT}/docs")
        uvicorn.run(app, host=cfg.HOST, port=cfg.PORT)
        return 0

    if cmd == "ingest":
        if len(args) < 2:
            print("用法: python main.py ingest <文件/目录>"); return 1
        p = Path(args[1])
        if p.is_dir():
            n = retriever.ingest_dir(p)
        else:
            n = retriever.ingest_file(p)
        retriever.save()
        print(f"入库完成，新增 {n} 个 chunk（当前共 {retriever.chunk_count}）")
        return 0

    if cmd == "ask":
        q = " ".join(args[1:])
        ans = retriever.ask(q)
        print(ans)
        return 0

    if cmd == "search":
        q = " ".join(args[1:])
        hits = retriever.search(q)
        if not hits:
            print("（未命中）"); return 0
        for c, s in hits:
            print(f"[sim={s:.3f}] [{c.doc_name}] {c.content[:120]}")
        return 0

    if cmd == "info":
        print(f"doc_id: {retriever.doc_id}")
        print(f"chunks: {retriever.chunk_count}")
        print(f"embedding: {cfg.EMBEDDING_MODEL}")
        print(f"llm: {cfg.LLM_MODEL} @ {cfg.LLM_BASE_URL}")
        return 0

    if cmd == "clear":
        retriever.clear()
        print("知识库已清空")
        return 0

    print(f"未知命令: {cmd}"); _usage(); return 1


def _usage():
    print(__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
