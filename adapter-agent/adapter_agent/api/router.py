"""
Router - 路由与负载均衡

实现请求路由和多实例负载均衡
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import random
import time
import hashlib


class LoadBalanceStrategy(Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    IP_HASH = "ip_hash"


@dataclass
class ServiceInstance:
    """服务实例"""
    id: str
    host: str
    port: int
    weight: int = 1
    healthy: bool = True
    active_connections: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class RouteConfig:
    """路由配置"""
    path_pattern: str
    service_name: str
    methods: List[str] = field(default_factory=lambda: ["GET", "POST"])
    priority: int = 0
    middleware: List[str] = field(default_factory=list)
    rate_limit: Optional[int] = None  # 每秒请求数限制
    timeout_ms: int = 30000
    retry_count: int = 3


@dataclass
class RouteMatch:
    """路由匹配结果"""
    matched: bool
    config: Optional[RouteConfig] = None
    path_params: Dict[str, str] = field(default_factory=dict)
    instance: Optional[ServiceInstance] = None


class LoadBalancer:
    """
    负载均衡器

    支持多种负载均衡策略
    """

    def __init__(self, strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN):
        self.strategy = strategy
        self._instances: Dict[str, List[ServiceInstance]] = {}
        self._round_robin_index: Dict[str, int] = {}

    def register_instance(self, service_name: str, instance: ServiceInstance) -> None:
        """注册服务实例"""
        if service_name not in self._instances:
            self._instances[service_name] = []
            self._round_robin_index[service_name] = 0

        self._instances[service_name].append(instance)

    def unregister_instance(self, service_name: str, instance_id: str) -> None:
        """注销服务实例"""
        if service_name in self._instances:
            self._instances[service_name] = [
                i for i in self._instances[service_name]
                if i.id != instance_id
            ]

    def mark_unhealthy(self, service_name: str, instance_id: str) -> None:
        """标记实例为不健康"""
        if service_name in self._instances:
            for instance in self._instances[service_name]:
                if instance.id == instance_id:
                    instance.healthy = False
                    break

    def mark_healthy(self, service_name: str, instance_id: str) -> None:
        """标记实例为健康"""
        if service_name in self._instances:
            for instance in self._instances[service_name]:
                if instance.id == instance_id:
                    instance.healthy = True
                    break

    def select_instance(
        self,
        service_name: str,
        client_ip: Optional[str] = None
    ) -> Optional[ServiceInstance]:
        """
        选择服务实例

        Args:
            service_name: 服务名称
            client_ip: 客户端 IP（用于 IP Hash 策略）

        Returns:
            选中的服务实例
        """
        instances = self._instances.get(service_name, [])
        healthy_instances = [i for i in instances if i.healthy]

        if not healthy_instances:
            return None

        if self.strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return self._round_robin_select(service_name, healthy_instances)
        elif self.strategy == LoadBalanceStrategy.RANDOM:
            return self._random_select(healthy_instances)
        elif self.strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return self._least_connections_select(healthy_instances)
        elif self.strategy == LoadBalanceStrategy.WEIGHTED:
            return self._weighted_select(healthy_instances)
        elif self.strategy == LoadBalanceStrategy.IP_HASH:
            return self._ip_hash_select(healthy_instances, client_ip)

        return healthy_instances[0]

    def _round_robin_select(
        self,
        service_name: str,
        instances: List[ServiceInstance]
    ) -> ServiceInstance:
        """轮询选择"""
        idx = self._round_robin_index.get(service_name, 0)
        instance = instances[idx % len(instances)]
        self._round_robin_index[service_name] = (idx + 1) % len(instances)
        return instance

    def _random_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """随机选择"""
        return random.choice(instances)

    def _least_connections_select(
        self,
        instances: List[ServiceInstance]
    ) -> ServiceInstance:
        """最少连接数选择"""
        return min(instances, key=lambda i: i.active_connections)

    def _weighted_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """加权选择"""
        total_weight = sum(i.weight for i in instances)
        rand = random.uniform(0, total_weight)

        cumulative = 0
        for instance in instances:
            cumulative += instance.weight
            if rand <= cumulative:
                return instance

        return instances[-1]

    def _ip_hash_select(
        self,
        instances: List[ServiceInstance],
        client_ip: Optional[str]
    ) -> ServiceInstance:
        """IP Hash 选择"""
        if not client_ip:
            return self._random_select(instances)

        hash_value = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        return instances[hash_value % len(instances)]

    def get_instances(self, service_name: str) -> List[ServiceInstance]:
        """获取服务的所有实例"""
        return self._instances.get(service_name, [])


class Router:
    """
    请求路由器

    管理路由规则和请求分发
    """

    def __init__(self, load_balancer: Optional[LoadBalancer] = None):
        self._routes: List[RouteConfig] = []
        self._load_balancer = load_balancer or LoadBalancer()
        self._middleware_registry: Dict[str, Callable] = {}

    def add_route(self, config: RouteConfig) -> None:
        """添加路由规则"""
        self._routes.append(config)
        # 按优先级排序
        self._routes.sort(key=lambda r: r.priority, reverse=True)

    def remove_route(self, path_pattern: str) -> None:
        """移除路由规则"""
        self._routes = [r for r in self._routes if r.path_pattern != path_pattern]

    def register_middleware(self, name: str, handler: Callable) -> None:
        """注册中间件"""
        self._middleware_registry[name] = handler

    def match(self, path: str, method: str, client_ip: Optional[str] = None) -> RouteMatch:
        """
        匹配路由

        Args:
            path: 请求路径
            method: HTTP 方法
            client_ip: 客户端 IP

        Returns:
            路由匹配结果
        """
        for route in self._routes:
            # 检查方法
            if method not in route.methods:
                continue

            # 路径匹配
            path_params = self._match_path(route.path_pattern, path)
            if path_params is not None:
                # 选择服务实例
                instance = self._load_balancer.select_instance(
                    route.service_name,
                    client_ip
                )

                return RouteMatch(
                    matched=True,
                    config=route,
                    path_params=path_params,
                    instance=instance
                )

        return RouteMatch(matched=False)

    def _match_path(self, pattern: str, path: str) -> Optional[Dict[str, str]]:
        """
        匹配路径模式

        支持参数占位符，如 /api/{version}/users/{id}
        """
        pattern_parts = pattern.strip("/").split("/")
        path_parts = path.strip("/").split("/")

        if len(pattern_parts) != len(path_parts):
            return None

        params = {}
        for p_part, path_part in zip(pattern_parts, path_parts):
            if p_part.startswith("{") and p_part.endswith("}"):
                # 参数占位符
                param_name = p_part[1:-1]
                params[param_name] = path_part
            elif p_part == "*":
                # 通配符
                continue
            elif p_part != path_part:
                # 不匹配
                return None

        return params

    def get_middleware(self, names: List[str]) -> List[Callable]:
        """获取中间件列表"""
        return [
            self._middleware_registry[name]
            for name in names
            if name in self._middleware_registry
        ]


@dataclass
class RateLimitResult:
    """限流结果"""
    allowed: bool
    remaining: int
    reset_time: float


class RateLimiter:
    """
    请求限流器

    基于令牌桶算法实现
    """

    def __init__(self):
        self._buckets: Dict[str, Dict] = {}

    def check(self, key: str, limit: int, window_seconds: int = 1) -> RateLimitResult:
        """
        检查是否允许请求

        Args:
            key: 限流键（如 IP 或用户 ID）
            limit: 限制数量
            window_seconds: 时间窗口（秒）

        Returns:
            限流结果
        """
        now = time.time()

        if key not in self._buckets:
            self._buckets[key] = {
                "tokens": limit,
                "last_update": now
            }

        bucket = self._buckets[key]

        # 补充令牌
        elapsed = now - bucket["last_update"]
        tokens_to_add = int(elapsed / window_seconds * limit)
        bucket["tokens"] = min(limit, bucket["tokens"] + tokens_to_add)
        bucket["last_update"] = now

        # 检查令牌
        if bucket["tokens"] > 0:
            bucket["tokens"] -= 1
            return RateLimitResult(
                allowed=True,
                remaining=bucket["tokens"],
                reset_time=now + window_seconds
            )

        return RateLimitResult(
            allowed=False,
            remaining=0,
            reset_time=now + window_seconds
        )
