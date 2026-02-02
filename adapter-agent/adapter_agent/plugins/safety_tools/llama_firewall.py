"""
LlamaFirewall Plugin - Meta LlamaFirewall 插件

功能：
- Agent 安全
- 工具调用安全
- 权限边界检查
- Prompt 注入防护
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
class DangerousOperation:
    """危险操作定义"""
    pattern: str
    description: str
    action: str  # "block", "confirm", "log"
    message: Optional[str] = None


@dataclass
class LlamaFirewallConfig(SafetyToolConfig):
    """LlamaFirewall 配置"""
    # 危险操作规则
    dangerous_operations: List[DangerousOperation] = field(default_factory=list)
    # 频率限制
    rate_limits: Dict[str, int] = field(default_factory=dict)  # pattern: limit_per_hour
    # 权限配置
    allowed_tools: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)


class LlamaFirewallPlugin(BaseSafetyToolPlugin):
    """
    LlamaFirewall 插件

    Meta 出品的 Agent 安全防护框架
    """

    NAME = "llama_firewall"
    VERSION = "1.0.0"
    DESCRIPTION = "LlamaFirewall - Meta出品，Agent安全，工具调用安全"
    AUTHOR = "GuardAdapter"

    SUPPORTED_CHECKS = [
        CheckType.INPUT,
        CheckType.OUTPUT,
        CheckType.TOOL_CALL,
        CheckType.PROMPT_INJECTION,
    ]

    # 默认危险操作
    DEFAULT_DANGEROUS_OPS = [
        DangerousOperation(
            pattern=r"delete_\w+",
            description="删除操作",
            action="confirm",
            message="确认要执行删除操作吗？"
        ),
        DangerousOperation(
            pattern=r"send_email(_bulk)?",
            description="发送邮件",
            action="confirm",
            message="确认要发送邮件吗？"
        ),
        DangerousOperation(
            pattern=r"execute_\w+",
            description="执行操作",
            action="confirm",
            message="确认要执行此操作吗？"
        ),
        DangerousOperation(
            pattern=r"rm\s+-rf",
            description="强制删除",
            action="block",
            message="此操作已被禁止"
        ),
        DangerousOperation(
            pattern=r"DROP\s+TABLE",
            description="删除数据表",
            action="block",
            message="此操作已被禁止"
        ),
    ]

    def __init__(self, config: Optional[LlamaFirewallConfig] = None):
        super().__init__(config)
        self.fw_config = config or LlamaFirewallConfig(
            name=self.NAME,
            version=self.VERSION
        )
        # 合并默认危险操作
        if not self.fw_config.dangerous_operations:
            self.fw_config.dangerous_operations = self.DEFAULT_DANGEROUS_OPS

        # 操作计数器（用于频率限制）
        self._operation_counts: Dict[str, int] = {}

    async def initialize(self) -> bool:
        """初始化"""
        return True

    async def shutdown(self) -> None:
        """关闭"""
        self._operation_counts.clear()

    async def check_input(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查用户输入"""
        start_time = time.perf_counter()

        # Prompt 注入检查
        injection_result = await self._check_prompt_injection(text)
        if not injection_result.is_safe:
            injection_result.latency_ms = (time.perf_counter() - start_time) * 1000
            return injection_result

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

        # 检查输出中是否包含敏感信息泄露
        sensitive_patterns = [
            r"password\s*[:=]\s*\S+",
            r"api[_-]?key\s*[:=]\s*\S+",
            r"secret\s*[:=]\s*\S+",
        ]

        for pattern in sensitive_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.OUTPUT,
                    confidence=0.9,
                    reason="输出中可能包含敏感凭证信息",
                    latency_ms=(time.perf_counter() - start_time) * 1000,
                    tool_name=self.NAME
                )

        latency = (time.perf_counter() - start_time) * 1000
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.OUTPUT,
            latency_ms=latency,
            tool_name=self.NAME
        )

    async def check_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """
        检查工具调用安全性

        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            context: 上下文

        Returns:
            安全检查结果
        """
        start_time = time.perf_counter()

        # 检查工具是否被禁止
        if tool_name in self.fw_config.blocked_tools:
            return SafetyCheckResult(
                is_safe=False,
                check_type=CheckType.TOOL_CALL,
                confidence=1.0,
                reason=f"工具 '{tool_name}' 已被禁止使用",
                latency_ms=(time.perf_counter() - start_time) * 1000,
                tool_name=self.NAME
            )

        # 如果配置了允许列表，检查是否在列表中
        if self.fw_config.allowed_tools and tool_name not in self.fw_config.allowed_tools:
            return SafetyCheckResult(
                is_safe=False,
                check_type=CheckType.TOOL_CALL,
                confidence=1.0,
                reason=f"工具 '{tool_name}' 不在允许列表中",
                latency_ms=(time.perf_counter() - start_time) * 1000,
                tool_name=self.NAME
            )

        # 检查危险操作
        for op in self.fw_config.dangerous_operations:
            if re.match(op.pattern, tool_name, re.IGNORECASE):
                if op.action == "block":
                    return SafetyCheckResult(
                        is_safe=False,
                        check_type=CheckType.TOOL_CALL,
                        confidence=1.0,
                        reason=op.message or f"操作 '{tool_name}' 已被禁止",
                        details={"operation": op.description, "action": op.action},
                        latency_ms=(time.perf_counter() - start_time) * 1000,
                        tool_name=self.NAME
                    )
                elif op.action == "confirm":
                    return SafetyCheckResult(
                        is_safe=False,
                        check_type=CheckType.TOOL_CALL,
                        confidence=0.8,
                        reason=op.message or f"操作 '{tool_name}' 需要确认",
                        details={
                            "operation": op.description,
                            "action": op.action,
                            "requires_confirmation": True
                        },
                        latency_ms=(time.perf_counter() - start_time) * 1000,
                        tool_name=self.NAME
                    )

        # 检查频率限制
        rate_limit_result = await self._check_rate_limit(tool_name)
        if not rate_limit_result.is_safe:
            rate_limit_result.latency_ms = (time.perf_counter() - start_time) * 1000
            return rate_limit_result

        # 检查参数安全性
        params_result = await self._check_tool_params(tool_name, tool_args)
        if not params_result.is_safe:
            params_result.latency_ms = (time.perf_counter() - start_time) * 1000
            return params_result

        latency = (time.perf_counter() - start_time) * 1000
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.TOOL_CALL,
            latency_ms=latency,
            tool_name=self.NAME
        )

    async def _check_prompt_injection(self, text: str) -> SafetyCheckResult:
        """检查 Prompt 注入"""
        # 高级 Prompt 注入检测模式
        injection_patterns = [
            # 系统指令覆盖
            r"system\s*:\s*",
            r"<\|im_start\|>system",
            r"\[INST\]",
            # 角色切换
            r"you\s+are\s+(now\s+)?(?:a|an)\s+",
            r"from\s+now\s+on",
            r"new\s+instructions?\s*:",
            # 指令忽略
            r"ignore\s+(all\s+)?(previous|prior|above)",
            r"disregard\s+(everything|all)",
            r"forget\s+(all|everything)",
            # 越狱尝试
            r"jailbreak",
            r"DAN\s+mode",
            r"developer\s+mode",
            r"unrestricted\s+mode",
        ]

        text_to_check = text.lower()

        for pattern in injection_patterns:
            if re.search(pattern, text_to_check, re.IGNORECASE):
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.PROMPT_INJECTION,
                    confidence=0.9,
                    reason="检测到可能的 Prompt 注入攻击",
                    details={"matched_pattern": pattern},
                    tool_name=self.NAME
                )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.PROMPT_INJECTION,
            tool_name=self.NAME
        )

    async def _check_rate_limit(self, tool_name: str) -> SafetyCheckResult:
        """检查频率限制"""
        # 查找匹配的限制规则
        for pattern, limit in self.fw_config.rate_limits.items():
            if re.match(pattern, tool_name, re.IGNORECASE):
                current_count = self._operation_counts.get(pattern, 0)
                if current_count >= limit:
                    return SafetyCheckResult(
                        is_safe=False,
                        check_type=CheckType.TOOL_CALL,
                        confidence=1.0,
                        reason=f"操作 '{tool_name}' 已达到频率限制 ({limit}/小时)",
                        details={"current_count": current_count, "limit": limit},
                        tool_name=self.NAME
                    )
                self._operation_counts[pattern] = current_count + 1

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.TOOL_CALL,
            tool_name=self.NAME
        )

    async def _check_tool_params(
        self,
        tool_name: str,
        tool_args: Dict[str, Any]
    ) -> SafetyCheckResult:
        """检查工具参数安全性"""
        # 检查参数中是否包含注入攻击
        dangerous_patterns = [
            r";\s*(?:rm|del|drop|truncate)",
            r"\|\s*(?:rm|del|cat|nc)",
            r"`[^`]+`",
            r"\$\([^)]+\)",
        ]

        args_str = str(tool_args).lower()

        for pattern in dangerous_patterns:
            if re.search(pattern, args_str, re.IGNORECASE):
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.TOOL_CALL,
                    confidence=0.85,
                    reason="工具参数中检测到可能的注入攻击",
                    details={"pattern": pattern},
                    tool_name=self.NAME
                )

        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.TOOL_CALL,
            tool_name=self.NAME
        )
