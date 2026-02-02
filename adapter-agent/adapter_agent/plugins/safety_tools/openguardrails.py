"""
OpenGuardrails Plugin - OpenGuardrails 安全工具插件

功能：
- 统一检测平台
- 支持119种语言
- 内容安全检测
- PII 检测
- 有害内容过滤
"""

import time
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .base_safety_tool import (
    BaseSafetyToolPlugin,
    SafetyCheckResult,
    CheckType,
    SafetyToolConfig
)


@dataclass
class OpenGuardrailsConfig(SafetyToolConfig):
    """OpenGuardrails 配置"""
    # 内容安全阈值
    toxicity_threshold: float = 0.7
    pii_detection_enabled: bool = True
    # 支持的语言
    languages: List[str] = field(default_factory=lambda: ["en", "zh"])
    # 自定义敏感词
    custom_blocked_words: List[str] = field(default_factory=list)


class OpenGuardrailsPlugin(BaseSafetyToolPlugin):
    """
    OpenGuardrails 插件

    统一检测平台，支持多语言内容安全检测
    """

    NAME = "openguardrails"
    VERSION = "1.0.0"
    DESCRIPTION = "OpenGuardrails - 统一检测平台，119语言支持"
    AUTHOR = "GuardAdapter"

    SUPPORTED_CHECKS = [
        CheckType.INPUT,
        CheckType.OUTPUT,
        CheckType.CONTENT,
        CheckType.PII,
        CheckType.TOXICITY,
        CheckType.PROMPT_INJECTION,
    ]

    # PII 正则模式
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone_cn": r"\b1[3-9]\d{9}\b",
        "phone_us": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "id_card_cn": r"\b\d{17}[\dXx]\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    }

    # Prompt 注入模式
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above)\s+(instructions|prompts)",
        r"disregard\s+(all\s+)?(previous|above)",
        r"forget\s+(everything|all)",
        r"you\s+are\s+now\s+",
        r"act\s+as\s+(if\s+you\s+are\s+)?",
        r"pretend\s+(to\s+be|you\s+are)",
        r"roleplay\s+as",
        r"jailbreak",
        r"DAN\s+mode",
    ]

    def __init__(self, config: Optional[OpenGuardrailsConfig] = None):
        super().__init__(config)
        self.og_config = config or OpenGuardrailsConfig(
            name=self.NAME,
            version=self.VERSION
        )
        self._client = None

    async def initialize(self) -> bool:
        """初始化 OpenGuardrails 客户端"""
        try:
            # 在实际实现中，这里会初始化 OpenGuardrails 客户端
            # from openguardrails import Client
            # self._client = Client(api_key=self.og_config.api_key)
            return True
        except Exception:
            return False

    async def shutdown(self) -> None:
        """关闭客户端"""
        self._client = None

    async def check_input(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查用户输入"""
        start_time = time.perf_counter()

        # 组合多种检查
        checks = [
            await self._check_toxicity(text),
            await self._check_prompt_injection(text),
            await self._check_blocked_words(text),
        ]

        # 如果任何检查失败，返回失败结果
        for check in checks:
            if not check.is_safe:
                check.latency_ms = (time.perf_counter() - start_time) * 1000
                return check

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

        # 检查输出的安全性
        checks = [
            await self._check_toxicity(text),
            await self._check_pii(text),
        ]

        for check in checks:
            if not check.is_safe:
                check.latency_ms = (time.perf_counter() - start_time) * 1000
                return check

        latency = (time.perf_counter() - start_time) * 1000
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.OUTPUT,
            latency_ms=latency,
            tool_name=self.NAME
        )

    async def _check_toxicity(self, text: str) -> SafetyCheckResult:
        """检查有害内容"""
        # 简化实现：基于关键词检测
        # 实际实现应该调用 OpenGuardrails API
        toxic_keywords = [
            "kill", "die", "hate", "violence", "attack",
            "杀", "死", "攻击", "暴力", "仇恨"
        ]

        text_lower = text.lower()
        for keyword in toxic_keywords:
            if keyword in text_lower:
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.TOXICITY,
                    confidence=0.8,
                    reason=f"检测到可能的有害内容关键词: {keyword}",
                    tool_name=self.NAME
                )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.TOXICITY,
            tool_name=self.NAME
        )

    async def _check_pii(self, text: str) -> SafetyCheckResult:
        """检查隐私信息"""
        if not self.og_config.pii_detection_enabled:
            return SafetyCheckResult(
                is_safe=True,
                check_type=CheckType.PII,
                tool_name=self.NAME
            )

        detected_pii = []
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                detected_pii.append({
                    "type": pii_type,
                    "count": len(matches)
                })

        if detected_pii:
            return SafetyCheckResult(
                is_safe=False,
                check_type=CheckType.PII,
                confidence=0.95,
                reason="检测到隐私信息",
                details={"detected_pii": detected_pii},
                tool_name=self.NAME
            )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.PII,
            tool_name=self.NAME
        )

    async def _check_prompt_injection(self, text: str) -> SafetyCheckResult:
        """检查 Prompt 注入"""
        text_lower = text.lower()

        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.PROMPT_INJECTION,
                    confidence=0.85,
                    reason="检测到可能的 Prompt 注入尝试",
                    details={"pattern_matched": pattern},
                    tool_name=self.NAME
                )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.PROMPT_INJECTION,
            tool_name=self.NAME
        )

    async def _check_blocked_words(self, text: str) -> SafetyCheckResult:
        """检查自定义敏感词"""
        text_lower = text.lower()

        for word in self.og_config.custom_blocked_words:
            if word.lower() in text_lower:
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.CONTENT,
                    confidence=1.0,
                    reason=f"检测到敏感词: {word}",
                    tool_name=self.NAME
                )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.CONTENT,
            tool_name=self.NAME
        )

    def mask_pii(self, text: str) -> str:
        """脱敏隐私信息"""
        result = text

        replacements = {
            "email": "[邮箱已隐藏]",
            "phone_cn": "[手机号已隐藏]",
            "phone_us": "[电话已隐藏]",
            "id_card_cn": "[身份证已隐藏]",
            "credit_card": "[信用卡已隐藏]",
            "ssn": "[SSN已隐藏]",
        }

        for pii_type, pattern in self.PII_PATTERNS.items():
            replacement = replacements.get(pii_type, "[已隐藏]")
            result = re.sub(pattern, replacement, result)

        return result
