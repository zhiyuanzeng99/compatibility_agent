"""
Data Collector - 数据采集与处理

负责从各种来源收集和处理训练数据
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import json
import hashlib


class DataSourceType(Enum):
    """数据源类型"""
    GITHUB_DOCS = "github_docs"
    GITHUB_ISSUES = "github_issues"
    GITHUB_CODE = "github_code"
    OFFICIAL_DOCS = "official_docs"
    STACK_OVERFLOW = "stack_overflow"
    ARXIV = "arxiv"
    CUSTOM = "custom"


@dataclass
class DataSource:
    """数据源配置"""
    name: str
    source_type: DataSourceType
    url: Optional[str] = None
    api_key: Optional[str] = None
    update_frequency: str = "daily"
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RawDataItem:
    """原始数据项"""
    id: str
    source: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    collected_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessedDataItem:
    """处理后的数据项"""
    id: str
    source: str
    input_text: str
    output_text: str
    task_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_conversation_format(self) -> Dict:
        """转换为对话格式"""
        return {
            "conversations": [
                {"role": "user", "content": self.input_text},
                {"role": "assistant", "content": self.output_text}
            ],
            "metadata": self.metadata
        }


class DataCollector:
    """数据收集器"""

    SAFETY_TOOL_REPOS = {
        "openguardrails": "openguardrails/openguardrails",
        "nemo_guardrails": "NVIDIA/NeMo-Guardrails",
        "llama_firewall": "meta-llama/PurpleLlama",
        "guardrails_ai": "guardrails-ai/guardrails",
    }

    FRAMEWORK_REPOS = {
        "langchain": "langchain-ai/langchain",
        "llamaindex": "run-llama/llama_index",
        "haystack": "deepset-ai/haystack",
    }

    def __init__(self):
        self._sources: List[DataSource] = []
        self._collected_data: List[RawDataItem] = []

    def add_source(self, source: DataSource) -> None:
        self._sources.append(source)

    def add_default_sources(self) -> None:
        for tool_name, repo in self.SAFETY_TOOL_REPOS.items():
            self._sources.append(DataSource(
                name=f"{tool_name}_docs",
                source_type=DataSourceType.GITHUB_DOCS,
                url=f"https://github.com/{repo}"
            ))
            self._sources.append(DataSource(
                name=f"{tool_name}_issues",
                source_type=DataSourceType.GITHUB_ISSUES,
                url=f"https://api.github.com/repos/{repo}/issues"
            ))

    async def collect_all(self) -> List[RawDataItem]:
        all_items = []
        for source in self._sources:
            items = await self._collect_from_source(source)
            all_items.extend(items)
            self._collected_data.extend(items)
        return all_items

    async def _collect_from_source(self, source: DataSource) -> List[RawDataItem]:
        # 实际实现需要使用 GitHub API 等
        return []


class DataProcessor:
    """数据处理器"""

    def __init__(self):
        self._processed_data: List[ProcessedDataItem] = []

    def process_for_sft(self, raw_items: List[RawDataItem]) -> List[ProcessedDataItem]:
        processed = []
        for item in raw_items:
            processed_item = self._convert_to_sft(item)
            if processed_item:
                processed.append(processed_item)
        self._processed_data.extend(processed)
        return processed

    def _convert_to_sft(self, item: RawDataItem) -> Optional[ProcessedDataItem]:
        return None

    def export_to_jsonl(self, output_path: str) -> int:
        count = 0
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in self._processed_data:
                f.write(json.dumps(item.to_conversation_format(), ensure_ascii=False))
                f.write('\n')
                count += 1
        return count

    def deduplicate(self) -> int:
        seen = set()
        unique = []
        for item in self._processed_data:
            h = hashlib.md5((item.input_text + item.output_text).encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(item)
        removed = len(self._processed_data) - len(unique)
        self._processed_data = unique
        return removed

    def split_dataset(self, train_ratio: float = 0.9) -> tuple:
        import random
        data = self._processed_data.copy()
        random.shuffle(data)
        split_idx = int(len(data) * train_ratio)
        return data[:split_idx], data[split_idx:]
