# RAG 智能问答服务

把客户的文档（产品手册、售后 FAQ、内部制度等）变成「能准确回答、带来源引用、一行代码嵌入客户网站」的 AI 问答。

## 系统架构

```
客户文档 → 自动分块 → 语义向量化 → FAISS 向量库
                                     ↓
用户提问 → 检索相关片段 → LLM 生成回答（带来源引用）
                                     ↓
前端浮窗 SDK（一行 script 嵌入客户网页）
```

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 本地 venv |
| torch | 2.6.0+cu124 | CUDA 版，RTX 显卡加速 |
| Ollama | 任意最新版 | 本地 LLM，模型 `qwen2.5:7b` |

## 快速开始

### 1. 创建虚拟环境

```bash
cd C:\yoyac-work\RAG
uv venv .venv --python 3.11
.venv\Scripts\activate
```

### 2. 安装依赖

```bash
# CPU 依赖（走国内镜像）
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# CUDA 版 torch（必须单独装，否则装成 CPU 版，显卡闲置）
pip install --upgrade "torch==2.6.0+cu124" --index-url https://download.pytorch.org/whl/cu124
```

### 3. 配置

```bash
copy .env.example .env
```

关键配置项：

```env
EMBEDDING_MODE=semantic          # 语义检索（需联网下载模型，首次约 2 分钟）
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:7b
PORT=8000
```

### 4. 启动 Ollama（本地 LLM）

```bash
ollama pull qwen2.5:7b
ollama serve
```

### 5. 启动 RAG 服务

```bash
python main.py serve
```

验证：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/info
- 嵌入浮窗演示：打开 `web/demo/index.html`

## 常用命令

```bash
python main.py serve              # 启动 REST 服务 (0.0.0.0:8000)
python main.py ingest <文件/目录>  # 上传文档入库
python main.py ask "问题"          # 终端问答
python main.py search "关键词"     # 终端纯检索
python main.py info               # 知识库状态
python main.py clear              # 清空知识库
```

## 启动方式（Windows 生产环境）

| 方式 | 命令 | 说明 |
|------|------|------|
| **开发调试** | `python main.py serve` | 前台运行，Ctrl+C 停止 |
| **后台静默** | `python start_service.py` | pythonw 无控制台，双击即用 |
| **守护进程** | `python start_daemon.py` | 双 fork 脱离，崩溃自动重启 |
| **BAT 脚本** | `双击 start_rag.bat` | 前台运行，崩溃 3 秒后自动重启 |
| **PowerShell** | `.\start_rag.ps1` | 隐藏窗口后台启动 |
| **Uvicorn 直启** | `uvicorn src.rag.api.app:app --host 0.0.0.0 --port 8000` | 直接调 API |

### 推荐：守护进程模式

```bash
python start_daemon.py
# 日志输出到 rag.log，崩溃自动重启，不占控制台
```

### 推荐：BAT 脚本（最简单）

```bash
双击 start_rag.bat
# 窗口内实时输出日志，Ctrl+C 停止
# 如果进程意外退出，3 秒后自动重启
```

## 打包为 EXE

使用 PyInstaller 打包为独立 EXE（无需安装 Python）：

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包（使用项目根目录的 main.spec）
pyinstaller main.spec
```

### 产出

```
dist/
  main/                        # 可执行目录
    main.exe                   # 入口 EXE
    _internal/                 # 打包后的依赖
```

### 运行打包后的 EXE

```bash
cd dist\main
main.exe serve                 # 启动服务
main.exe ingest data\           # 入库
main.exe ask "问题"             # 问答
```

### 打包注意事项

| 问题 | 解决 |
|------|------|
| faiss-cpu 打包后找不到 | `main.spec` 的 `binaries` 加上 `faiss` 的 DLL |
| torch DLL 缺失 | `binaries` 加上 `torch\lib\*.dll` |
| sentence-transformers 模型下载 | 打包前先用 `EMBEDDING_MODE=tfidf` 启动一次生成缓存，或把模型目录打进 `datas` |
| 打包体积大（>2GB） | 考虑用 `--exclude-module` 排除未用的 torch 子模块，或使用 Docker 部署 |

### 完整 main.spec 示例（生产用）

```python
# -*- mode: python ; coding: utf-8 -*-
import os, glob

