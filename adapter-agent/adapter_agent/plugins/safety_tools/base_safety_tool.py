"""
Base Safety Tool Plugin - 安全工具插件基类

定义安全工具插件的通用接口
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from ..base import BasePlugin, PluginConfig


class CheckType(Enum):
    """检查类型"""
    INPUT = "input"              # 输入检查
    OUTPUT = "output"            # 输出检查
    TOOL_CALL = "tool_call"      # 工具调用检查
    CONTENT = "content"          # 内容安全检查
    PROMPT_INJECTION = "prompt_injection"  # Prompt注入检查
    PII = "pii"                  # 隐私信息检查
    TOXICITY = "toxicity"        # 有害内容检查
    HALLUCINATION = "hallucination"  # 幻觉检查


@dataclass
class SafetyCheckResult:
    """安全检查结果"""
    is_safe: bool
    check_type: CheckType
    confidence: float = 1.0
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0
    tool_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "is_safe": self.is_safe,
            "check_type": self.check_type.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "details": self.details,
            "latency_ms": self.latency_ms,
            "tool_name": self.tool_name
        }


@dataclass
class SafetyToolConfig(PluginConfig):
    """安全工具配置"""
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    model_path: Optional[str] = None
    timeout_seconds: float = 5.0
    max_retries: int = 3
    enabled_checks: List[CheckType] = field(default_factory=lambda: list(CheckType))


class BaseSafetyToolPlugin(BasePlugin):
    """
    安全工具插件基类

    所有安全工具插件必须继承此类
    """

    PLUGIN_TYPE = "safety_tool"

    # 支持的检查类型（子类覆盖）
    SUPPORTED_CHECKS: List[CheckType] = []

    def __init__(self, config: Optional[SafetyToolConfig] = None):
        super().__init__(config)
        self.tool_config = config or SafetyToolConfig(
            name=self.NAME,
            version=self.VERSION
        )

    @abstractmethod
    async def check_input(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """
        检查用户输入

        Args:
            text: 输入文本
            context: 上下文信息

        Returns:
            安全检查结果
        """
        pass

    @abstractmethod
    async def check_output(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """
        检查模型输出

        Args:
            text: 输出文本
            context: 上下文信息

        Returns:
            安全检查结果
        """
        pass

    async def check_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """
        检查工具调用

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            context: 上下文信息

        Returns:
            安全检查结果
        """
        # 默认实现：允许所有工具调用
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.TOOL_CALL,
            tool_name=self.NAME
        )

    async def check_content(
        self,
        text: str,
        check_types: Optional[List[CheckType]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> List[SafetyCheckResult]:
        """
        执行多种内容检查

        Args:
            text: 要检查的文本
            check_types: 要执行的检查类型（默认所有支持的类型）
            context: 上下文信息

        Returns:
            安全检查结果列表
        """
        check_types = check_types or self.SUPPORTED_CHECKS
        results = []

        for check_type in check_types:
            if check_type not in self.SUPPORTED_CHECKS:
                continue

            result = await self._execute_check(text, check_type, context)
            results.append(result)

        return results

    async def _execute_check(
        self,
        text: str,
        check_type: CheckType,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """执行单个检查"""
        # 默认实现，子类可以覆盖
        return SafetyCheckResult(
            is_safe=True,
            check_type=check_type,
            tool_name=self.NAME
        )

    def supports_check(self, check_type: CheckType) -> bool:
        """检查是否支持某种检查类型"""
        return check_type in self.SUPPORTED_CHECKS

    def get_supported_checks(self) -> List[CheckType]:
        """获取支持的检查类型"""
        return self.SUPPORTED_CHECKS.copy()
