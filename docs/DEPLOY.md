# 部署与运维

## 生产部署步骤

### 1. 机器环境

- Python 3.13
- （推荐）NVIDIA 显卡 + 驱动，CUDA 12 以上 → 语义向量化 GPU 加速（实测 1010 queries/s）
- 磁盘：bge 模型缓存约 2GB，向量库按文档量增长

### 2. 环境搭建

```bash
# 建干净 venv（关键：不要用全局 python 混装）
uv venv .venv --python 3.13
.venv/Scripts/python.exe -m ensurepip

# 装依赖（CPU 部分，走国内镜像）
PYTHONPATH="" .venv/Scripts/python.exe -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# 装 CUDA 版 torch（有显卡必装，单独走官方源）
PYTHONPATH="" .venv/Scripts/python.exe -m pip install --upgrade "torch==2.6.0+cu124" --index-url https://download.pytorch.org/whl/cu124

# 验证 GPU
.venv/Scripts/python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# 期望输出类似：torch 2.6.0+cu124 CUDA True NVIDIA GeForce RTX 3060
```

### 3. 配置

```bash
copy .env.example .env
```
编辑 `.env`，重点关注：
- `EMBEDDING_MODE=semantic`（生产必须，tfidf 区分度差）
- `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`（按你的 LLM 填）
- `HOST=0.0.0.0`（远程访问必须，127.0.0.1 只本地）
- `HF_ENDPOINT` 默认已设 `https://hf-mirror.com`（国内必须，HF 官方被墙）

### 4. LLM 服务（以 Ollama 本地为例）

```bash
# 拉模型（VPN 下官方源更快；模型较大 qwen2.5:7b 约 5GB）
"C:\Users\<用户>\AppData\Local\Programs\Ollama\ollama.exe" pull qwen2.5:7b
# 启动服务（服务端常驻）
"C:\Users\<用户>\AppData\Local\Programs\Ollama\ollama.exe" serve
```

> Ollama 是可选的。换 DeepSeek / 其他 OpenAI 兼容 API：只改 .env 三行，代码零改动。LLM 离线时 /ask 优雅降级，不影响 /search 检索。

### 5. 启动服务

```bash
# 前台（调试）
PYTHONPATH="C:\yoyac-work\RAG" .venv/Scripts/python.exe main.py serve

# 后台常驻（生产建议用进程管理器，如 Windows 任务 / systemd / PM2）
```

> **关键**：启动命令前必须 `PYTHONPATH="C:\yoyac-work\RAG"`（绝对 Windows 路径），否则 `import src` 失败。venv 的 python 是 Windows 原生，不认 `/c/...` POSIX 路径。

### 6. 前端嵌入

把 `web/widget/rag-widget.js` 部署到任意静态资源可访问的地址，客户页面加一行：

```html
<script src="https://你的域名/widget/rag-widget.js"
        data-rag-api="https://你的域名"
        data-rag-lang="zh"
        data-rag-title="智能问答"></script>
```

跨域注意：如果前端页面域名 ≠ RAG 服务域名，需要在 app.py 加 CORS 中间件（当前默认同域）。

## 多租户（生产必做）

当前 `app.py` 硬编码 `tenant_001`。生产必须按客户隔离：

1. 为每个客户建独立 `Retriever`（不同 `doc_id`）→ 数据物理隔离
2. 把 `doc_id` 做成按请求路由（header / token / 子路径）
3. 加管理后台（React+antd）：创建租户、上传文档、查看对话、计费

## 监控与运维

| 关注点 | 怎么监控 |
|--------|----------|
| 服务存活 | 健康检查 `GET /info`，可接系统进程守护 |
| 知识库状态 | `/info` 看 chunks 数、模型、LLM |
| GPU 利用率 | `nvidia-smi`（embedding 高峰时显存占用）|
| 日志 | Uvicorn 访问日志；生产建议接结构化日志 |
| 磁盘 | vector_db/ 和 HF 缓存 (~2GB) 会增长 |

## 已知限制（当前 MVP）

- 向量库为内存型 FAISS（重启已持久化，但海量文档需换 Milvus）
- 单进程同步，高并发需 uvicorn 多 worker
- 无鉴权（生产必须加 API key / token）
- 无 CORS（跨域需补中间件）
- 无对话历史（当前单轮问答，无多轮上下文）
