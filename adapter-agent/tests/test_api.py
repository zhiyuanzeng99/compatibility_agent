"""
API 接入层测试
"""

import pytest
from adapter_agent.api import (
    ProtocolAdapter,
    ProtocolType,
    FormatConverter,
    FormatType,
    Router,
    RouteConfig,
    LoadBalancer,
    LoadBalanceStrategy,
    ServiceInstance,
    Gateway,
    GatewayConfig
)


class TestProtocolAdapter:
    """协议适配器测试"""

    def test_rest_adapter(self):
        """测试 REST 适配器"""
        adapter = ProtocolAdapter()
        raw_request = {
            "request_id": "req_001",
            "method": "POST",
            "path": "/api/v1/chat",
            "headers": {"Content-Type": "application/json"},
            "body": {"message": "hello"}
        }

        request = adapter.parse_request(ProtocolType.REST, raw_request)

        assert request.protocol == ProtocolType.REST
        assert request.method == "POST"
        assert request.path == "/api/v1/chat"
        assert request.body == {"message": "hello"}

    def test_websocket_adapter(self):
        """测试 WebSocket 适配器"""
        adapter = ProtocolAdapter()
        raw_message = '{"id": "msg_001", "type": "message", "payload": "hello"}'

        request = adapter.parse_request(ProtocolType.WEBSOCKET, raw_message)

        assert request.protocol == ProtocolType.WEBSOCKET
        assert request.body == "hello"

    def test_supported_protocols(self):
        """测试支持的协议"""
        adapter = ProtocolAdapter()
        protocols = adapter.get_supported_protocols()

        assert ProtocolType.REST in protocols
        assert ProtocolType.GRPC in protocols
        assert ProtocolType.WEBSOCKET in protocols
        assert ProtocolType.SDK in protocols


class TestFormatConverter:
    """格式转换器测试"""

    def test_openai_to_anthropic(self):
        """测试 OpenAI 到 Anthropic 格式转换"""
        converter = FormatConverter()
        openai_format = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ],
            "model": "gpt-4"
        }

        result = converter.convert(
            openai_format,
            FormatType.OPENAI_CHAT,
            FormatType.ANTHROPIC_CHAT
        )

        assert result.success is True
        assert "system" in result.converted_data
        assert len(result.converted_data["messages"]) == 2  # user + assistant

    def test_anthropic_to_openai(self):
        """测试 Anthropic 到 OpenAI 格式转换"""
        converter = FormatConverter()
        anthropic_format = {
            "system": "You are a helpful assistant",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"}
            ]
        }

        result = converter.convert(
            anthropic_format,
            FormatType.ANTHROPIC_CHAT,
            FormatType.OPENAI_CHAT
        )

        assert result.success is True
        assert len(result.converted_data["messages"]) == 3  # system + user + assistant

    def test_format_detection(self):
        """测试格式检测"""
        converter = FormatConverter()

        openai_data = {
            "messages": [{"role": "user", "content": "hello"}]
        }
        detected = converter.detect_format(openai_data)
        assert detected == FormatType.OPENAI_CHAT


class TestRouter:
    """路由器测试"""

    def test_add_route(self):
        """测试添加路由"""
        router = Router()
        config = RouteConfig(
            path_pattern="/api/v1/chat",
            service_name="chat_service",
            methods=["POST"]
        )
        router.add_route(config)

        match = router.match("/api/v1/chat", "POST")
        assert match.matched is True
        assert match.config.service_name == "chat_service"

    def test_path_params(self):
        """测试路径参数"""
        router = Router()
        config = RouteConfig(
            path_pattern="/api/{version}/users/{id}",
            service_name="user_service"
        )
        router.add_route(config)

        match = router.match("/api/v1/users/123", "GET")
        assert match.matched is True
        assert match.path_params["version"] == "v1"
        assert match.path_params["id"] == "123"

    def test_no_match(self):
        """测试无匹配"""
        router = Router()
        match = router.match("/unknown/path", "GET")
        assert match.matched is False


class TestLoadBalancer:
    """负载均衡器测试"""

    def test_round_robin(self):
        """测试轮询策略"""
        lb = LoadBalancer(strategy=LoadBalanceStrategy.ROUND_ROBIN)

        lb.register_instance("service1", ServiceInstance("1", "host1", 8080))
        lb.register_instance("service1", ServiceInstance("2", "host2", 8080))
        lb.register_instance("service1", ServiceInstance("3", "host3", 8080))

        # 轮询选择
        instances = [lb.select_instance("service1") for _ in range(6)]
        hosts = [i.host for i in instances]

        # 应该循环选择
        assert hosts == ["host1", "host2", "host3", "host1", "host2", "host3"]

    def test_least_connections(self):
        """测试最少连接策略"""
        lb = LoadBalancer(strategy=LoadBalanceStrategy.LEAST_CONNECTIONS)

        i1 = ServiceInstance("1", "host1", 8080, active_connections=5)
        i2 = ServiceInstance("2", "host2", 8080, active_connections=2)
        i3 = ServiceInstance("3", "host3", 8080, active_connections=8)

        lb.register_instance("service1", i1)
        lb.register_instance("service1", i2)
        lb.register_instance("service1", i3)

        selected = lb.select_instance("service1")
        assert selected.host == "host2"  # 连接数最少

    def test_health_status(self):
        """测试健康状态"""
        lb = LoadBalancer()

        lb.register_instance("service1", ServiceInstance("1", "host1", 8080))
        lb.register_instance("service1", ServiceInstance("2", "host2", 8080))

        lb.mark_unhealthy("service1", "1")

        selected = lb.select_instance("service1")
        assert selected.host == "host2"  # 只选择健康实例


class TestGateway:
    """网关测试"""

    @pytest.fixture
    def gateway(self):
        config = GatewayConfig(
            enable_safety_check=True,
            enable_rate_limit=True,
            rate_limit_per_second=10
        )
        return Gateway(config)

    def test_gateway_init(self, gateway):
        """测试网关初始化"""
        assert gateway.config.enable_safety_check is True
        assert gateway.config.rate_limit_per_second == 10

    def test_add_route(self, gateway):
        """测试添加路由"""
        gateway.add_route(RouteConfig(
            path_pattern="/api/chat",
            service_name="chat"
        ))
        # 路由已添加

    def test_get_statistics(self, gateway):
        """测试获取统计"""
        stats = gateway.get_statistics()
        assert "total_requests" in stats
        assert "blocked_requests" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
