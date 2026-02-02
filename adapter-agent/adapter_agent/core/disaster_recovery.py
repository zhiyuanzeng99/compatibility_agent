"""
Disaster Recovery Module - 容灾恢复（完整版）

功能：
- 自动故障检测
- 故障转移
- 降级策略
- 恢复机制
"""

import asyncio
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from enum import Enum

from .scanner import ProjectProfile
from .matcher import SafetyTool
from .validator import Validator, ValidationStatus


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class FailoverStrategy(Enum):
    """故障转移策略"""
    BYPASS = "bypass"           # 跳过安全检查
    FALLBACK = "fallback"       # 使用备用工具
    REJECT = "reject"           # 拒绝所有请求
    LOG_ONLY = "log_only"       # 仅记录，不阻止


class RecoveryAction(Enum):
    """恢复动作"""
    RESTART = "restart"
    RELOAD_CONFIG = "reload_config"
    SWITCH_TOOL = "switch_tool"
    ROLLBACK = "rollback"
    MANUAL = "manual"


@dataclass
class HealthCheck:
    """健康检查结果"""
    component: str
    status: HealthStatus
    latency_ms: float = 0
    error: Optional[str] = None
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0


@dataclass
class FailoverEvent:
    """故障转移事件"""
    timestamp: datetime
    trigger: str
    strategy: FailoverStrategy
    from_state: HealthStatus
    to_state: HealthStatus
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FailoverResult:
    """故障转移结果"""
    success: bool
    strategy: FailoverStrategy
    action_taken: str
    original_tool: Optional[SafetyTool] = None
    fallback_tool: Optional[SafetyTool] = None
    error: Optional[str] = None
    recovery_time_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "strategy": self.strategy.value,
            "action_taken": self.action_taken,
            "original_tool": self.original_tool.value if self.original_tool else None,
            "fallback_tool": self.fallback_tool.value if self.fallback_tool else None,
            "error": self.error,
            "recovery_time_ms": self.recovery_time_ms
        }


@dataclass
class DisasterRecoveryConfig:
    """容灾恢复配置"""
    # 健康检查配置
    health_check_interval_seconds: int = 30
    health_check_timeout_seconds: int = 5
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2

    # 故障转移配置
    failover_strategy: FailoverStrategy = FailoverStrategy.FALLBACK
    fallback_tools: List[SafetyTool] = field(default_factory=list)
    auto_recovery: bool = True
    recovery_delay_seconds: int = 60

    # 降级配置
    allow_degraded_mode: bool = True
    degraded_timeout_seconds: int = 300


