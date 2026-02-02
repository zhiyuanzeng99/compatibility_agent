"""
ClaudeBot Integrator - ClaudeBot (Anthropic Claude) 集成插件

专为 ClaudeBot 设计的多层安全防护集成:
- 第一道防线: OpenGuardrails (内容安全)
- 第二道防线: LlamaFirewall (操作安全)

支持:
- 危险操作拦截
- 敏感信息脱敏
- 工具调用安全检查
- 审计日志
"""

import time
import re
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .base_integrator import (
    BaseIntegratorPlugin,
    IntegrationResult,
    IntegrationPoint,
    IntegratorConfig
)


class OperationAction(Enum):
    """操作动作"""
    ALLOW = "allow"
    BLOCK = "block"
    CONFIRM = "confirm"
    LOG = "log"


@dataclass
class DangerousOperationRule:
    """危险操作规则"""
    pattern: str
    action: OperationAction
    reason: str
    confirm_message: Optional[str] = None


@dataclass
class SensitiveDataRule:
    """敏感数据规则"""
    name: str
    pattern: str
    replacement: str


@dataclass
class RateLimitRule:
    """频率限制规则"""
    pattern: str
    limit_per_hour: int
    reason: str


@dataclass
class ClaudeBotConfig(IntegratorConfig):
    """ClaudeBot 集成配置"""
    # 危险操作规则
    dangerous_operations: List[DangerousOperationRule] = field(default_factory=list)
    # 敏感数据脱敏规则
    sensitive_data_rules: List[SensitiveDataRule] = field(default_factory=list)
    # 频率限制规则
    rate_limit_rules: List[RateLimitRule] = field(default_factory=list)
    # 审计配置
    audit_enabled: bool = True
    audit_log_tool_calls: bool = True
    audit_retention_days: int = 90
    # 确认配置
    confirmation_callback: Optional[Callable[[str], Awaitable[bool]]] = None


