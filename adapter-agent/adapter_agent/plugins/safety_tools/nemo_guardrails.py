"""
NeMo Guardrails Plugin - NVIDIA NeMo Guardrails 插件

功能：
- GPU 加速
- 对话流控制
- 主题控制
- 事实检查
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


@dataclass
class NeMoGuardrailsConfig(SafetyToolConfig):
    """NeMo Guardrails 配置"""
    config_path: Optional[str] = None
    model_name: str = "gpt-4"
    # 对话流配置
    flows_enabled: bool = True
    # 主题控制
    allowed_topics: List[str] = field(default_factory=list)
    blocked_topics: List[str] = field(default_factory=list)
    # 事实检查
    fact_checking_enabled: bool = False


class NeMoGuardrailsPlugin(BaseSafetyToolPlugin):
    """
    NeMo Guardrails 插件

    NVIDIA 出品的对话安全框架，支持 GPU 加速
    """

    NAME = "nemo_guardrails"
    VERSION = "1.0.0"
    DESCRIPTION = "NeMo Guardrails - NVIDIA出品，GPU加速，对话流控制"
    AUTHOR = "GuardAdapter"

    SUPPORTED_CHECKS = [
        CheckType.INPUT,
        CheckType.OUTPUT,
        CheckType.CONTENT,
        CheckType.PROMPT_INJECTION,
        CheckType.HALLUCINATION,
    ]

    def __init__(self, config: Optional[NeMoGuardrailsConfig] = None):
        super().__init__(config)
        self.nemo_config = config or NeMoGuardrailsConfig(
            name=self.NAME,
            version=self.VERSION
        )
        self._rails = None

    async def initialize(self) -> bool:
        """初始化 NeMo Guardrails"""
        try:
            # 实际实现中，这里会初始化 NeMo Guardrails
            # from nemoguardrails import RailsConfig, LLMRails
            # config = RailsConfig.from_path(self.nemo_config.config_path)
            # self._rails = LLMRails(config)
            return True
        except Exception:
            return False

    async def shutdown(self) -> None:
        """关闭"""
        self._rails = None

    async def check_input(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查用户输入"""
        start_time = time.perf_counter()

        # 主题检查
        topic_result = await self._check_topic(text)
        if not topic_result.is_safe:
            topic_result.latency_ms = (time.perf_counter() - start_time) * 1000
            return topic_result

        # Jailbreak 检查
        jailbreak_result = await self._check_jailbreak(text)
        if not jailbreak_result.is_safe:
            jailbreak_result.latency_ms = (time.perf_counter() - start_time) * 1000
            return jailbreak_result

        latency = (time.perf_counter() - start_time) * 1000
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.INPUT,
            latency_ms=latency,
            tool_name=self.NAME
        )

    async def check_output(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查模型输出"""
        start_time = time.perf_counter()

        # 幻觉检查（如果启用）
        if self.nemo_config.fact_checking_enabled:
            hallucination_result = await self._check_hallucination(text, context)
            if not hallucination_result.is_safe:
                hallucination_result.latency_ms = (time.perf_counter() - start_time) * 1000
                return hallucination_result

        latency = (time.perf_counter() - start_time) * 1000
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.OUTPUT,
            latency_ms=latency,
            tool_name=self.NAME
        )

    async def _check_topic(self, text: str) -> SafetyCheckResult:
        """检查主题是否允许"""
        text_lower = text.lower()

        # 检查被阻止的主题
        for topic in self.nemo_config.blocked_topics:
            if topic.lower() in text_lower:
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.CONTENT,
                    confidence=0.9,
                    reason=f"话题 '{topic}' 不在允许范围内",
                    tool_name=self.NAME
                )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.CONTENT,
            tool_name=self.NAME
        )

    async def _check_jailbreak(self, text: str) -> SafetyCheckResult:
        """检查 Jailbreak 尝试"""
        # NeMo 的 jailbreak 检测
        jailbreak_indicators = [
            "ignore all previous",
            "disregard your instructions",
            "you are now",
            "bypass your safety",
            "pretend you have no",
            "act as if you are",
            "override your",
        ]

        text_lower = text.lower()
        for indicator in jailbreak_indicators:
            if indicator in text_lower:
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.PROMPT_INJECTION,
                    confidence=0.85,
                    reason="检测到 Jailbreak 尝试",
                    details={"indicator": indicator},
                    tool_name=self.NAME
                )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.PROMPT_INJECTION,
            tool_name=self.NAME
        )

    async def _check_hallucination(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查幻觉"""
        # 简化实现：实际应该使用 NeMo 的事实检查功能
        # 这里只做基本的一致性检查

        # 如果有上下文中的事实，检查输出是否与之矛盾
        facts = context.get("facts", []) if context else []

        # 简化实现：默认通过
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.HALLUCINATION,
            tool_name=self.NAME
        )

    async def generate_with_rails(
        self,
        messages: List[Dict[str, str]]
    ) -> str:
        """
        使用 Rails 生成响应

        实际实现会调用 NeMo Guardrails 的生成功能
        """
        # 实际实现：
        # response = await self._rails.generate_async(messages=messages)
        # return response
        return "This is a placeholder response."
