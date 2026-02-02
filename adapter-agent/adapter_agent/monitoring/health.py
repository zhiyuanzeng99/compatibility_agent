"""
Health Check - 健康检查

系统和组件健康状态检查
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum


class HealthStatus(Enum):
    """健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """组件健康状态"""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: float = 0
    last_check: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "details": self.details
        }


@dataclass
class HealthReport:
    """健康报告"""
    overall_status: HealthStatus
    timestamp: datetime
    components: List[ComponentHealth]
    summary: str

    def to_dict(self) -> dict:
        return {
            "overall_status": self.overall_status.value,
            "timestamp": self.timestamp.isoformat(),
            "components": [c.to_dict() for c in self.components],
            "summary": self.summary
        }

    @property
    def is_healthy(self) -> bool:
        return self.overall_status == HealthStatus.HEALTHY


@dataclass
class HealthCheckConfig:
    """健康检查配置"""
    timeout_seconds: float = 5.0
    interval_seconds: float = 30.0
    failure_threshold: int = 3
    success_threshold: int = 2


class HealthChecker:
    """
    健康检查器

    检查系统各组件的健康状态
    """

    def __init__(self, config: Optional[HealthCheckConfig] = None):
        self.config = config or HealthCheckConfig()
        self._checks: Dict[str, Callable[[], Awaitable[ComponentHealth]]] = {}
        self._last_results: Dict[str, ComponentHealth] = {}
        self._failure_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}

        # 注册内置检查
        self._register_builtin_checks()

    def _register_builtin_checks(self):
        """注册内置健康检查"""
        # 这些检查在实际使用时需要根据具体实现来完善
        pass

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], Awaitable[ComponentHealth]]
    ) -> None:
        """
        注册健康检查

        Args:
            name: 检查名称
            check_fn: 检查函数（异步）
        """
        self._checks[name] = check_fn
        self._failure_counts[name] = 0
        self._success_counts[name] = 0

    def unregister_check(self, name: str) -> None:
        """注销健康检查"""
        self._checks.pop(name, None)
        self._last_results.pop(name, None)
        self._failure_counts.pop(name, None)
        self._success_counts.pop(name, None)

    async def check(self, name: str) -> ComponentHealth:
        """
        执行单个健康检查

        Args:
            name: 检查名称

        Returns:
            组件健康状态
        """
        check_fn = self._checks.get(name)
        if not check_fn:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNKNOWN,
                message="检查未注册"
            )

        start_time = datetime.now()

        try:
            result = await asyncio.wait_for(
                check_fn(),
                timeout=self.config.timeout_seconds
            )
            result.latency_ms = (datetime.now() - start_time).total_seconds() * 1000
            result.last_check = datetime.now()

            # 更新计数
            if result.status == HealthStatus.HEALTHY:
                self._success_counts[name] += 1
                self._failure_counts[name] = 0
            else:
                self._failure_counts[name] += 1
                self._success_counts[name] = 0

            self._last_results[name] = result
            return result

        except asyncio.TimeoutError:
            self._failure_counts[name] += 1
            self._success_counts[name] = 0

            result = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message="检查超时",
                latency_ms=self.config.timeout_seconds * 1000,
                last_check=datetime.now()
            )
            self._last_results[name] = result
            return result

        except Exception as e:
            self._failure_counts[name] += 1
            self._success_counts[name] = 0

            result = ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=(datetime.now() - start_time).total_seconds() * 1000,
                last_check=datetime.now()
            )
            self._last_results[name] = result
            return result

    async def check_all(self) -> HealthReport:
        """
        执行所有健康检查

        Returns:
            健康报告
        """
        components = []

        # 并发执行所有检查
        tasks = [self.check(name) for name in self._checks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                components.append(ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=str(result)
                ))
            else:
                components.append(result)

        # 计算整体状态
        overall_status = self._compute_overall_status(components)

        # 生成摘要
        healthy_count = sum(1 for c in components if c.status == HealthStatus.HEALTHY)
        total_count = len(components)
        summary = f"{healthy_count}/{total_count} 组件健康"

        return HealthReport(
            overall_status=overall_status,
            timestamp=datetime.now(),
            components=components,
            summary=summary
        )

    def _compute_overall_status(
        self,
        components: List[ComponentHealth]
    ) -> HealthStatus:
        """计算整体健康状态"""
        if not components:
            return HealthStatus.UNKNOWN

        statuses = [c.status for c in components]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN

    def get_last_result(self, name: str) -> Optional[ComponentHealth]:
        """获取最后一次检查结果"""
        return self._last_results.get(name)

    def get_all_last_results(self) -> Dict[str, ComponentHealth]:
        """获取所有最后一次检查结果"""
        return self._last_results.copy()

    def is_flapping(self, name: str) -> bool:
        """检查组件是否在震荡（频繁切换状态）"""
        # 简化实现：如果失败和成功计数都未达到阈值，认为在震荡
        failures = self._failure_counts.get(name, 0)
        successes = self._success_counts.get(name, 0)

        return (0 < failures < self.config.failure_threshold and
                0 < successes < self.config.success_threshold)


def create_http_check(url: str, timeout: float = 5.0) -> Callable[[], Awaitable[ComponentHealth]]:
    """
    创建 HTTP 健康检查

    Args:
        url: 检查 URL
        timeout: 超时时间

    Returns:
        健康检查函数
    """
    async def check() -> ComponentHealth:
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        return ComponentHealth(
                            name=url,
                            status=HealthStatus.HEALTHY,
                            details={"status_code": resp.status}
                        )
                    else:
                        return ComponentHealth(
                            name=url,
                            status=HealthStatus.UNHEALTHY,
                            message=f"HTTP {resp.status}",
                            details={"status_code": resp.status}
                        )
        except Exception as e:
            return ComponentHealth(
                name=url,
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )

    return check


def create_tcp_check(
    host: str,
    port: int,
    timeout: float = 5.0
) -> Callable[[], Awaitable[ComponentHealth]]:
    """
    创建 TCP 连接健康检查

    Args:
        host: 主机地址
        port: 端口
        timeout: 超时时间

    Returns:
        健康检查函数
    """
    async def check() -> ComponentHealth:
        name = f"{host}:{port}"
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()

            return ComponentHealth(
                name=name,
                status=HealthStatus.HEALTHY
            )
        except Exception as e:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )

    return check


def create_command_check(
    command: List[str],
    timeout: float = 10.0
) -> Callable[[], Awaitable[ComponentHealth]]:
    """
    创建命令执行健康检查

    Args:
        command: 要执行的命令
        timeout: 超时时间

    Returns:
        健康检查函数
    """
    async def check() -> ComponentHealth:
        name = " ".join(command)
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            if process.returncode == 0:
                return ComponentHealth(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    details={"stdout": stdout.decode()[:200]}
                )
            else:
                return ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Exit code: {process.returncode}",
                    details={"stderr": stderr.decode()[:200]}
                )
        except Exception as e:
            return ComponentHealth(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e)
            )

    return check