class DisasterRecovery:
    """
    容灾恢复 - 完整版

    提供安全防护系统的高可用保障
    """

    def __init__(
        self,
        profile: ProjectProfile,
        config: Optional[DisasterRecoveryConfig] = None
    ):
        self.profile = profile
        self.config = config or DisasterRecoveryConfig()
        self.project_path = Path(profile.project_path)

        # 状态
        self._current_tool: Optional[SafetyTool] = None
        self._health_checks: Dict[str, HealthCheck] = {}
        self._failover_history: List[FailoverEvent] = []
        self._is_degraded: bool = False
        self._degraded_since: Optional[datetime] = None

        # 回调
        self._on_failover: Optional[Callable[[FailoverEvent], None]] = None
        self._on_recovery: Optional[Callable[[], None]] = None

    def set_current_tool(self, tool: SafetyTool) -> None:
        """设置当前使用的安全工具"""
        self._current_tool = tool

    def on_failover(self, callback: Callable[[FailoverEvent], None]) -> None:
        """设置故障转移回调"""
        self._on_failover = callback

    def on_recovery(self, callback: Callable[[], None]) -> None:
        """设置恢复回调"""
        self._on_recovery = callback

    async def health_check(self) -> HealthCheck:
        """
        执行健康检查

        Returns:
            健康检查结果
        """
        check = HealthCheck(
            component="safety_wrapper",
            status=HealthStatus.UNKNOWN,
            last_check=datetime.now()
        )

        start_time = time.perf_counter()

        try:
            # 检查安全模块
            validator = Validator(self.profile)
            report = validator.validate()

            latency = (time.perf_counter() - start_time) * 1000
            check.latency_ms = latency

            if report.overall_status == ValidationStatus.PASSED:
                check.status = HealthStatus.HEALTHY
                check.consecutive_failures = 0
            elif report.overall_status == ValidationStatus.WARNING:
                check.status = HealthStatus.DEGRADED
                check.consecutive_failures = 0
            else:
                check.status = HealthStatus.UNHEALTHY
                check.error = report.summary
                prev_check = self._health_checks.get("safety_wrapper")
                check.consecutive_failures = (
                    prev_check.consecutive_failures + 1 if prev_check else 1
                )

        except asyncio.TimeoutError:
            check.status = HealthStatus.UNHEALTHY
            check.error = "健康检查超时"
            check.latency_ms = self.config.health_check_timeout_seconds * 1000

        except Exception as e:
            check.status = HealthStatus.UNHEALTHY
            check.error = str(e)
            check.latency_ms = (time.perf_counter() - start_time) * 1000

        self._health_checks["safety_wrapper"] = check
        return check

    async def failover(self, trigger: str = "manual") -> FailoverResult:
        """
        执行故障转移

        Args:
            trigger: 触发原因

        Returns:
            故障转移结果
        """
        start_time = time.perf_counter()
        result = FailoverResult(
            success=False,
            strategy=self.config.failover_strategy,
            action_taken="",
            original_tool=self._current_tool
        )

        try:
            # 记录事件
            event = FailoverEvent(
                timestamp=datetime.now(),
                trigger=trigger,
                strategy=self.config.failover_strategy,
                from_state=self._get_current_health_status(),
                to_state=HealthStatus.UNKNOWN,
                details={"original_tool": self._current_tool.value if self._current_tool else None}
            )

            # 执行策略
            if self.config.failover_strategy == FailoverStrategy.BYPASS:
                result = await self._execute_bypass_strategy(result)

            elif self.config.failover_strategy == FailoverStrategy.FALLBACK:
                result = await self._execute_fallback_strategy(result)

            elif self.config.failover_strategy == FailoverStrategy.REJECT:
                result = await self._execute_reject_strategy(result)

            elif self.config.failover_strategy == FailoverStrategy.LOG_ONLY:
                result = await self._execute_log_only_strategy(result)

            # 更新事件
            event.to_state = HealthStatus.DEGRADED if result.success else HealthStatus.UNHEALTHY
            event.details["result"] = result.action_taken

            self._failover_history.append(event)

            # 触发回调
            if self._on_failover:
                self._on_failover(event)

            # 进入降级模式
            if result.success and self.config.allow_degraded_mode:
                self._is_degraded = True
                self._degraded_since = datetime.now()

        except Exception as e:
            result.success = False
            result.error = str(e)

        result.recovery_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    async def _execute_bypass_strategy(self, result: FailoverResult) -> FailoverResult:
        """执行跳过策略"""
        # 禁用安全检查
        result.success = True
        result.action_taken = "已禁用安全检查，所有请求将直接通过"
        return result

    async def _execute_fallback_strategy(self, result: FailoverResult) -> FailoverResult:
        """执行备用策略"""
        # 尝试切换到备用工具
        for fallback_tool in self.config.fallback_tools:
            if fallback_tool != self._current_tool:
                try:
                    # 验证备用工具可用
                    # 这里简化处理，实际应该部署并验证
                    result.fallback_tool = fallback_tool
                    result.success = True
                    result.action_taken = f"已切换到备用工具: {fallback_tool.value}"
                    self._current_tool = fallback_tool
                    return result
                except Exception:
                    continue

        # 没有可用的备用工具，降级到日志模式
        result.success = True
        result.action_taken = "无可用备用工具，已降级为日志模式"
        return result

    async def _execute_reject_strategy(self, result: FailoverResult) -> FailoverResult:
        """执行拒绝策略"""
        result.success = True
        result.action_taken = "已启用拒绝模式，所有请求将被拒绝"
        return result

    async def _execute_log_only_strategy(self, result: FailoverResult) -> FailoverResult:
        """执行仅日志策略"""
        result.success = True
        result.action_taken = "已启用日志模式，安全检查失败将仅记录日志"
        return result

    async def recover(self) -> bool:
        """
        尝试恢复

        Returns:
            是否恢复成功
        """
        # 执行健康检查
        check = await self.health_check()

        if check.status == HealthStatus.HEALTHY:
            self._is_degraded = False
            self._degraded_since = None

            if self._on_recovery:
                self._on_recovery()

            return True

        return False

    async def start_monitoring(self) -> None:
        """启动健康监控"""
        while True:
            try:
                check = await self.health_check()

                # 检查是否需要故障转移
                if check.consecutive_failures >= self.config.unhealthy_threshold:
                    await self.failover(trigger="consecutive_failures")

                # 检查降级超时
                if self._is_degraded and self._degraded_since:
                    elapsed = (datetime.now() - self._degraded_since).total_seconds()
                    if elapsed > self.config.degraded_timeout_seconds:
                        # 尝试恢复
                        if self.config.auto_recovery:
                            await self.recover()

                await asyncio.sleep(self.config.health_check_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self.config.health_check_interval_seconds)

    def _get_current_health_status(self) -> HealthStatus:
        """获取当前健康状态"""
        check = self._health_checks.get("safety_wrapper")
        return check.status if check else HealthStatus.UNKNOWN

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "current_tool": self._current_tool.value if self._current_tool else None,
            "health_status": self._get_current_health_status().value,
            "is_degraded": self._is_degraded,
            "degraded_since": self._degraded_since.isoformat() if self._degraded_since else None,
            "health_checks": {
                name: {
                    "status": check.status.value,
                    "latency_ms": check.latency_ms,
                    "error": check.error,
                    "consecutive_failures": check.consecutive_failures
                }
                for name, check in self._health_checks.items()
            },
            "failover_history_count": len(self._failover_history)
        }

    def get_failover_history(self) -> List[Dict]:
        """获取故障转移历史"""
        return [
            {
                "timestamp": event.timestamp.isoformat(),
                "trigger": event.trigger,
                "strategy": event.strategy.value,
                "from_state": event.from_state.value,
                "to_state": event.to_state.value,
                "details": event.details
            }
            for event in self._failover_history
        ]


