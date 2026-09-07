"""FastAPI 服务 —— RAG 对外接口（多租户版）。

鉴权模型：
  - 业务端点（/ask /search /ingest/* /info /clear）：凭 X-API-Key 路由到对应租户
    · 带 key → 查租户注册表 → 该租户的 Retriever（独立向量库）
    · 不带 key → ALLOW_ANON=true 时落到默认租户（本地开发），否则 401
  - 管理端点（/admin/*）：凭 X-Admin-Key（.env ADMIN_API_KEY）管理租户

数据隔离：
  租户 ↔ 独立向量库文件（index_{tenant_id}.faiss），引擎层已物理隔离，
  本层只负责「钥匙 → 租户 → 知识库」的路由，两层合起来才是完整多租户。
"""
import os
import re

from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..core.config import Config
from ..core.retriever import Retriever
from ..core.embedder import get_embedder
from ..core.tenant_store import TenantStore, TenantNotFound

cfg = Config()

# ---------- 租户注册表 ----------
tenant_store = TenantStore()
tenant_store.ensure_default(cfg.DEFAULT_API_KEY)

# 租户 → Retriever 缓存（懒加载，共享同一个 Embedder 实例）
_retrievers: dict[str, Retriever] = {}


def _get_retriever(tenant_id: str) -> Retriever:
    if tenant_id not in _retrievers:
        emb = get_embedder(cfg.EMBEDDING_MODEL, cfg.EMBEDDING_MODE)
        r = Retriever(doc_id=tenant_id, cfg=cfg, embedder=emb)
        _retrievers[tenant_id] = r
    return _retrievers[tenant_id]


def _resolve_tenant(x_api_key: str | None) -> str:
    """API key → tenant_id。无效 key 一律 401。"""
    if x_api_key:
        rec = tenant_store.get_by_key(x_api_key)
        if rec and rec.get("status") == "active":
            return rec["tenant_id"]
        raise HTTPException(401, "API key 无效或已停用")
    if cfg.ALLOW_ANON:
        return tenant_store.default_tenant_id
    raise HTTPException(401, "缺少 X-API-Key 请求头")


def _require_admin(x_admin_key: str | None = Header(None, alias="X-Admin-Key")):
    if not x_admin_key or x_admin_key != cfg.ADMIN_API_KEY:
        raise HTTPException(401, "管理密钥无效")


app = FastAPI(title="RAG 智能问答服务", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
    product_ids: list[str] = []


class IngestResponse(BaseModel):
    chunks_added: int


class TenantCreateRequest(BaseModel):
    name: str


# ---------- 业务端点（X-API-Key 路由） ----------
@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(file: UploadFile = File(...),
                      x_api_key: str | None = Header(None, alias="X-API-Key")):
    """上传单文档入库（写入调用方租户的知识库）。"""
    retriever = _get_retriever(_resolve_tenant(x_api_key))
    suf = Path(file.filename or "").suffix
    tmp = Path("data") / f"upload{Path(file.filename or '').stem}{suf}"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_bytes(await file.read())
    n = retriever.ingest_file(tmp)
    retriever.save()
    return IngestResponse(chunks_added=n)


@app.post("/ingest/dir", response_model=IngestResponse)
async def ingest_dir(path: str = Form(...),
                     x_api_key: str | None = Header(None, alias="X-API-Key")):
    """指定本机目录批量入库（写入调用方租户的知识库）。"""
    retriever = _get_retriever(_resolve_tenant(x_api_key))
    if not Path(path).is_dir():
        raise HTTPException(400, "目录不存在")
    n = retriever.ingest_dir(path)
    retriever.save()
    return IngestResponse(chunks_added=n)


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest,
              x_api_key: str | None = Header(None, alias="X-API-Key")):
    """智能问答（只检索调用方租户的知识库）。"""
    retriever = _get_retriever(_resolve_tenant(x_api_key))
    if retriever.chunk_count == 0:
        return AskResponse(question=req.question,
                           answer="知识库为空，请先上传文档。", sources=[], product_ids=[])
    hits = retriever.search(req.question, req.top_k)
    answer = retriever.ask(req.question)
    sources = [{"doc": c.doc_name, "score": round(float(s), 4),
                "text": c.content} for c, s in hits]

    # 从 sources 文本中提取商品 ID
    product_ids = []
    for src in sources:
        ids = re.findall(r'\[ID:([^\]]+)\]', src["text"])
        for pid in ids:
            if pid not in product_ids:
                product_ids.append(pid)

    return AskResponse(question=req.question, answer=answer, sources=sources, product_ids=product_ids)


