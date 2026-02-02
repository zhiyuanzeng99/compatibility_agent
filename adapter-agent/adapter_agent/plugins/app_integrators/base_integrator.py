"""
Base Integrator Plugin - AI应用集成插件基类

定义AI应用集成的通用接口
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime
from enum import Enum

from ..base import BasePlugin, PluginConfig


class IntegrationPoint(Enum):
    """集成点"""
    PRE_PROMPT = "pre_prompt"           # Prompt输入前
    POST_TASK_SPLIT = "post_task_split"  # 任务拆分后
    PRE_TOOL_CALL = "pre_tool_call"     # 工具调用前
    POST_RESULT = "post_result"         # 最终结果后
    PRE_LLM_CALL = "pre_llm_call"       # LLM调用前
    POST_LLM_CALL = "post_llm_call"     # LLM调用后


@dataclass
class IntegrationResult:
    """集成结果"""
    success: bool
    point: IntegrationPoint
    modified_data: Any = None
    blocked: bool = False
    block_reason: Optional[str] = None
    latency_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "point": self.point.value,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata
        }


@dataclass
class IntegratorConfig(PluginConfig):
    """集成器配置"""
    # 启用的集成点
    enabled_points: List[IntegrationPoint] = field(
        default_factory=lambda: list(IntegrationPoint)
    )
    # 是否异步处理
    async_mode: bool = False
    # 超时配置
    timeout_seconds: float = 5.0


class BaseIntegratorPlugin(BasePlugin):
    """
    AI应用集成插件基类

    所有AI应用集成插件必须继承此类
    """

    PLUGIN_TYPE = "app_integrator"

    # 支持的集成点（子类覆盖）
    SUPPORTED_POINTS: List[IntegrationPoint] = []

    # 支持的框架名称
    FRAMEWORK_NAME: str = "base"

    def __init__(self, config: Optional[IntegratorConfig] = None):
        super().__init__(config)
        self.integrator_config = config or IntegratorConfig(
            name=self.NAME,
            version=self.VERSION
        )
        # 安全检查器回调
        self._safety_checkers: Dict[IntegrationPoint, List[Callable]] = {}

    def register_safety_checker(
        self,
        point: IntegrationPoint,
        checker: Callable[[Any, Dict], Awaitable[Dict]]
    ) -> None:
        """
        注册安全检查器

        Args:
            point: 集成点
            checker: 检查函数，接收(data, context)返回检查结果
        """
        if point not in self._safety_checkers:
            self._safety_checkers[point] = []
        self._safety_checkers[point].append(checker)

    @abstractmethod
    async def intercept(
        self,
        point: IntegrationPoint,
        data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> IntegrationResult:
        """
        拦截并处理数据

        Args:
            point: 集成点
            data: 要处理的数据
            context: 上下文信息

        Returns:
            集成结果
        """
        pass

    @abstractmethod
    def get_wrapper_code(self) -> str:
        """
        获取包装器代码

        Returns:
            可以集成到目标应用的包装器代码
        """
        pass

    @abstractmethod
    def get_middleware_code(self) -> str:
        """
        获取中间件代码

        Returns:
            可以作为中间件使用的代码
        """
        pass

    async def run_safety_checks(
        self,
        point: IntegrationPoint,
        data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        运行安全检查

        Args:
            point: 集成点
            data: 要检查的数据
            context: 上下文

        Returns:
            检查结果
        """
        checkers = self._safety_checkers.get(point, [])
        results = []

        for checker in checkers:
            try:
                result = await checker(data, context or {})
                results.append(result)

                # 如果任何检查失败，立即返回
                if not result.get("is_safe", True):
                    return {
                        "is_safe": False,
                        "reason": result.get("reason", "安全检查未通过"),
                        "results": results
                    }
            except Exception as e:
                results.append({"error": str(e)})

        return {"is_safe": True, "results": results}

    def supports_point(self, point: IntegrationPoint) -> bool:
        """检查是否支持某个集成点"""
        return point in self.SUPPORTED_POINTS

    def get_supported_points(self) -> List[IntegrationPoint]:
        """获取支持的集成点"""
        return self.SUPPORTED_POINTS.copy()
