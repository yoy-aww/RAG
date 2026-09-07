# 项目概览（OVERVIEW）

> 本文件是项目总览：它是做什么的、现在做到什么程度、由哪些部分组成、怎么跑起来、下一步去哪。
> 详细文档导航见 README.md；本文件聚焦「现状事实」，均来自实际运行验证。

## 1. 一句话定位

面向企业的 **「嵌入现有系统的 AI 问答窗口」服务**：客户上传文档 → 系统分块 + 语义向量化 + 入库 → 用户提问时检索相关片段 → 本地大模型基于片段生成**带来源引用**的回答 → 前端浮窗一行 `<script>` 嵌入客户任何网页。

**卖的不是 RAG 技术，是「花几万块，在客户的客服系统/官网里加一个不用培训就能用的 AI 问答窗口」。**

## 2. 工作原理（一句话）

```
文档上传 → 解析纯文本 → 分块(带 doc_id) → bge 向量化(1024维) → FAISS 入库
提问 → 问题向量化 → FAISS 检索 top_k 片段 → 拼成参考资料 → LLM 生成带来源的回答
```

## 3. 当前完成度（实测验证过的事实）

| 能力 | 状态 | 实测数据 |
|------|------|---------|
| 文档入库 | ✅ 完成 | 支持 txt/md/csv/html/xml/pdf/docx/xlsx，按后缀路由解析，失败跳过不中断 |
| 语义检索 | ✅ 完成 | bge-large-zh-v1.5，GPU 加速 **1010 queries/s**（1000 条 0.99 秒） |
| LLM 生成 | ✅ 完成 | OpenAI 兼容协议，Ollama 本地 qwen3:8b；LLM 离线时优雅降级不炸服务 |
| 检索质量 | ✅ 完成 | bge 语义 vs TF-IDF：相似度从全 1.000 的真实排序提升到 0.74 区分度 |
| 前端浮窗 SDK | ✅ 完成 | 纯原生 JS 单文件（84 行），无框架依赖，一行 script 嵌入 |
| REST API | ✅ 完成 | 6 个端点 + FastAPI 自动 Swagger 文档 |
| MySQL Text-to-SQL 通道 | ✅ 完成 | 只读账号 rag_ro，代码层强制仅 SELECT，结果限 100 行 |
| 商城数据导入 | ✅ 完成 | 6 张表全量导出入库（方案 A：导出→入库，非实时同步） |
| 多租户 | ⚠️ 半成品 | 引擎层已按 doc_id 物理隔离，但 API 层硬编码 tenant_001 |
| 鉴权/CORS/对话历史 | ❌ 未做 | 生产上线前必补 |

## 4. 代码结构（核心代码约 1030 行）

```
main.py                        CLI 入口（serve / ingest / ask / search / info / clear）— 84 行
src/rag/
  core/
    config.py                  全部参数走 .env，dataclass 冻结 — 39 行
    chunker.py                 换行粗切 + 滑动窗口精切，每块带 doc_id — 43 行
    embedder.py                双模式：semantic(bge, GPU) / tfidf(零下载兜底) — 56 行
    vector_store.py            FAISS IndexFlatIP + 元数据 pkl 持久化 — 84 行
    generator.py               LLM 生成，system prompt 注入资料、要求标来源 — 52 行
    retriever.py               编排门面：入库/问答对外的唯一对象 — 95 行
    db_retriever.py            MySQL Text-to-SQL 检索通道 — 173 行
  api/
    app.py                     FastAPI 服务，6 端点，已开 CORS — 121 行
scripts/import_mall.py         商城 SQLite → 文本 → /ingest/file 入库（--dry-run/--table）— 202 行
web/
  widget/rag-widget.js         自包含浮窗 SDK（一行 script 嵌入）— 84 行
  demo/index.html / rag-ui.html 演示页
docs/                          README / ARCHITECTURE / DEVELOP / API / DEPLOY / OVERVIEW
TROUBLESHOOTING.md             真实踩坑记录（PYTHONPATH 污染、CPU torch、MSYS 路径等 7 条）
```

## 5. 数据现状

- **向量库**：`vector_db/index_tenant_001.faiss`（118KB）+ `meta_tenant_001.pkl`，已持久化，重启自动恢复
- **data/ 内容**：
  - `光伏组件产品手册.txt` — 最初示例文档（朋友公司场景，仅演示用）
  - `mall_*.md` — 商城 6 表原始导出（products/categories/orders/reviews/banners/aftersales）
  - `uploadmall_*.md` — 入库前文本格式（如「野生人参片 [ID:herbs_1] 价格 ¥488.0 …」）

## 6. 配置现状（.env 实测值）

```
EMBEDDING_MODE=semantic        # bge 中文语义检索
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
CHUNK_SIZE=500 / OVERLAP=50 / TOP_K=5
LLM_BASE_URL=http://localhost:11434/v1   # Ollama
LLM_MODEL=qwen3:8b
HOST=0.0.0.0 / PORT=8000
MYSQL_ENABLED=true             # Text-to-SQL 通道本地开发已启用
```

环境：Python 3.13 venv（.venv）、torch 2.6.0+cu124（RTX 3060 CUDA 可用 ✅）、faiss ✅、Ollama 已装 qwen3:8b。

## 7. 怎么跑

```bash
# 起 LLM（Ollama 服务常驻）
"C:\Users\aww\AppData\Local\Programs\Ollama\ollama.exe" serve

# 起 RAG 服务（注意 PYTHONPATH 必须绝对 Windows 路径）
PYTHONPATH="C:\yoyac-work\RAG" .venv/Scripts/python.exe main.py serve

# 交互文档 http://localhost:8000/docs ；演示页 web/demo/index.html
# 终端问答：main.py ask "问题"
```

## 8. 下一步路线图（按价值排序）

1. **多租户 API 化**：把 app.py 硬编码的 `tenant_001` 改为按 header/token 路由到独立 Retriever —— 商业化的命门
2. **管理后台**（React+antd）：创建租户、上传文档、看对话记录 —— 你熟的技术栈
3. **生产加固**：API Key 鉴权、CORS、对话历史（多轮）、uvicorn 多 worker
4. **容器化**：Dockerfile + docker-compose，一键部署到客户服务器
5. **商业化验证**：自家公司（或朋友的）真实文档做第一个客户，跑通「文档 → 嵌入 → 使用」全流程，再对外报价

> 回顾 PLAN.md 的提醒：这个项目最大的风险不是技术，而是做完之后没有第一个真实客户。技术骨架已经齐了，下一步的瓶颈是「交付物 + 第一个愿意用的人」，不是再写一行代码。
