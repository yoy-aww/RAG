#!/usr/bin/env python3
"""RAG 服务 CLI 入口 + 服务启动。

这是整个项目的唯一入口文件。所有功能（启动服务、文档入库、问答、
检索、租户管理）都通过命令行参数路由到对应分支。

用法：
  python main.py serve              启动 REST 服务（默认 0.0.0.0:8000）
  python main.py ingest <路径>      入库（文件 or 目录）
  python main.py ask "问题"         问答（检索 + LLM 生成）
  python main.py search "关键词"    纯向量检索（不调用 LLM）
  python main.py info               知识库状态（chunk 数、模型信息）
  python main.py clear              清空知识库
  python main.py tenant ...         租户管理（create/list/delete/reset-key/key）

启动流程（python main.py serve）：
  1. Config()          — 读取 .env 配置（嵌入模型、LLM 地址、分块参数等）
  2. Retriever(...)    — 初始化默认租户的检索引擎：
                         TextChunker（分块规则）
                         Embedder（加载 bge 模型，首次约 2 分钟）
                         VectorStore（创建/恢复 FAISS 向量库）
                         Generator（创建 LLM 客户端，不实际连接）
  3. from app import app — 触发 FastAPI 初始化：
                         Config() 再读一次配置
                         TenantStore 加载租户注册表
                         ensure_default 确保默认租户存在
                         创建 FastAPI app + CORS 中间件
  4. uvicorn.run(app)  — 启动 HTTP 服务，监听 0.0.0.0:8000

返回值约定：0=成功，1=失败（通过 raise SystemExit 传递给 shell）
"""
import sys
from pathlib import Path

# ── 核心依赖：配置 + 检索编排器 ──
# Config:   从 .env 加载全部运行参数（嵌入模型、LLM、分块、多租户等）
# Retriever: 对外的核心对象，封装了「给它文档→入库；给它问题→回答」的完整流水线
from src.rag.core.config import Config
from src.rag.core.retriever import Retriever


