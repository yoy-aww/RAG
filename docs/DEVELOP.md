# 开发 & 学习文档

这份文档给你（或未来的任何开发者）一个进入这套代码的清晰路径：先看懂骨架，再逐个模块吃透，最后知道怎么扩展。

## 推荐阅读顺序

1. **ARCHITECTURE.md** — 先看整体：数据怎么流、模块怎么分工（10 分钟）
2. **本文档** — 看懂每个模块内部在干什么（30 分钟）
3. **对着代码读一遍** `chunker → embedder → vector_store → generator → retriever`（60 分钟）
4. **API.md** — 搞清对外协议
5. **动手改一个功能**（见下「扩展练习」）

## 入口点

- `main.py`：CLI 入口，所有命令最终都调用 `Retriever`
- `src/rag/api/app.py`：HTTP 服务入口，`/ask` 等端点最终调用 `Retriever`

两条路殊途同归，核心都落在 `src/rag/core/retriever.py` 的 `Retriever` 类。

## 模块逐个吃透

### 1. config.py — 配置

- 全部参数走 `.env` 环境变量，dataclass `frozen=True` 防止运行时误改。
- **关键点**：`EMBEDDING_MODE` 决定用 semantic（bge 语义）还是 tfidf（兜底）。生产必须 semantic。
- **扩展**：加字段只需 .env 加一行 + dataclass 加一行 + 用到的模块读一次。

### 2. chunker.py — 文本分块

- `Chunk` 数据类：`content / doc_id / chunk_index / doc_name`。**doc_id 是多租户隔离的根本**，从这步起每个 chunk 都背着客户身份。
- `split` 算法：先按换行把文档切成段落块；短的整段成一个 chunk；超长的用**滑动窗口**（CHUNK_SIZE 窗口，CHUNK_OVERLAP 重叠）保证语义不撕裂。
- **思考**：overlap 设多少合适？太大 → 冗余；太小 → 跨块信息丢失。默认 500/50 是通用起点，按文档类型调。

### 3. embedder.py — 向量化

- 双模式：
  - `semantic`：加载 bge 模型（自动 GPU），`encode(..., normalize_embeddings=True)` 输出 L2 归一化向量（1024 维）。**首次需联网下载模型**，之后本地缓存。
  - `tfidf`：sklearn char n-gram，零下载兜底，但相似度区分度差（实测全趋近 1.000），仅用于开发测试。
- **关键点**：自动设 `HF_ENDPOINT=https://hf-mirror.com`（国内必须，HF 官方被墙）。
- **注意**：GPU 加速来自 torch CUDA 版，若装了 CPU 版 torch 则退化为 CPU 推理（慢数倍）。

### 4. vector_store.py — 向量库

- 用 `faiss.IndexFlatIP`（内积索引）。**为什么内积**：因为 embedder 输出已 L2 归一化，归一化向量的内积就等于余弦相似度。
- 持久化：`index_{doc_id}.faiss`（向量）+ `meta_{doc_id}.pkl`（chunk 文本+元数据）。启动时自动 `_load` 恢复。
- `search` 返回 `(Chunk, float)` 列表。**doc_id 隔离**体现为每个客户独立的文件名。

### 5. generator.py — LLM 生成

- 统一走 **OpenAI 兼容协议**（`openai` 库），所以 Ollama / DeepSeek / 本地任何兼容服务都能插进去，**只改 .env 三行**。
- `_RAG_SYSTEM` 提示词：明确要求「只依据参考资料回答」「答不了就直说」「末尾标来源」——这是防止 LLM 胡编的关键。
- `answer` 包了 try/except：LLM 离线时返回友好错误提示，**不炸服务**。
- `temperature=0.3`：偏事实回答，低随机性。

### 6. retriever.py — 编排（核心）

- 对外的唯一门面。构造时一次性搭好 chunker/embedder/store/generator。
- `ingest_file` / `ingest_dir`：按后缀路由解析器（txt/md/csv/html/xml/pdf/docx/xlsx），失败打印 WARN 跳过不中断。
- `ask`：检索 → 用 generator 拼参考资料 → 生成回答。检索为空时返回「请先上传文档」提示。
- **扩展点**：把 `doc_id` 从硬编码改成按请求/租户路由，就是多租户管理后台的骨架。

### 7. api/app.py — HTTP 服务

- 6 个端点，见 API.md。当前硬编码 `tenant_001`。
- `/ask` 返回 `{question, answer, sources}`；`/search` 返回 `{query, results}`，便于前端做高亮/引用。
- `/docs`：FastAPI 自动生成的交互式 API 文档（Swagger UI）。

## 关键概念速查

| 概念 | 在本系统里是什么 |
|------|----------------|
| chunk | 一段分块后的文档文本，带 doc_id，最小检索单元 |
| embedding | 把文本变向量（bge 模型，1024 维） |
| top_k | 检索返回最相似的 chunk 数，默认 5 |
| 多租户 doc_id | 客户隔离标识，决定独立向量库文件 |
| semantic vs tfidf | 语义向量 vs 词频兜底；生产用 semantic |

## 扩展练习（按难度递进）

1. **【入门】换 LLM**：把 .env 的 LLM_BASE_URL/LLM_MODEL 换成 DeepSeek API，验证 /ask 仍工作——代码零改动。
2. **【入门】加文档格式**：在 retriever.py `_read_text` 加 .pptx 解析。
3. **【进阶】多租户 API**：把 app.py 硬编码的 `tenant_001` 改成按请求 header/参数路由到不同 Retriever。
4. **【进阶】管理后台**：用 React+antd 做一个界面，可创建租户、上传文档、看对话记录（你熟 antd）。
5. **【进阶】检索增强**：加重排序（rerank）层，或混合检索（关键词 + 向量）。
6. **【高级】容器化**：写 Dockerfile + docker-compose，一键部署。
