# RAG 智能问答服务

为其他企业嵌入其现有系统的智能问答窗口。核心能力：把客户的文档（产品手册、售后 FAQ、内部制度等）变成「能准确回答、带来源引用、一行代码嵌入客户网站」的 AI 问答。

## 一句话讲清

客户上传文档 → 系统自动分块 + 语义向量化 + 存进向量库 → 用户提问时检索相关片段 → 大模型基于片段生成带来源引用的回答 → 前端浮窗一行 script 嵌入客户任何网页。

## 一分钟跑起来

```bash
# 0. 环境要求：Python 3.13 + (可选 RTX 显卡加速)
# 1. 建干净 venv
uv venv .venv --python 3.13
.venv/Scripts/python.exe -m ensurepip

# 2. 装 CPU 依赖（走国内镜像）
PYTHONPATH="" .venv/Scripts/python.exe -m pip install -r requirements.txt ^
  -i https://mirrors.aliyun.com/pypi/simple

# 3. 装 CUDA 版 torch（有 NVIDIA 显卡必装，否则 3060 闲置）
PYTHONPATH="" .venv/Scripts/python.exe -m pip install --upgrade ^
  "torch==2.6.0+cu124" --index-url https://download.pytorch.org/whl/cu124

# 4. 配好 .env（复制模板）
copy .env.example .env
#    默认 EMBEDDING_MODE=semantic 用 bge 中文语义检索，首次启动需联网下载模型

# 5. 启动本地 LLM（Ollama，模型离线时问答优雅降级不炸）
"C:\Users\<你的用户>\AppData\Local\Programs\Ollama\ollama.exe" pull qwen2.5:7b
"C:\Users\<你的用户>\AppData\Local\Programs\Ollama\ollama.exe" serve

# 6. 启动 RAG 服务
PYTHONPATH="C:\yoyac-work\RAG" .venv/Scripts/python.exe main.py serve
# 打开 http://localhost:8000/docs 看自动生成的 API 文档
# 浏览器打开 web/demo/index.html 看嵌入浮窗演示
```

> 环境配置踩坑极多，详见 [DEPLOY.md](docs/DEPLOY.md) 和 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)。

## 常用命令

```bash
main.py serve              # 启动 REST 服务 (0.0.0.0:8000)
main.py ingest <文件/目录> # 上传文档入库
main.py ask "问题"        # 终端问答
main.py search "关键词"   # 终端纯检索
main.py info              # 知识库状态
main.py clear             # 清空知识库
```

## 目录结构

```
main.py                  # CLI 入口
.env / .env.example      # 配置（运行参数全部走 .env）
requirements.txt         # 依赖清单
TROUBLESHOOTING.md       # 真实踩坑记录
docs/
  ARCHITECTURE.md        # 系统架构 + 模块职责
  DEVELOP.md             # 开发/学习文档：如何看懂并扩展代码
  DEPLOY.md              # 生产部署 + 监控 + 运维
  API.md                 # 完整接口契约
src/rag/core/            # RAG 引擎
  config.py   chunker.py embedder.py
  vector_store.py generator.py retriever.py
src/rag/api/
  app.py                 # FastAPI 服务（6 个端点）
web/widget/rag-widget.js # 自包含前端浮窗 SDK（客户一行嵌入）
web/demo/index.html      # 嵌入演示页
data/                    # 示例文档（光伏组件产品手册）
vector_db/               # 向量库持久化目录（运行生成，已 .gitignore）
```

## 文档导航

| 想做什么 | 看哪份 |
|----------|--------|
| 把项目跑起来、配环境 | 本 README + [DEPLOY.md](docs/DEPLOY.md) |
| 搞懂系统怎么工作、数据怎么流 | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 看懂代码、改功能、加模块 | [DEVELOP.md](docs/DEVELOP.md) |
| 改接口、接前端、对协议 | [API.md](docs/API.md) |
| 部署上线、运维、监控 | [DEPLOY.md](docs/DEPLOY.md) |
| 遇到环境/安装报错 | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |

## 技术栈

- **检索**：sentence-transformers + bge-large-zh-v1.5（中文语义）/ TF-IDF 兜底
- **向量库**：FAISS（IndexFlatIP，内积 = 余弦相似度）
- **生成**：任何 OpenAI 兼容协议 LLM（Ollama 本地 / DeepSeek / 其他）
- **服务**：FastAPI + Uvicorn
- **前端**：纯原生 JS 浮窗 SDK，无框架依赖，客户一行 script 嵌入

## 关键事实（已实测）

- bge 语义检索 vs TF-IDF：相似度从全 1.000 的真实排序提升到 0.74 区分度，命中准确段落
- RTX 3060 GPU 加速 embedding：1010 queries/s（1000 条 0.99 秒）
- LLM 离线时 /ask 优雅降级返回提示，不中断检索
