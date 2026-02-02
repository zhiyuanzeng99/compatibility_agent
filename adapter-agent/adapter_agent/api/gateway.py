"""
Gateway - 统一网关

为黑盒 AI 应用提供透明化安全接入
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime
from enum import Enum
import uuid

from .protocol_adapter import ProtocolAdapter, ProtocolType, Request, Response
from .format_converter import FormatConverter, FormatType
from .router import Router, LoadBalancer, RateLimiter, RouteConfig


class GatewayMode(Enum):
    """网关模式"""
    PROXY = "proxy"              # 代理模式（黑盒应用）
    MIDDLEWARE = "middleware"    # 中间件模式（白盒应用）
    SIDECAR = "sidecar"          # Sidecar 模式


@dataclass
class GatewayConfig:
    """网关配置"""
    mode: GatewayMode = GatewayMode.PROXY
    host: str = "0.0.0.0"
    port: int = 8080

    # 安全配置
    enable_safety_check: bool = True
    safety_check_timeout_ms: int = 5000

    # 限流配置
    enable_rate_limit: bool = True
    rate_limit_per_second: int = 100

    # 日志配置
    enable_audit_log: bool = True
    log_request_body: bool = False
    log_response_body: bool = False

    # 超时配置
    request_timeout_ms: int = 30000
    connect_timeout_ms: int = 5000


@dataclass
class GatewayContext:
    """请求上下文"""
    request_id: str
    start_time: datetime
    request: Request
    client_ip: Optional[str] = None
    user_id: Optional[str] = None
    safety_check_result: Optional[Dict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLog:
    """审计日志"""
    request_id: str
    timestamp: datetime
    client_ip: str
    user_id: Optional[str]
    method: str
    path: str
    status_code: int
    latency_ms: float
    safety_blocked: bool
    safety_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "client_ip": self.client_ip,
            "user_id": self.user_id,
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "safety_blocked": self.safety_blocked,
            "safety_reason": self.safety_reason
        }


class Gateway:
    """
    统一网关

    为 AI 应用提供透明化的安全防护接入
    """

    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()

        # 核心组件
        self._protocol_adapter = ProtocolAdapter()
        self._format_converter = FormatConverter()
        self._router = Router()
        self._rate_limiter = RateLimiter()

        # 安全检查器
        self._safety_checkers: List[Callable[[GatewayContext], Awaitable[Dict]]] = []

        # 钩子
        self._pre_handlers: List[Callable[[GatewayContext], Awaitable[None]]] = []
        self._post_handlers: List[Callable[[GatewayContext, Response], Awaitable[None]]] = []

        # 审计日志
        self._audit_logs: List[AuditLog] = []

    def add_safety_checker(
        self,
        checker: Callable[[GatewayContext], Awaitable[Dict]]
    ) -> None:
        """添加安全检查器"""
        self._safety_checkers.append(checker)

    def add_pre_handler(
        self,
        handler: Callable[[GatewayContext], Awaitable[None]]
    ) -> None:
        """添加请求前处理器"""
        self._pre_handlers.append(handler)

    def add_post_handler(
        self,
        handler: Callable[[GatewayContext, Response], Awaitable[None]]
    ) -> None:
        """添加响应后处理器"""
        self._post_handlers.append(handler)

    def add_route(self, config: RouteConfig) -> None:
        """添加路由规则"""
        self._router.add_route(config)

    async def handle_request(
        self,
        raw_request: Any,
        protocol: ProtocolType,
        client_ip: Optional[str] = None
    ) -> Response:
        """
        处理请求

        Args:
            raw_request: 原始请求
            protocol: 协议类型
            client_ip: 客户端 IP

        Returns:
            响应
        """
        start_time = datetime.now()
        request_id = str(uuid.uuid4())

        try:
            # 解析请求
            request = self._protocol_adapter.parse_request(protocol, raw_request)
            request.id = request_id

            # 创建上下文
            context = GatewayContext(
                request_id=request_id,
                start_time=start_time,
                request=request,
                client_ip=client_ip
            )

            # 限流检查
            if self.config.enable_rate_limit:
                limit_key = client_ip or "global"
                limit_result = self._rate_limiter.check(
                    limit_key,
                    self.config.rate_limit_per_second
                )
                if not limit_result.allowed:
                    return self._create_error_response(
                        request_id, 429, "请求过于频繁，请稍后重试"
                    )

            # 执行前置处理器
            for handler in self._pre_handlers:
                await handler(context)

            # 安全检查
            if self.config.enable_safety_check:
                safety_result = await self._run_safety_checks(context)
                context.safety_check_result = safety_result

                if not safety_result.get("is_safe", True):
                    response = self._create_error_response(
                        request_id,
                        403,
                        safety_result.get("reason", "安全检查未通过")
                    )
                    await self._log_audit(context, response, blocked=True)
                    return response

            # 路由匹配
            route_match = self._router.match(
                request.path,
                request.method,
                client_ip
            )

            if not route_match.matched:
                return self._create_error_response(
                    request_id, 404, "路由未找到"
                )

            # 转发请求
            response = await self._forward_request(context, route_match)

            # 执行后置处理器
            for handler in self._post_handlers:
                await handler(context, response)

            # 记录审计日志
            if self.config.enable_audit_log:
                await self._log_audit(context, response)

            return response

        except asyncio.TimeoutError:
            return self._create_error_response(
                request_id, 504, "请求超时"
            )
        except Exception as e:
            return self._create_error_response(
                request_id, 500, f"内部错误: {str(e)}"
            )

    async def _run_safety_checks(self, context: GatewayContext) -> Dict:
        """运行安全检查"""
        for checker in self._safety_checkers:
            try:
                result = await asyncio.wait_for(
                    checker(context),
                    timeout=self.config.safety_check_timeout_ms / 1000
                )
                if not result.get("is_safe", True):
                    return result
            except asyncio.TimeoutError:
                # 安全检查超时，记录但不阻止
                context.metadata["safety_check_timeout"] = True
            except Exception as e:
                context.metadata["safety_check_error"] = str(e)

        return {"is_safe": True}

    async def _forward_request(
        self,
        context: GatewayContext,
        route_match: Any
    ) -> Response:
        """转发请求到后端服务"""
        # 这里实现实际的请求转发逻辑
        # 在实际实现中，应该使用 aiohttp 或 httpx 进行异步 HTTP 请求

        # 模拟响应
        return Response(
            request_id=context.request_id,
            status_code=200,
            body={"status": "ok", "message": "Request forwarded successfully"}
        )

    def _create_error_response(
        self,
        request_id: str,
        status_code: int,
        message: str
    ) -> Response:
        """创建错误响应"""
        return Response(
            request_id=request_id,
            status_code=status_code,
            body={"error": message},
            error=message
        )

    async def _log_audit(
        self,
        context: GatewayContext,
        response: Response,
        blocked: bool = False
    ) -> None:
        """记录审计日志"""
        latency = (datetime.now() - context.start_time).total_seconds() * 1000

        log = AuditLog(
            request_id=context.request_id,
            timestamp=context.start_time,
            client_ip=context.client_ip or "unknown",
            user_id=context.user_id,
            method=context.request.method,
            path=context.request.path,
            status_code=response.status_code,
            latency_ms=latency,
            safety_blocked=blocked,
            safety_reason=context.safety_check_result.get("reason") if blocked else None
        )

        self._audit_logs.append(log)

        # 保持最近 10000 条日志
        if len(self._audit_logs) > 10000:
            self._audit_logs = self._audit_logs[-10000:]

    def get_audit_logs(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """获取审计日志"""
        logs = self._audit_logs[-(offset + limit):]
        if offset > 0:
            logs = logs[:-offset]
        return [log.to_dict() for log in logs[-limit:]]

    def get_statistics(self) -> Dict:
        """获取网关统计信息"""
        total_requests = len(self._audit_logs)
        blocked_requests = sum(1 for log in self._audit_logs if log.safety_blocked)
        avg_latency = (
            sum(log.latency_ms for log in self._audit_logs) / total_requests
            if total_requests > 0 else 0
        )

        status_codes = {}
        for log in self._audit_logs:
            code = str(log.status_code)
            status_codes[code] = status_codes.get(code, 0) + 1

        return {
            "total_requests": total_requests,
            "blocked_requests": blocked_requests,
            "block_rate": blocked_requests / total_requests if total_requests > 0 else 0,
            "average_latency_ms": avg_latency,
            "status_codes": status_codes
        }
