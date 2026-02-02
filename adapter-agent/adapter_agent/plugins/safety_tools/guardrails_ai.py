"""
Guardrails AI Plugin - Guardrails AI 插件

功能：
- RAIL 规范
- 输出验证
- 结构化输出保证
- 自动重试
"""

import time
import json
from typing import Optional, Dict, Any, List, Type
from dataclasses import dataclass, field

from .base_safety_tool import (
    BaseSafetyToolPlugin,
    SafetyCheckResult,
    CheckType,
    SafetyToolConfig
)


@dataclass
class OutputValidator:
    """输出验证器"""
    name: str
    description: str
    validator_type: str  # "regex", "json_schema", "custom"
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardrailsAIConfig(SafetyToolConfig):
    """Guardrails AI 配置"""
    # 输出验证器
    validators: List[OutputValidator] = field(default_factory=list)
    # 自动重试
    auto_retry: bool = True
    max_retries: int = 3
    # JSON Schema 验证
    output_schema: Optional[Dict] = None


class GuardrailsAIPlugin(BaseSafetyToolPlugin):
    """
    Guardrails AI 插件

    提供结构化输出验证和保证
    """

    NAME = "guardrails_ai"
    VERSION = "1.0.0"
    DESCRIPTION = "Guardrails AI - RAIL规范，输出验证，结构化输出保证"
    AUTHOR = "GuardAdapter"

    SUPPORTED_CHECKS = [
        CheckType.OUTPUT,
        CheckType.CONTENT,
    ]

    def __init__(self, config: Optional[GuardrailsAIConfig] = None):
        super().__init__(config)
        self.gai_config = config or GuardrailsAIConfig(
            name=self.NAME,
            version=self.VERSION
        )
        self._guard = None

    async def initialize(self) -> bool:
        """初始化 Guardrails AI"""
        try:
            # 实际实现中，这里会初始化 Guardrails AI
            # from guardrails import Guard
            # self._guard = Guard()
            return True
        except Exception:
            return False

    async def shutdown(self) -> None:
        """关闭"""
        self._guard = None

    async def check_input(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查输入（Guardrails AI 主要用于输出验证）"""
        return SafetyCheckResult(
            is_safe=True,
            check_type=CheckType.INPUT,
            tool_name=self.NAME
        )

    async def check_output(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """检查模型输出"""
        start_time = time.perf_counter()

        # 运行所有验证器
        validation_results = []

        for validator in self.gai_config.validators:
            result = await self._run_validator(validator, text)
            validation_results.append(result)

            if not result["passed"]:
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.OUTPUT,
                    confidence=0.95,
                    reason=result["reason"],
                    details={"validator": validator.name, "results": validation_results},
                    latency_ms=(time.perf_counter() - start_time) * 1000,
                    tool_name=self.NAME
                )

        # 如果有 JSON Schema，验证输出格式
        if self.gai_config.output_schema:
            schema_result = await self._validate_json_schema(text)
            if not schema_result["passed"]:
                return SafetyCheckResult(
                    is_safe=False,
                    check_type=CheckType.OUTPUT,
                    confidence=0.95,
                    reason=schema_result["reason"],
                    details={"schema_validation": schema_result},
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

    async def _run_validator(
        self,
        validator: OutputValidator,
        text: str
    ) -> Dict[str, Any]:
        """运行单个验证器"""
        if validator.validator_type == "regex":
            import re
            pattern = validator.config.get("pattern", "")
            match = re.search(pattern, text)
            should_match = validator.config.get("should_match", True)

            if should_match and not match:
                return {
                    "passed": False,
                    "reason": f"输出不匹配预期模式: {validator.description}"
                }
            elif not should_match and match:
                return {
                    "passed": False,
                    "reason": f"输出包含禁止的模式: {validator.description}"
                }

        elif validator.validator_type == "length":
            min_length = validator.config.get("min", 0)
            max_length = validator.config.get("max", float("inf"))

            if len(text) < min_length:
                return {
                    "passed": False,
                    "reason": f"输出长度过短（最少 {min_length} 字符）"
                }
            if len(text) > max_length:
                return {
                    "passed": False,
                    "reason": f"输出长度过长（最多 {max_length} 字符）"
                }

        elif validator.validator_type == "contains":
            required = validator.config.get("required", [])
            forbidden = validator.config.get("forbidden", [])

            for req in required:
                if req.lower() not in text.lower():
                    return {
                        "passed": False,
                        "reason": f"输出缺少必需内容: {req}"
                    }

            for forb in forbidden:
                if forb.lower() in text.lower():
                    return {
                        "passed": False,
                        "reason": f"输出包含禁止内容: {forb}"
                    }

        return {"passed": True, "reason": None}

    async def _validate_json_schema(self, text: str) -> Dict[str, Any]:
        """验证 JSON Schema"""
        try:
            # 尝试解析 JSON
            data = json.loads(text)

            # 使用 jsonschema 验证（简化实现）
            schema = self.gai_config.output_schema

            # 检查必需字段
            required = schema.get("required", [])
            properties = schema.get("properties", {})

            for field in required:
                if field not in data:
                    return {
                        "passed": False,
                        "reason": f"缺少必需字段: {field}"
                    }

            # 检查字段类型
            for field, value in data.items():
                if field in properties:
                    expected_type = properties[field].get("type")
                    if not self._check_type(value, expected_type):
                        return {
                            "passed": False,
                            "reason": f"字段 '{field}' 类型不匹配，期望 {expected_type}"
                        }

            return {"passed": True, "reason": None}

        except json.JSONDecodeError as e:
            return {
                "passed": False,
                "reason": f"输出不是有效的 JSON: {str(e)}"
            }

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型"""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected = type_map.get(expected_type)
        if expected is None:
            return True

        return isinstance(value, expected)

    async def validate_and_fix(
        self,
        text: str,
        fix_function: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        验证输出并尝试修复

        Args:
            text: 要验证的文本
            fix_function: 修复函数（重新生成）

        Returns:
            验证和修复结果
        """
        for attempt in range(self.gai_config.max_retries + 1):
            result = await self.check_output(text)

            if result.is_safe:
                return {
                    "success": True,
                    "output": text,
                    "attempts": attempt + 1
                }

            if not self.gai_config.auto_retry or fix_function is None:
                return {
                    "success": False,
                    "output": text,
                    "error": result.reason,
                    "attempts": attempt + 1
                }

            # 尝试修复（重新生成）
            text = await fix_function()

        return {
            "success": False,
            "output": text,
            "error": "达到最大重试次数",
            "attempts": self.gai_config.max_retries + 1
        }
