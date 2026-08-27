# API 接口契约

服务地址默认 `http://localhost:8000`。FastAPI 自动生成交互文档：启动后访问 `/docs`（Swagger UI）可直接在线试调。

## 1. 智能问答

`POST /ask`

根据知识库文档生成带来源引用的回答。**核心接口**，前端浮窗 SDK 调的就是它。

请求体：
```json
{"question": "逆变器质保多久", "top_k": 5}
```
`top_k` 可选，指定检索命中条数，不传用 .env 的 TOP_K。

响应：
```json
{
  "question": "逆变器质保多久",
  "answer": "逆变器质保5年，可扩展至10年。[来源：资料1]",
  "sources": [
    {"doc": "光伏组件产品手册.txt", "score": 0.7548, "text": "逆变器质保 5 年，可扩展至 10 年。"}
  ]
}
```

- 知识库为空 → `answer="知识库为空，请先上传文档。"`, `sources=[]`
- LLM 离线 → `answer="（模型调用失败：...）"`, 但 `sources` 仍正常返回（检索不受 LLM 影响）

## 2. 纯检索

`POST /search`

只返回命中文本，不调用 LLM。适合前端做结果高亮、引用面板，或调试检索质量。

请求体：`{"question": "开路电压", "top_k": 5}`

响应：
```json
{
  "query": "开路电压",
  "results": [
    {"doc": "光伏组件产品手册.txt", "score": 0.6951, "text": "FH-M10-560 在 0℃ 时开路电压约 53.2V..."}
  ]
}
```

## 3. 上传单文档入库

`POST /ingest/file`

Multipart 表单，字段 `file`。返回新增 chunk 数。

```bash
curl -X POST http://127.0.0.1:8000/ingest/file -F "file=@产品手册.pdf"
# → {"chunks_added": 29}
```

支持格式：txt / md / csv / html / xml / pdf / docx / xlsx。

## 4. 批量入库目录

`POST /ingest/dir`

表单字段 `path` = 服务器本机路径，递归扫描所有支持格式的文档入库。

```bash
curl -X POST http://127.0.0.1:8000/ingest/dir -F "path=C:\yoyac-work\RAG\data"
# → {"chunks_added": 29}
```

> 注意：`path` 是 RAG 服务所在机器上的路径，不是客户端路径。

## 5. 知识库状态

`GET /info`

```json
{"doc_id": "tenant_001", "chunks": 29, "model": "BAAI/bge-large-zh-v1.5", "llm": "qwen2.5:7b"}
```

## 6. 清空知识库

`DELETE /clear` → `{"status": "cleared"}`

## 字段说明

| 字段 | 含义 |
|------|------|
| doc | 来源文档名 |
| score | 相似度（semantic 模式下 0~1，越高越相关）|
| text | 命中的文档片段原文 |
| answer | LLM 生成的自然语言回答 |
| sources | 该回答依据的资料列表 |
