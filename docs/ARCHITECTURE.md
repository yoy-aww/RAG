# 系统架构

## 整体架构

系统分三层：嵌入层（客户侧）→ 服务层（RAG API）→ 引擎层（检索 + 生成）。

```
客户现有系统（网站 / ERP / 后台）
┌───────────────────────────────────────────────────┐
│  <script src=".../rag-widget.js">                 │  ← 嵌入层：一行嵌入，客户无需学新技术
│  右下角浮窗：用户输入问题                          │
└───────────────────────┬───────────────────────────┘
                        │ HTTP POST /ask (JSON)
                        ▼
┌───────────────────────────────────────────────────┐
│  RAG 服务层  (FastAPI :8000)                       │
│  POST /ask  →  检索命中 + 生成回答 + 来源引用      │
│  POST /search → 仅检索                            │
│  POST /ingest/file/dir → 文档入库                 │
└───────────────────────┬───────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────────┐
│  引擎层  (src/rag/core)                            │
│  Retriever 编排整个流水线：                        │
│    入库：文档解析 → 分块 → 语义向量化 → 写入向量库  │
│    问答：问题向量化 → FAISS 检索 → 拼装资料 → LLM 生成 │
│  多租户：每个客户一个 doc_id，向量空间隔离          │
└───────────────────────────────────────────────────┘
```

## 核心模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 配置 | `core/config.py` | 全部运行参数走 `.env`，dataclass 冻结防误改 |
| 分块 | `core/chunker.py` | 先按换行粗切段落，超长段落用滑动窗口精切，保证语义连续；每个 chunk 带 `doc_id`（多租户隔离根本） |
| 向量化 | `core/embedder.py` | 双模式：`semantic`(bge 语义，GPU 加速)/`tfidf`(零下载兜底)；自动设 HF 镜像端点 |
| 向量库 | `core/vector_store.py` | FAISS IndexFlatIP（内积），向量已 L2 归一化故内积=余弦；持久化 index + 元数据 pkl |
| 生成 | `core/generator.py` | 走 OpenAI 兼容协议，system prompt 注入检索资料，要求只依据资料回答 + 末尾标来源；调用失败优雅降级 |
| 编排 | `core/retriever.py` | 对外的核心对象。对外只暴露：给它文档→入库；给它问题→回答。支持解析 txt/md/csv/html/xml/pdf/docx/xlsx |

## 数据流向

### 入库流程（用户传文档）

```
文档文件 → 按后缀解析成纯文本(pypdf/docx/openpyxl)
        → chunker 分块（每块带 doc_id + doc_name）
        → embedder 语义向量化（GPU 加速）
        → vector_store 写入 FAISS index + pickle 元数据
```

### 问答流程（用户提问）

```
问题 → embedder 向量化 → FAISS 检索 top_k 最相似 chunk
     → generator 把命中片段拼成「参考资料1..N」注入 system prompt
     → LLM 基于资料生成回答（要求标来源）
     → 返回 {answer, sources:[{doc,score,text}]}
```

## 多租户设计

当前是**实例级隔离**：每个客户一个 `Retriever` 实例，`doc_id` 决定独立的 FAISS index 文件和元数据文件（`index_{doc_id}.faiss`、`meta_{doc_id}.pkl`）。不同客户的数据物理分离，绝不串扰。

> 扩展方向：多租户管理后台（创建客户、分配 doc_id、管理各自文档库）。当前 `app.py` 硬编码 `tenant_001`，生产需做成按租户路由。

## 设计取舍（为什么这么选）

| 决策 | 选择 | 理由 |
|------|------|------|
| 向量化 | 自写 embedder，不引 LangChain/LlamaIndex | MVP 阶段保持逻辑清晰可控，框架太重且黑盒 |
| 向量库 | FAISS 起步 | 零配置、内存检索、够用；文档量再上量可换 ChromaDB/Milvus |
| 嵌入 SDK | 纯原生 JS 单文件 | 跨框架、客户无需任何依赖，一行 script 即可 |
| 多租户 | 实例级 doc_id 隔离 | 简单、物理隔离数据；后期可升级库级隔离 |