@app.post("/search", response_model=SearchResponse)
async def search(req: AskRequest,
                 x_api_key: str | None = Header(None, alias="X-API-Key")):
    """纯向量检索（只检索调用方租户的知识库）。"""
    retriever = _get_retriever(_resolve_tenant(x_api_key))
    hits = retriever.search(req.question, req.top_k)
    results = [{"doc": c.doc_name, "score": round(float(s), 4),
                "text": c.content} for c, s in hits]
    return SearchResponse(query=req.question, results=results)


@app.get("/info")
async def info(x_api_key: str | None = Header(None, alias="X-API-Key")):
    """当前租户知识库状态。"""
    tenant_id = _resolve_tenant(x_api_key)
    retriever = _get_retriever(tenant_id)
    return {"tenant_id": tenant_id, "chunks": retriever.chunk_count,
            "model": cfg.EMBEDDING_MODEL, "llm": cfg.LLM_MODEL}


@app.delete("/clear")
async def clear(x_api_key: str | None = Header(None, alias="X-API-Key")):
    """清空当前租户的知识库。"""
    retriever = _get_retriever(_resolve_tenant(x_api_key))
    retriever.clear()
    return {"status": "cleared"}


# ---------- 管理端点（X-Admin-Key 鉴权） ----------
@app.post("/admin/tenants")
async def admin_create_tenant(req: TenantCreateRequest,
                              _: None = Depends(_require_admin)):
    """创建租户，返回 tenant_id + api_key（仅此一次完整可见）。"""
    rec = tenant_store.create(req.name.strip())
    return {"tenant_id": rec["tenant_id"], "name": rec["name"],
            "api_key": rec["api_key"], "created_at": rec["created_at"]}


@app.get("/admin/tenants")
async def admin_list_tenants(_: None = Depends(_require_admin)):
    """租户列表（api_key 只显示掩码）。"""
    tenants = tenant_store.list()
    for t in tenants:
        r = _retrievers.get(t["tenant_id"])
        t["chunks"] = r.chunk_count if r else _peek_chunk_count(t["tenant_id"])
    return {"tenants": tenants}


def _peek_chunk_count(tenant_id: str) -> int:
    """不加载模型的情况下读取已有向量库的 chunk 数（读 pkl 元数据）。"""
    try:
        import pickle
        p = Path(cfg.VECTOR_DB_DIR) / f"meta_{tenant_id}.pkl"
        if p.exists():
            return len(pickle.load(open(p, "rb")))
    except Exception:
        pass
    return 0


@app.delete("/admin/tenants/{tenant_id}")
async def admin_delete_tenant(tenant_id: str,
                              _: None = Depends(_require_admin)):
    """删除租户（注册表 + 内存缓存；向量库文件一并删除）。"""
    try:
        tenant_store.delete(tenant_id)
    except TenantNotFound:
        raise HTTPException(404, f"租户 {tenant_id} 不存在")
    _retrievers.pop(tenant_id, None)
    for suf in (".faiss", ".pkl"):
        p = Path(cfg.VECTOR_DB_DIR) / f"{('index' if suf == '.faiss' else 'meta')}_{tenant_id}{suf}"
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
    return {"status": "deleted", "tenant_id": tenant_id}


@app.post("/admin/tenants/{tenant_id}/reset-key")
async def admin_reset_key(tenant_id: str,
                          _: None = Depends(_require_admin)):
    """重置 API key（旧 key 立即失效）。"""
    try:
        new_key = tenant_store.reset_key(tenant_id)
    except TenantNotFound:
        raise HTTPException(404, f"租户 {tenant_id} 不存在")
    return {"status": "reset", "tenant_id": tenant_id, "api_key": new_key}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=cfg.HOST, port=cfg.PORT)
