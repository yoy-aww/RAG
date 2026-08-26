
"""FastAPI 服务 —— RAG 对外接口。

MVP 阶段接口：
  POST /ingest/file    上传并入库单文档
  POST /ingest/dir     指定目录批量入库
  POST /ask            问答（返回自然语言回答）
  POST /search         纯检索（返回命中文本，便于前端做高亮/引用）
  GET  /info           知识库状态（chunk 数）
  DELETE /clear        清空当前知识库
"""
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from ..core.config import Config
from ..core.retriever import Retriever

cfg = Config()
_retriever = Retriever(doc_id="tenant_001", cfg=cfg)

app = FastAPI(title="RAG 智能问答服务", version="0.1.0")


# ---------- 请求/响应模型 ----------
class AskRequest(BaseModel):
    question: str
    top_k: int | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[dict]


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict]


class IngestResponse(BaseModel):
    chunks_added: int


# ---------- 入库 ----------
@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...)):
    """上传单文档入库。"""
    suf = Path(file.filename or "").suffix
    tmp = Path("data") / f"upload{Path(file.filename or '').stem}{suf}"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_bytes(await file.read())
    n = _retriever.ingest_file(tmp)
    _retriever.save()
    return IngestResponse(chunks_added=n)


@app.post("/ingest/dir", response_model=IngestResponse)
async def ingest_dir(path: str = Form(...)):
    """指定本机目录批量入库。"""
    if not Path(path).is_dir():
        raise HTTPException(400, "目录不存在")
    n = _retriever.ingest_dir(path)
    _retriever.save()
    return IngestResponse(chunks_added=n)


# ---------- 问答 / 检索 ----------
@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """智能问答。"""
    if _retriever.chunk_count == 0:
        return AskResponse(question=req.question,
                           answer="知识库为空，请先上传文档。", sources=[])
    hits = _retriever.search(req.question, req.top_k)
    answer = _retriever.ask(req.question)
    sources = [{"doc": c.doc_name, "score": round(float(s), 4),
                "text": c.content} for c, s in hits]
    return AskResponse(question=req.question, answer=answer, sources=sources)


@app.post("/search", response_model=SearchResponse)
async def search(req: AskRequest):
    """纯向量检索，返回命中文本。"""
    hits = _retriever.search(req.question, req.top_k)
    results = [{"doc": c.doc_name, "score": round(float(s), 4),
                "text": c.content} for c, s in hits]
    return SearchResponse(query=req.question, results=results)


# ---------- 管理 ----------
@app.get("/info")
async def info():
    return {"doc_id": _retriever.doc_id, "chunks": _retriever.chunk_count,
            "model": cfg.EMBEDDING_MODEL, "llm": cfg.LLM_MODEL}


@app.delete("/clear")
async def clear():
    _retriever.clear()
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=cfg.HOST, port=cfg.PORT)
