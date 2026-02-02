"""
LlamaGuard Plugin - Meta LlamaGuard 插件

功能：
- 内容分类
- 安全评估
- 多轮对话安全检查
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .base_safety_tool import (
    BaseSafetyToolPlugin,
    SafetyCheckResult,
    CheckType,
    SafetyToolConfig
)


class SafetyCategory:
    """安全类别"""
    S1 = "S1"  # Violence and Hate
    S2 = "S2"  # Sexual Content
    S3 = "S3"  # Criminal Planning
    S4 = "S4"  # Guns and Illegal Weapons
    S5 = "S5"  # Regulated Substances
    S6 = "S6"  # Self-Harm
    S7 = "S7"  # Privacy
    S8 = "S8"  # Financial Crimes
    S9 = "S9"  # Intellectual Property
    S10 = "S10"  # Code Interpreter Abuse
    S11 = "S11"  # Defamation
    S12 = "S12"  # Elections
    S13 = "S13"  # Specialized Advice

    DESCRIPTIONS = {
        "S1": "暴力和仇恨",
        "S2": "色情内容",
        "S3": "犯罪策划",
        "S4": "枪支和非法武器",
        "S5": "管制物质",
        "S6": "自我伤害",
        "S7": "隐私侵犯",
        "S8": "金融犯罪",
        "S9": "知识产权侵犯",
        "S10": "代码解释器滥用",
        "S11": "诽谤",
        "S12": "选举相关",
        "S13": "专业建议（医疗/法律）"
    }


@dataclass
class LlamaGuardConfig(SafetyToolConfig):
    """LlamaGuard 配置"""
    model_id: str = "meta-llama/LlamaGuard-7b"
    device: str = "cuda"  # cuda / cpu
    # 启用的安全类别
    enabled_categories: List[str] = field(default_factory=lambda: [
        "S1", "S2", "S3", "S4", "S5", "S6"
    ])
    # 阈值
    unsafe_threshold: float = 0.5


class LlamaGuardPlugin(BaseSafetyToolPlugin):
    """
    LlamaGuard 插件

    Meta 出品的内容安全分类模型
    """

    NAME = "llama_guard"
    VERSION = "1.0.0"
    DESCRIPTION = "LlamaGuard - Meta出品，内容安全分类"
    AUTHOR = "GuardAdapter"

    SUPPORTED_CHECKS = [
        CheckType.INPUT,
        CheckType.OUTPUT,
        CheckType.CONTENT,
        CheckType.TOXICITY,
    ]

    def __init__(self, config: Optional[LlamaGuardConfig] = None):
        super().__init__(config)
        self.guard_config = config or LlamaGuardConfig(
            name=self.NAME,
            version=self.VERSION
        )
        self._model = None
        self._tokenizer = None

    async def initialize(self) -> bool:
        """初始化 LlamaGuard 模型"""
        try:
            # 实际实现中，这里会加载模型
            # from transformers import AutoModelForCausalLM, AutoTokenizer
            # self._tokenizer = AutoTokenizer.from_pretrained(self.guard_config.model_id)
            # self._model = AutoModelForCausalLM.from_pretrained(
            #     self.guard_config.model_id,
            #     device_map=self.guard_config.device
            # )
            return True
        except Exception:
            return False

    async def shutdown(self) -> None:
        """释放模型资源"""
        self._model = None
        self._tokenizer = None

    async def check_input(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查用户输入"""
        return await self._classify_content(text, "user")

    async def check_output(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查模型输出"""
        return await self._classify_content(text, "assistant")

    async def _classify_content(
        self,
        text: str,
        role: str
    ) -> SafetyCheckResult:
        """
        使用 LlamaGuard 分类内容

        Args:
            text: 要分类的文本
            role: 角色（user/assistant）

        Returns:
            安全检查结果
        """
        start_time = time.perf_counter()

        # 简化实现：基于规则的分类
        # 实际实现会调用 LlamaGuard 模型

        violated_categories = []

        # 检查各个安全类别
        category_patterns = {
            "S1": ["kill", "attack", "violence", "hate", "杀", "攻击", "暴力"],
            "S2": ["porn", "sex", "nude", "色情", "性"],
            "S3": ["how to hack", "steal", "fraud", "如何黑", "偷", "诈骗"],
            "S4": ["gun", "weapon", "bomb", "枪", "武器", "炸弹"],
            "S5": ["drug", "cocaine", "heroin", "毒品", "可卡因"],
            "S6": ["suicide", "self-harm", "自杀", "自残"],
        }

        text_lower = text.lower()
        for category, patterns in category_patterns.items():
            if category not in self.guard_config.enabled_categories:
                continue

            for pattern in patterns:
                if pattern in text_lower:
                    violated_categories.append(category)
                    break

        latency = (time.perf_counter() - start_time) * 1000

        if violated_categories:
            category_descriptions = [
                SafetyCategory.DESCRIPTIONS.get(c, c)
                for c in violated_categories
            ]
            return SafetyCheckResult(
                is_safe=False,
                check_type=CheckType.CONTENT,
                confidence=0.85,
                reason=f"内容违反安全类别: {', '.join(category_descriptions)}",
                details={
                    "violated_categories": violated_categories,
                    "role": role
                },
                latency_ms=latency,
                tool_name=self.NAME
            )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.CONTENT,
            latency_ms=latency,
            tool_name=self.NAME
        )

    async def check_conversation(
        self,
        messages: List[Dict[str, str]]
    ) -> SafetyCheckResult:
        """
        检查整个对话的安全性

        Args:
            messages: 对话消息列表 [{"role": "user/assistant", "content": "..."}]

        Returns:
            安全检查结果
        """
        start_time = time.perf_counter()

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            result = await self._classify_content(content, role)
            if not result.is_safe:
                result.latency_ms = (time.perf_counter() - start_time) * 1000
                return result

        latency = (time.perf_counter() - start_time) * 1000
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.CONTENT,
            latency_ms=latency,
            tool_name=self.NAME
        )
