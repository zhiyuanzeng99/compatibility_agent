"""
Protocol Adapter - 多协议适配器

支持 REST、gRPC、SDK 等多种协议的统一接入
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import json


class ProtocolType(Enum):
    """协议类型"""
    REST = "rest"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
    SDK = "sdk"


@dataclass
class Request:
    """统一请求格式"""
    id: str
    protocol: ProtocolType
    method: str
    path: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "protocol": self.protocol.value,
            "method": self.method,
            "path": self.path,
            "headers": self.headers,
            "body": self.body,
            "metadata": self.metadata
        }


@dataclass
class Response:
    """统一响应格式"""
    request_id: str
    status_code: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "error": self.error
        }


class BaseProtocolAdapter(ABC):
    """协议适配器基类"""

    @abstractmethod
    def parse_request(self, raw_request: Any) -> Request:
        """解析原始请求为统一格式"""
        pass

    @abstractmethod
    def format_response(self, response: Response) -> Any:
        """格式化响应为协议特定格式"""
        pass

    @abstractmethod
    def get_protocol_type(self) -> ProtocolType:
        """获取协议类型"""
        pass


class RESTAdapter(BaseProtocolAdapter):
    """REST API 适配器"""

    def parse_request(self, raw_request: Dict) -> Request:
        """解析 REST 请求"""
        return Request(
            id=raw_request.get("request_id", ""),
            protocol=ProtocolType.REST,
            method=raw_request.get("method", "GET"),
            path=raw_request.get("path", "/"),
            headers=raw_request.get("headers", {}),
            body=raw_request.get("body"),
            metadata=raw_request.get("metadata", {})
        )

    def format_response(self, response: Response) -> Dict:
        """格式化为 REST 响应"""
        return {
            "status_code": response.status_code,
            "headers": {
                "Content-Type": "application/json",
                **response.headers
            },
            "body": json.dumps(response.body) if response.body else ""
        }

    def get_protocol_type(self) -> ProtocolType:
        return ProtocolType.REST


class GRPCAdapter(BaseProtocolAdapter):
    """gRPC 适配器"""

    def parse_request(self, raw_request: Any) -> Request:
        """解析 gRPC 请求"""
        # gRPC 消息通常是 protobuf 格式
        return Request(
            id=getattr(raw_request, "request_id", ""),
            protocol=ProtocolType.GRPC,
            method=getattr(raw_request, "method", ""),
            path=getattr(raw_request, "service", ""),
            headers=dict(getattr(raw_request, "metadata", {})),
            body=raw_request,
            metadata={}
        )

    def format_response(self, response: Response) -> Any:
        """格式化为 gRPC 响应"""
        # 返回可序列化的响应对象
        return {
            "status": response.status_code,
            "message": response.body,
            "error": response.error
        }

    def get_protocol_type(self) -> ProtocolType:
        return ProtocolType.GRPC


class WebSocketAdapter(BaseProtocolAdapter):
    """WebSocket 适配器"""

    def parse_request(self, raw_request: str) -> Request:
        """解析 WebSocket 消息"""
        try:
            data = json.loads(raw_request)
        except json.JSONDecodeError:
            data = {"message": raw_request}

        return Request(
            id=data.get("id", ""),
            protocol=ProtocolType.WEBSOCKET,
            method="MESSAGE",
            path=data.get("type", "message"),
            headers={},
            body=data.get("payload", data),
            metadata=data.get("metadata", {})
        )

    def format_response(self, response: Response) -> str:
        """格式化为 WebSocket 消息"""
        return json.dumps({
            "id": response.request_id,
            "type": "response",
            "payload": response.body,
            "error": response.error
        })

    def get_protocol_type(self) -> ProtocolType:
        return ProtocolType.WEBSOCKET


class SDKAdapter(BaseProtocolAdapter):
    """SDK 直接调用适配器"""

    def parse_request(self, raw_request: Dict) -> Request:
        """解析 SDK 调用"""
        return Request(
            id=raw_request.get("call_id", ""),
            protocol=ProtocolType.SDK,
            method=raw_request.get("function", ""),
            path=raw_request.get("module", ""),
            headers={},
            body=raw_request.get("args", {}),
            metadata=raw_request.get("kwargs", {})
        )

    def format_response(self, response: Response) -> Any:
        """返回 SDK 响应（直接返回结果）"""
        if response.error:
            raise Exception(response.error)
        return response.body

    def get_protocol_type(self) -> ProtocolType:
        return ProtocolType.SDK


class ProtocolAdapter:
    """
    协议适配器管理器

    统一管理多种协议的适配
    """

    def __init__(self):
        self._adapters: Dict[ProtocolType, BaseProtocolAdapter] = {
            ProtocolType.REST: RESTAdapter(),
            ProtocolType.GRPC: GRPCAdapter(),
            ProtocolType.WEBSOCKET: WebSocketAdapter(),
            ProtocolType.SDK: SDKAdapter(),
        }
        self._middleware: List[Callable[[Request], Request]] = []

    def register_adapter(self, adapter: BaseProtocolAdapter) -> None:
        """注册自定义适配器"""
        self._adapters[adapter.get_protocol_type()] = adapter

    def add_middleware(self, middleware: Callable[[Request], Request]) -> None:
        """添加请求中间件"""
        self._middleware.append(middleware)

    def parse_request(self, protocol: ProtocolType, raw_request: Any) -> Request:
        """解析请求"""
        adapter = self._adapters.get(protocol)
        if not adapter:
            raise ValueError(f"不支持的协议类型: {protocol}")

        request = adapter.parse_request(raw_request)

        # 应用中间件
        for middleware in self._middleware:
            request = middleware(request)

        return request

    def format_response(self, protocol: ProtocolType, response: Response) -> Any:
        """格式化响应"""
        adapter = self._adapters.get(protocol)
        if not adapter:
            raise ValueError(f"不支持的协议类型: {protocol}")

        return adapter.format_response(response)

    def get_supported_protocols(self) -> List[ProtocolType]:
        """获取支持的协议列表"""
        return list(self._adapters.keys())