class ClaudeBotIntegrator(BaseIntegratorPlugin):
    """
    ClaudeBot 集成插件

    为基于 Claude 的 AI 助手提供全面的安全防护
    """

    NAME = "claudebot_integrator"
    VERSION = "1.0.0"
    DESCRIPTION = "ClaudeBot 专用集成，多层安全防护，危险操作拦截，敏感信息脱敏"
    AUTHOR = "GuardAdapter"
    FRAMEWORK_NAME = "claudebot"

    SUPPORTED_POINTS = [
        IntegrationPoint.PRE_PROMPT,
        IntegrationPoint.POST_TASK_SPLIT,
        IntegrationPoint.PRE_TOOL_CALL,
        IntegrationPoint.POST_RESULT,
    ]

    # 默认危险操作规则
    DEFAULT_DANGEROUS_OPS = [
        DangerousOperationRule(
            pattern=r"delete_\w*",
            action=OperationAction.BLOCK,
            reason="删除操作默认禁止"
        ),
        DangerousOperationRule(
            pattern=r"send_email_bulk",
            action=OperationAction.BLOCK,
            reason="批量发送邮件禁止"
        ),
        DangerousOperationRule(
            pattern=r"delete_email",
            action=OperationAction.CONFIRM,
            reason="删除邮件需要确认",
            confirm_message="确认要删除邮件 {email_id} 吗？"
        ),
        DangerousOperationRule(
            pattern=r"send_email",
            action=OperationAction.CONFIRM,
            reason="发送邮件需要确认",
            confirm_message="确认发送邮件给 {recipient} 吗？"
        ),
    ]

    # 默认敏感数据脱敏规则
    DEFAULT_SENSITIVE_RULES = [
        SensitiveDataRule(
            name="email",
            pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            replacement="[邮箱已隐藏]"
        ),
        SensitiveDataRule(
            name="phone_cn",
            pattern=r"\b1[3-9]\d{9}\b",
            replacement="[手机号已隐藏]"
        ),
        SensitiveDataRule(
            name="id_card",
            pattern=r"\b\d{17}[\dXx]\b",
            replacement="[身份证已隐藏]"
        ),
        SensitiveDataRule(
            name="credit_card",
            pattern=r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
            replacement="[银行卡已隐藏]"
        ),
    ]

    # 默认频率限制规则
    DEFAULT_RATE_LIMITS = [
        RateLimitRule(
            pattern=r"send_\w*",
            limit_per_hour=10,
            reason="发送操作频率限制"
        ),
    ]

    def __init__(self, config: Optional[ClaudeBotConfig] = None):
        super().__init__(config)
        self.cb_config = config or ClaudeBotConfig(
            name=self.NAME,
            version=self.VERSION
        )

        # 设置默认规则
        if not self.cb_config.dangerous_operations:
            self.cb_config.dangerous_operations = self.DEFAULT_DANGEROUS_OPS
        if not self.cb_config.sensitive_data_rules:
            self.cb_config.sensitive_data_rules = self.DEFAULT_SENSITIVE_RULES
        if not self.cb_config.rate_limit_rules:
            self.cb_config.rate_limit_rules = self.DEFAULT_RATE_LIMITS

        # 操作计数器
        self._operation_counts: Dict[str, List[datetime]] = {}
        # 审计日志
        self._audit_logs: List[Dict] = []

    async def initialize(self) -> bool:
        """初始化"""
        return True

    async def shutdown(self) -> None:
        """关闭"""
        self._operation_counts.clear()

    async def intercept(
        self,
        point: IntegrationPoint,
        data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> IntegrationResult:
        """拦截并处理数据"""
        start_time = time.perf_counter()

        # 运行安全检查
        safety_result = await self.run_safety_checks(point, data, context)

        if not safety_result.get("is_safe", True):
            await self._log_audit("safety_block", point, data, safety_result)
            return IntegrationResult(
                success=True,
                point=point,
                blocked=True,
                block_reason=safety_result.get("reason"),
                latency_ms=(time.perf_counter() - start_time) * 1000
            )

        # 根据集成点处理
        modified_data = data

        if point == IntegrationPoint.PRE_PROMPT:
            # 输入检查（Prompt注入等）
            pass

        elif point == IntegrationPoint.PRE_TOOL_CALL:
            # 工具调用检查
            result = await self._check_tool_call(data, context)
            if result.blocked:
                return result

        elif point == IntegrationPoint.POST_RESULT:
            # 输出脱敏
            modified_data = await self._mask_sensitive_data(data)

        return IntegrationResult(
            success=True,
            point=point,
            modified_data=modified_data,
            latency_ms=(time.perf_counter() - start_time) * 1000
        )

    async def _check_tool_call(
        self,
        data: Any,
        context: Optional[Dict[str, Any]]
    ) -> IntegrationResult:
        """检查工具调用"""
        tool_name = data.get("tool_name", "") if isinstance(data, dict) else str(data)
        tool_args = data.get("args", {}) if isinstance(data, dict) else {}

        # 检查危险操作
        for rule in self.cb_config.dangerous_operations:
            if re.match(rule.pattern, tool_name, re.IGNORECASE):
                if rule.action == OperationAction.BLOCK:
                    await self._log_audit("blocked", IntegrationPoint.PRE_TOOL_CALL, data, {
                        "rule": rule.pattern,
                        "reason": rule.reason
                    })
                    return IntegrationResult(
                        success=True,
                        point=IntegrationPoint.PRE_TOOL_CALL,
                        blocked=True,
                        block_reason=rule.reason
                    )

                elif rule.action == OperationAction.CONFIRM:
                    # 需要用户确认
                    if self.cb_config.confirmation_callback:
                        message = rule.confirm_message or f"确认执行 {tool_name}？"
                        # 替换占位符
                        for key, value in tool_args.items():
                            message = message.replace(f"{{{key}}}", str(value))

                        confirmed = await self.cb_config.confirmation_callback(message)
                        if not confirmed:
                            return IntegrationResult(
                                success=True,
                                point=IntegrationPoint.PRE_TOOL_CALL,
                                blocked=True,
                                block_reason="用户取消操作"
                            )
                    else:
                        # 没有确认回调，默认阻止
                        return IntegrationResult(
                            success=True,
                            point=IntegrationPoint.PRE_TOOL_CALL,
                            blocked=True,
                            block_reason=f"{rule.reason}（需要确认但无确认机制）",
                            metadata={"requires_confirmation": True}
                        )

        # 检查频率限制
        rate_result = await self._check_rate_limit(tool_name)
        if rate_result:
            return rate_result

        # 记录审计日志
        if self.cb_config.audit_log_tool_calls:
            await self._log_audit("tool_call", IntegrationPoint.PRE_TOOL_CALL, data, {
                "tool_name": tool_name,
                "args": tool_args
            })

        return IntegrationResult(
            success=True,
            point=IntegrationPoint.PRE_TOOL_CALL,
            modified_data=data
        )

    async def _check_rate_limit(self, tool_name: str) -> Optional[IntegrationResult]:
        """检查频率限制"""
        now = datetime.now()

        for rule in self.cb_config.rate_limit_rules:
            if re.match(rule.pattern, tool_name, re.IGNORECASE):
                # 获取该模式的调用记录
                calls = self._operation_counts.get(rule.pattern, [])

                # 清理超过1小时的记录
                one_hour_ago = now.timestamp() - 3600
                calls = [c for c in calls if c.timestamp() > one_hour_ago]

                # 检查是否超过限制
                if len(calls) >= rule.limit_per_hour:
                    return IntegrationResult(
                        success=True,
                        point=IntegrationPoint.PRE_TOOL_CALL,
                        blocked=True,
                        block_reason=f"{rule.reason}（限制 {rule.limit_per_hour}/小时）"
                    )

                # 记录本次调用
                calls.append(now)
                self._operation_counts[rule.pattern] = calls

        return None

    async def _mask_sensitive_data(self, data: Any) -> Any:
        """脱敏敏感数据"""
        if isinstance(data, str):
            result = data
            for rule in self.cb_config.sensitive_data_rules:
                result = re.sub(rule.pattern, rule.replacement, result)
            return result

        elif isinstance(data, dict):
            return {
                key: await self._mask_sensitive_data(value)
                for key, value in data.items()
            }

        elif isinstance(data, list):
            return [await self._mask_sensitive_data(item) for item in data]

        return data

    async def _log_audit(
        self,
        action: str,
        point: IntegrationPoint,
        data: Any,
        details: Dict[str, Any]
    ) -> None:
        """记录审计日志"""
        if not self.cb_config.audit_enabled:
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "integration_point": point.value,
            "details": details
        }

        self._audit_logs.append(log_entry)

        # 保持日志数量在合理范围内
        if len(self._audit_logs) > 10000:
            self._audit_logs = self._audit_logs[-10000:]

    def get_audit_logs(self, limit: int = 100) -> List[Dict]:
        """获取审计日志"""
        return self._audit_logs[-limit:]

    def get_wrapper_code(self) -> str:
        """获取 ClaudeBot 包装器代码"""
        return '''
"""
GuardAdapter ClaudeBot Wrapper
专为 ClaudeBot 设计的安全防护包装器
"""

import anthropic
from typing import Any, Dict, List, Optional


class SafeClaudeBot:
    """带安全防护的 ClaudeBot"""

    def __init__(
        self,
        client: anthropic.Anthropic,
        safety_checker,
        confirmation_callback=None
    ):
        self.client = client
        self.safety_checker = safety_checker
        self.confirmation_callback = confirmation_callback

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict:
        """安全的聊天接口"""
        # 检查最后一条用户消息
        for msg in reversed(messages):
            if msg.get("role") == "user":
                result = await self.safety_checker.check_input(msg.get("content", ""))
                if not result.is_safe:
                    return {
                        "blocked": True,
                        "reason": result.reason
                    }
                break

        # 调用 Claude API
        response = self.client.messages.create(
            messages=messages,
            tools=tools,
            **kwargs
        )

        # 处理工具调用
        if response.stop_reason == "tool_use":
            for content in response.content:
                if content.type == "tool_use":
                    tool_result = await self._check_tool_call(
                        content.name,
                        content.input
                    )
                    if tool_result.get("blocked"):
                        return tool_result

        # 检查输出并脱敏
        output_text = ""
        for content in response.content:
            if content.type == "text":
                output_text += content.text

        # 输出安全检查
        output_result = await self.safety_checker.check_output(output_text)
        if not output_result.is_safe:
            return {
                "blocked": True,
                "reason": output_result.reason
            }

        # 脱敏输出
        masked_output = await self.safety_checker.mask_sensitive_data(output_text)

        return {
            "content": masked_output,
            "original_response": response
        }

    async def _check_tool_call(
        self,
        tool_name: str,
        tool_args: Dict
    ) -> Dict:
        """检查工具调用"""
        result = await self.safety_checker.check_tool_call(tool_name, tool_args)

        if not result.is_safe:
            if result.details.get("requires_confirmation"):
                if self.confirmation_callback:
                    confirmed = await self.confirmation_callback(result.reason)
                    if confirmed:
                        return {"blocked": False}
            return {
                "blocked": True,
                "reason": result.reason
            }

        return {"blocked": False}
'''

    def get_middleware_code(self) -> str:
        """获取中间件代码"""
        return '''
"""
GuardAdapter ClaudeBot Middleware
用于 ClaudeBot 服务的安全中间件
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse


def create_claudebot_middleware(app: FastAPI, safety_checker):
    """创建 ClaudeBot 安全中间件"""

    @app.middleware("http")
    async def safety_middleware(request: Request, call_next):
        if request.method == "POST" and "/chat" in request.url.path:
            try:
                body = await request.json()
                messages = body.get("messages", [])

                # 检查用户输入
                for msg in messages:
                    if msg.get("role") == "user":
                        result = await safety_checker.check_input(msg.get("content", ""))
                        if not result.is_safe:
                            return JSONResponse(
                                status_code=403,
                                content={
                                    "error": "safety_check_failed",
                                    "reason": result.reason
                                }
                            )
            except Exception:
                pass

        response = await call_next(request)
        return response

    return app
'''