# 自动收集 torch 的 CUDA DLL
torch_path = os.path.dirname(os.path.dirname(__file__))
torch_libs = [
    (os.path.join(torch_path, 'torch', 'lib', lib), 'torch/lib')
    for lib in os.listdir(os.path.join(torch_path, 'torch', 'lib'))
    if lib.endswith('.dll')
]

a = Analysis(
    ['main.py'],
    binaries=torch_libs,
    datas=[],
    hiddenimports=['faiss', 'sentence_transformers'],
    ...
)
```

## 目录结构

```
RAG/
├── main.py                  # CLI 入口
├── main.spec                # PyInstaller 打包配置
├── start_service.py         # Windows 后台启动（pythonw）
├── start_daemon.py          # 守护进程（双 fork 脱离）
├── start_rag.bat            # BAT 启动脚本（自动重启）
├── start_rag.ps1            # PowerShell 启动脚本
├── start_rag.vbs            # VBS 启动脚本（无窗口）
├── .env / .env.example      # 配置
├── requirements.txt         # 依赖清单
├── rag.log                  # 守护进程日志
│
├── src/rag/
│   ├── core/                # RAG 引擎
│   │   ├── config.py        #   配置加载
│   │   ├── chunker.py       #   文本分块
│   │   ├── embedder.py      #   向量化（bge / TF-IDF）
│   │   ├── vector_store.py  #   FAISS 向量库
│   │   ├── generator.py     #   LLM 生成
│   │   ├── retriever.py     #   检索 + 生成
│   │   └── tenant_store.py  #   多租户管理
│   └── api/
│       └── app.py           # FastAPI 服务
│
├── web/
│   ├── widget/
│   │   └── rag-widget.js    # 前端浮窗 SDK（一行 script 嵌入）
│   └── demo/
│       ├── index.html       # 嵌入演示页
│       └── rag-ui.html      # 独立 UI 页面
│
├── data/                    # 示例文档
├── vector_db/               # 向量库持久化（运行生成，已 .gitignore）
├── tenant_db/               # 租户数据（运行生成，已 .gitignore）
├── docs/                    # 详细文档
│   ├── ARCHITECTURE.md      # 系统架构
│   ├── DEVELOP.md           # 开发指南
│   ├── DEPLOY.md            # 生产部署
│   ├── API.md               # 接口契约
│   └── OVERVIEW.md          # 项目概览
│
├── scripts/                 # 辅助脚本
└── TROUBLESHOOTING.md       # 踩坑记录
```

## API 接口

| 端点 | 方法 | 说明 | 鉴权 |
|------|------|------|------|
| `/info` | GET | 知识库状态 | X-API-Key |
| `/ask` | POST | 问答（带来源引用） | X-API-Key |
| `/search` | POST | 纯检索 | X-API-Key |
| `/ingest/file` | POST | 上传文件入库 | X-API-Key |
| `/ingest/url` | POST | URL 入库 | X-API-Key |
| `/clear` | POST | 清空知识库 | X-API-Key |
| `/admin/tenants` | GET | 租户列表 | X-Admin-Key |
| `/admin/tenants` | POST | 创建租户 | X-Admin-Key |
| `/admin/tenants/:id` | DELETE | 删除租户 | X-Admin-Key |
| `/admin/tenants/:id/reset-key` | POST | 重置 API Key | X-Admin-Key |

完整契约见 `docs/API.md`。

## 技术栈

- **检索**：sentence-transformers + bge-large-zh-v1.5（中文语义）/ TF-IDF 兜底
- **向量库**：FAISS（IndexFlatIP，内积 = 余弦相似度）
- **生成**：OpenAI 兼容协议 LLM（Ollama 本地 / DeepSeek / 其他）
- **服务**：FastAPI + Uvicorn
- **前端**：纯原生 JS 浮窗 SDK，无框架依赖

## 文档导航

| 想做什么 | 看哪份 |
|----------|--------|
| 把项目跑起来 | 本 README + `docs/DEPLOY.md` |
| 搞懂系统架构 | `docs/ARCHITECTURE.md` |
| 改代码、加功能 | `docs/DEVELOP.md` |
| 对接前端、调接口 | `docs/API.md` |
| 部署上线、运维 | `docs/DEPLOY.md` |
| 安装/环境报错 | `TROUBLESHOOTING.md` |

## 关键指标（实测）

- bge 语义检索 vs TF-IDF：相似度从全 1.000 提升到 0.74 区分度
- RTX 3060 GPU 加速 embedding：1010 queries/s
- LLM 离线时 /ask 优雅降级返回提示，不中断检索
