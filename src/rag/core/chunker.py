
"""文本分块。滑动窗口 + 段落粗切，保证语义连续、chunk 自包含。

多租户根：每个 chunk 都带 doc_id（客户/文档标识），从源到索引全链路隔离。
"""
from dataclasses import dataclass


@dataclass
class Chunk:
    content: str
    doc_id: str       # 来源文档标识 —— 多租户隔离的根本
    chunk_index: int
    doc_name: str = ""


class TextChunker:
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        if overlap >= chunk_size:
            raise ValueError("overlap 必须小于 chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str, doc_id: str, doc_name: str = "") -> list[Chunk]:
        if not text:
            return []
        blocks = [b.strip() for b in text.split("\n") if b.strip()]
        chunks: list[Chunk] = []
        for block in blocks:
            if len(block) <= self.chunk_size:
                chunks.append(Chunk(block, doc_id, len(chunks), doc_name))
                continue
            i = 0
            while i < len(block):
                end = i + self.chunk_size
                chunks.append(Chunk(block[i:end], doc_id, len(chunks), doc_name))
                i += self.chunk_size - self.overlap
        return chunks
