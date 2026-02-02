"""
Training - 数据与训练体系

针对 4x RTX 4090 (4x24GB = 96GB VRAM) 优化的训练系统

支持:
- 数据采集与处理
- SFT 监督微调
- DPO 偏好对齐
- 工具使用训练
- RAG 知识库构建
"""

from .data_collector import DataCollector, DataSource, DataProcessor
from .sft_trainer import SFTTrainer, SFTConfig, get_recommended_config_for_4x4090
from .dpo_trainer import DPOTrainer, DPOConfig
from .tool_trainer import ToolUseTrainer, ToolTrainingConfig
from .rag_builder import RAGBuilder, RAGConfig
from .evaluator import Evaluator, EvaluationMetrics

__all__ = [
    "DataCollector",
    "DataSource",
    "DataProcessor",
    "SFTTrainer",
    "SFTConfig",
    "get_recommended_config_for_4x4090",
    "DPOTrainer",
    "DPOConfig",
    "ToolUseTrainer",
    "ToolTrainingConfig",
    "RAGBuilder",
    "RAGConfig",
    "Evaluator",
    "EvaluationMetrics",
]