def main():
    """CLI 主入口：解析命令参数，路由到对应分支。"""

    # ── 第一步：加载配置 ──
    # Config 是 frozen dataclass，内部调用 load_dotenv() 读取 .env，
    # 所有字段都有默认值兜底，即使没有 .env 也能运行。
    cfg = Config()

    # ── 第二步：初始化默认租户的检索引擎 ──
    # doc_id="tenant_001" 是默认租户，CLI 模式始终操作这个租户的知识库。
    # 内部依次创建：
    #   TextChunker(500, 50)  — 分块规则：500字/块，50字重叠
    #   Embedder("BAAI/bge-large-zh-v1.5", "semantic") — 加载嵌入模型（最耗时）
    #   VectorStore(embedder, "vector_db", "tenant_001") — 创建/恢复 FAISS 索引
    #   Generator(cfg) — 创建 OpenAI 兼容客户端（连接 Ollama）
    retriever = Retriever(doc_id="tenant_001", cfg=cfg)

    # ── 解析命令行参数 ──
    # sys.argv[0] 是脚本名本身，[1:] 取用户输入的命令和参数
    args = sys.argv[1:]
    if not args:
        _usage(); return 1

    # ── 命令路由 ──
    cmd = args[0]

    # ----------------------------------------------------------------
    # serve: 启动 FastAPI REST 服务
    # ----------------------------------------------------------------
    # 延迟导入 FastAPI/Uvicorn，避免 CLI 其他命令（如 ask/search）
    # 也要等待这些包加载。import 触发 app.py 模块级代码执行：
    #   - 创建第二个 Config 实例
    #   - 加载 TenantStore 租户注册表
    #   - ensure_default() 确保默认租户存在
    #   - 创建 FastAPI app + CORS 中间件
    if cmd == "serve":
        from fastapi import FastAPI
        from src.rag.api.app import app
        import uvicorn
        print(f"启动 RAG 服务 http://{cfg.HOST}:{cfg.PORT}")
        print(f"文档: http://{cfg.HOST}:{cfg.PORT}/docs")
        uvicorn.run(app, host=cfg.HOST, port=cfg.PORT)
        return 0

    # ----------------------------------------------------------------
    # ingest: 文档入库
    # ----------------------------------------------------------------
    # 支持单文件和目录（递归扫描）。解析→分块→向量化→写入 FAISS 索引。
    # 必须显式 save()，否则数据只在内存中，进程退出后丢失。
    if cmd == "ingest":
        if len(args) < 2:
            print("用法: python main.py ingest <文件/目录>"); return 1
        p = Path(args[1])
        if p.is_dir():
            n = retriever.ingest_dir(p)    # 递归扫描目录，批量入库
        else:
            n = retriever.ingest_file(p)   # 单文件入库
        retriever.save()                   # 持久化向量库到 disk
        print(f"入库完成，新增 {n} 个 chunk（当前共 {retriever.chunk_count}）")
        return 0

    # ----------------------------------------------------------------
    # ask: 智能问答（检索 + LLM 生成）
    # ----------------------------------------------------------------
    # 完整 RAG 流程：问题向量化 → FAISS 检索 top_k → 拼装参考资料 → LLM 生成回答
    # 多个参数用空格拼接，允许: python main.py ask 逆变器 质保 多久
    if cmd == "ask":
        q = " ".join(args[1:])
        ans = retriever.ask(q)
        print(ans)
        return 0

    # ----------------------------------------------------------------
    # search: 纯向量检索（不调用 LLM）
    # ----------------------------------------------------------------
    # 只返回 FAISS 检索命中的 chunk 列表，适合调试检索质量。
    # 输出格式：[相似度] [来源文件] 内容前120字
    if cmd == "search":
        q = " ".join(args[1:])
        hits = retriever.search(q)
        if not hits:
            print("（未命中）"); return 0
        for c, s in hits:
            print(f"[sim={s:.3f}] [{c.doc_name}] {c.content[:120]}")
        return 0

    # ----------------------------------------------------------------
    # info: 知识库状态
    # ----------------------------------------------------------------
    # 显示当前租户的 chunk 数量、嵌入模型、LLM 模型及地址
    if cmd == "info":
        print(f"doc_id: {retriever.doc_id}")
        print(f"chunks: {retriever.chunk_count}")
        print(f"embedding: {cfg.EMBEDDING_MODEL}")
        print(f"llm: {cfg.LLM_MODEL} @ {cfg.LLM_BASE_URL}")
        return 0

    # ----------------------------------------------------------------
    # clear: 清空知识库
    # ----------------------------------------------------------------
    # 重置 FAISS 索引 + 清空 chunks 列表 + 保存到磁盘（覆盖旧文件）
    if cmd == "clear":
        retriever.clear()
        print("知识库已清空")
        return 0

    # ----------------------------------------------------------------
    # tenant: 租户管理（多租户 CRUD）
    # ----------------------------------------------------------------
    # 委托给 _tenant_cmd() 处理，独立子命令解析
    if cmd == "tenant":
        return _tenant_cmd(args[1:])

    # 未匹配任何命令，打印用法
    print(f"未知命令: {cmd}"); _usage(); return 1