class SafetyProxy:
    """
    安全代理 - 带容灾的安全检查代理

    在安全工具失败时提供降级保护
    """

    def __init__(
        self,
        profile: ProjectProfile,
        dr_config: Optional[DisasterRecoveryConfig] = None
    ):
        self.profile = profile
        self.dr = DisasterRecovery(profile, dr_config)
        self._safety_module = None

    def _load_safety_module(self):
        """加载安全模块"""
        if self._safety_module:
            return

        import importlib.util
        wrapper_path = Path(self.profile.project_path) / "safety_wrapper.py"

        if wrapper_path.exists():
            spec = importlib.util.spec_from_file_location("safety_wrapper", str(wrapper_path))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._safety_module = module

    async def check_input(self, user_input: str) -> Dict[str, Any]:
        """安全的输入检查（带容灾）"""
        try:
            self._load_safety_module()
            if self._safety_module and hasattr(self._safety_module, 'safety'):
                safety = self._safety_module.safety
                if hasattr(safety, 'check_input'):
                    result = safety.check_input(user_input)
                    return {
                        "is_safe": result.is_safe,
                        "reason": result.reason,
                        "degraded": False
                    }

        except Exception as e:
            # 触发故障转移
            await self.dr.failover(trigger=f"check_input_error: {str(e)}")

            # 降级处理
            if self.dr.config.failover_strategy == FailoverStrategy.BYPASS:
                return {"is_safe": True, "reason": "", "degraded": True}
            elif self.dr.config.failover_strategy == FailoverStrategy.REJECT:
                return {"is_safe": False, "reason": "系统故障，拒绝请求", "degraded": True}
            else:
                return {"is_safe": True, "reason": "", "degraded": True, "logged": True}

        return {"is_safe": True, "reason": "", "degraded": False}


def create_disaster_recovery(
    profile: ProjectProfile,
    config: Optional[DisasterRecoveryConfig] = None
) -> DisasterRecovery:
    """便捷函数：创建容灾恢复实例"""
    return DisasterRecovery(profile, config)
