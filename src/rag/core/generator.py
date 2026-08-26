
"""LLM 回答生成。统一走 OpenAI 兼容协议——Ollama / DeepSeek / 本地服务
换模型只需改 .env 里的 LLM_BASE_URL / LLM_MODEL，代码零改动。
"""
import os
from openai import OpenAI

from .config import Config


_RAG_SYSTEM = (
    "你是一个专业的企业知识问答助手。请严格根据下方【参考资料】回答用户问题。"
    "回答要求：\n"
    "1. 只依据参考资料回答，不要编造资料中没有的信息。\n"
    "2. 如果参考资料不足以回答问题，请直接说'现有资料无法回答该问题'，不要猜测。\n"
    "3. 回答要简洁、准确、条理清晰，引用关键数字或专有名词时保持原样。\n"
    "4. 在回答末尾用一行注明引用的资料编号，如 [来源：资料1, 资料3]。\n\n"
    "【参考资料】\n{context}\n"
)


class Generator:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.client = OpenAI(
            base_url=self.cfg.LLM_BASE_URL,
            api_key=self.cfg.LLM_API_KEY,
            timeout=self.cfg.LLM_TIMEOUT,
        )

    def answer(self, question: str, context: str) -> str:
        """context 是从向量库检索到的资料拼接文本。"""
        system = _RAG_SYSTEM.format(context=context)
        try:
            resp = self.client.chat.completions.create(
                model=self.cfg.LLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": question},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content or "（模型未返回有效回答）"
        except Exception as e:
            return f"（模型调用失败：{e}。请确认 Ollama/LLM 服务已启动且模型已下载。）"

    def _build_context(self, hits) -> str:
        """把检索命中的 chunk 拼成带编号的参考资料文本。"""
        lines = []
        for n, (chunk, score) in enumerate(hits, 1):
            lines.append(f"--- 资料{n}（相似度 {score:.3f}，来源：{chunk.doc_name}）---\n{chunk.content}")
        return "\n\n".join(lines)
