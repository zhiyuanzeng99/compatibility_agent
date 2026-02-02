"""
RAG Builder - 知识库构建

构建检索增强生成所需的知识库
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import hashlib


class IndexType(Enum):
    """索引类型"""
    DOCUMENTATION = "documentation"
    CODE_EXAMPLES = "code_examples"
    ISSUES_SOLUTIONS = "issues_solutions"
    COMPATIBILITY_MATRIX = "compatibility_matrix"


@dataclass
class DocumentChunk:
    """文档块"""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class RAGConfig:
    """RAG 配置"""
    vector_db: str = "chromadb"
    collection_name: str = "guaradapter_knowledge"
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_dimension: int = 1024
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5
    similarity_threshold: float = 0.7


class TextSplitter:
    """文本分割器"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            # 尝试在句子边界分割
            if end < len(text):
                for sep in ['\n\n', '\n', '。', '.']:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + len(sep)
                        break
            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap
        return [c for c in chunks if c]


class RAGBuilder:
    """RAG 知识库构建器"""

    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self._splitter = TextSplitter(self.config.chunk_size, self.config.chunk_overlap)
        self._chunks: List[DocumentChunk] = []

    def add_documents(
        self,
        documents: List[str],
        index_type: IndexType,
        metadata: Optional[List[Dict]] = None
    ) -> int:
        """添加文档"""
        count = 0
        for i, doc in enumerate(documents):
            doc_meta = metadata[i] if metadata and i < len(metadata) else {}
            for j, chunk in enumerate(self._splitter.split(doc)):
                chunk_id = hashlib.md5(chunk.encode()).hexdigest()
                self._chunks.append(DocumentChunk(
                    id=chunk_id,
                    content=chunk,
                    metadata={**doc_meta, "index_type": index_type.value, "chunk_idx": j}
                ))
                count += 1
        return count

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[DocumentChunk]:
        """检索（需要实际向量数据库实现）"""
        return self._chunks[:top_k or self.config.top_k]

    def get_context_for_query(self, query: str) -> str:
        """获取查询上下文"""
        chunks = self.retrieve(query)
        return "\n\n---\n\n".join(c.content for c in chunks)

    def get_statistics(self) -> Dict:
        return {"total_chunks": len(self._chunks)}