def _tenant_cmd(args):
    """租户管理子命令。

    用法: python main.py tenant <操作> [参数]
      tenant create <名字>           创建租户，返回 tenant_id + api_key
      tenant list                    列出所有租户（api_key 只显示掩码）
      tenant delete <tenant_id>      删除租户
      tenant reset-key <tenant_id>   重置 API key（旧 key 立即失效）
      tenant key <tenant_id>         查看完整 API key

    租户是多租户隔离的基础：每个租户有独立的向量库文件（index_{id}.faiss），
    调用方凭 api_key 路由到自己的知识库，不同客户数据绝不串扰。
    """
    # 延迟导入，避免非 tenant 命令也加载租户存储
    from src.rag.core.tenant_store import TenantStore
    store = TenantStore()  # 从 tenant_db/tenants.json 加载租户注册表

    if not args:
        print("用法: tenant create <名字> | list | delete <id> | reset-key <id> | key <id>")
        return 1
    op = args[0]

    # ── create: 创建租户 ──
    # 自动生成 tenant_id（基于时间戳）和 api_key（secrets.token_hex(16)）
    # api_key 仅在此处完整显示，之后 list 只展示掩码
    if op == "create":
        if len(args) < 2:
            print("用法: tenant create <名字>"); return 1
        rec = store.create(" ".join(args[1:]))  # 名字可能含空格，合并剩余参数
        print(f"租户创建成功:")
        print(f"  tenant_id: {rec['tenant_id']}")
        print(f"  name:      {rec['name']}")
        print(f"  api_key:   {rec['api_key']}  ← 保存好，之后不再完整显示")
        return 0

    # ── list: 列出所有租户 ──
    # api_key 只显示前6位+后4位的掩码，防泄露
    # chunk 数通过 _peek_chunk_count_cli() 直接读 pkl 文件，不加载嵌入模型
    if op == "list":
        tenants = store.list()
        if not tenants:
            print("（暂无租户）"); return 0
        print(f"{'tenant_id':<14} {'name':<12} {'api_key':<20} {'chunks':<7} 创建时间")
        for t in tenants:
            chunks = _peek_chunk_count_cli(t["tenant_id"])
            print(f"{t['tenant_id']:<14} {t['name']:<12} {t['api_key_masked']:<20} {chunks:<7} {t['created_at']}")
        return 0

    # ── delete / reset-key / key: 需要 tenant_id 的操作 ──
    if op in ("delete", "reset-key", "key"):
        if len(args) < 2:
            print(f"用法: tenant {op} <id>"); return 1
        tid = args[1]

        # delete: 从注册表删除（注意：不删除向量库文件，需手动清理）
        if op == "delete":
            try:
                store.delete(tid)
                print(f"租户 {tid} 已删除")
            except Exception as e:
                print(f"删除失败: {e}"); return 1
            return 0

        # reset-key: 生成新 api_key 替换旧的，旧 key 立即失效
        if op == "reset-key":
            try:
                print(f"新 api_key: {store.reset_key(tid)}")
            except Exception as e:
                print(f"重置失败: {e}"); return 1
            return 0

        # key: 查看指定租户的完整 api_key（管理用途）
        rec = store.get(tid)
        if not rec:
            print(f"租户 {tid} 不存在"); return 1
        print(rec["api_key"])
        return 0

    print(f"未知操作: {op}"); return 1


def _peek_chunk_count_cli(tenant_id: str) -> int:
    """直接读取 pkl 元数据文件获取 chunk 数，不加载嵌入模型。

    为什么不直接用 Retriever.chunk_count？
    因为创建 Retriever 会触发 Embedder 加载（bge 模型 ~1GB），
    在 tenant list 时对每个租户都加载一遍不可接受。
    所以直接读 meta_{tenant_id}.pkl 的列表长度，零开销。

    参数:
        tenant_id: 租户 ID，对应文件 meta_{tenant_id}.pkl
    返回:
        chunk 数量；文件不存在或读取失败返回 0
    """
    try:
        import pickle
        p = Path(cfg.VECTOR_DB_DIR) / f"meta_{tenant_id}.pkl"
        if p.exists():
            return len(pickle.load(open(p, "rb")))
    except Exception:
        pass
    return 0


def _usage():
    """打印用法说明（复用模块级 __doc__）。"""
    print(__doc__)


if __name__ == "__main__":
    # raise SystemExit() 让 shell 能拿到退出码（0=成功，1=失败）
    # 比 sys.exit() 更规范：不会在 try/except 中被捕获
    raise SystemExit(main())
