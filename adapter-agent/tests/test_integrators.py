"""
AI 应用集成插件测试
"""

import pytest
import asyncio

from adapter_agent.plugins.app_integrators import (
    BaseIntegratorPlugin,
    IntegrationResult,
    IntegrationPoint,
    LangChainIntegrator,
    LlamaIndexIntegrator,
    ClaudeBotIntegrator
)


class TestLangChainIntegrator:
    """LangChain 集成器测试"""

    @pytest.fixture
    def integrator(self):
        return LangChainIntegrator()

    @pytest.mark.asyncio
    async def test_initialize(self, integrator):
        """测试初始化"""
        result = await integrator.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_intercept_pre_prompt(self, integrator):
        """测试输入拦截"""
        await integrator.initialize()

        result = await integrator.intercept(
            IntegrationPoint.PRE_PROMPT,
            "Hello, how are you?",
            {}
        )

        assert result.success is True
        assert result.point == IntegrationPoint.PRE_PROMPT

    def test_supported_points(self, integrator):
        """测试支持的集成点"""
        points = integrator.get_supported_points()

        assert IntegrationPoint.PRE_PROMPT in points
        assert IntegrationPoint.PRE_LLM_CALL in points
        assert IntegrationPoint.POST_LLM_CALL in points
        assert IntegrationPoint.PRE_TOOL_CALL in points

    def test_get_wrapper_code(self, integrator):
        """测试获取包装器代码"""
        code = integrator.get_wrapper_code()

        assert "GuardAdapterCallback" in code
        assert "wrap_chain" in code

    def test_get_middleware_code(self, integrator):
        """测试获取中间件代码"""
        code = integrator.get_middleware_code()

        assert "GuardAdapterMiddleware" in code


class TestLlamaIndexIntegrator:
    """LlamaIndex 集成器测试"""

    @pytest.fixture
    def integrator(self):
        return LlamaIndexIntegrator()

    @pytest.mark.asyncio
    async def test_initialize(self, integrator):
        """测试初始化"""
        result = await integrator.initialize()
        assert result is True

    def test_framework_name(self, integrator):
        """测试框架名称"""
        assert integrator.FRAMEWORK_NAME == "llamaindex"

    def test_get_wrapper_code(self, integrator):
        """测试获取包装器代码"""
        code = integrator.get_wrapper_code()

        assert "GuardAdapterCallbackHandler" in code
        assert "wrap_query_engine" in code


class TestClaudeBotIntegrator:
    """ClaudeBot 集成器测试"""

    @pytest.fixture
    def integrator(self):
        return ClaudeBotIntegrator()

    @pytest.mark.asyncio
    async def test_initialize(self, integrator):
        """测试初始化"""
        result = await integrator.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_dangerous_operation_blocked(self, integrator):
        """测试危险操作拦截"""
        await integrator.initialize()

        result = await integrator.intercept(
            IntegrationPoint.PRE_TOOL_CALL,
            {"tool_name": "delete_all_data", "args": {}},
            {}
        )

        assert result.blocked is True

    @pytest.mark.asyncio
    async def test_confirmation_required(self, integrator):
        """测试需要确认的操作"""
        await integrator.initialize()

        result = await integrator.intercept(
            IntegrationPoint.PRE_TOOL_CALL,
            {"tool_name": "delete_email", "args": {"email_id": "123"}},
            {}
        )

        # 应该被阻止（需要确认但没有确认回调）
        assert result.blocked is True
        assert "确认" in result.block_reason or "confirm" in result.block_reason.lower()

    @pytest.mark.asyncio
    async def test_sensitive_data_masking(self, integrator):
        """测试敏感数据脱敏"""
        await integrator.initialize()

        result = await integrator.intercept(
            IntegrationPoint.POST_RESULT,
            "用户邮箱: test@example.com, 手机: 13812345678",
            {}
        )

        assert result.success is True
        # 敏感信息应该被脱敏
        assert "test@example.com" not in str(result.modified_data)
        assert "13812345678" not in str(result.modified_data)

    def test_supported_points(self, integrator):
        """测试支持的集成点"""
        points = integrator.get_supported_points()

        assert IntegrationPoint.PRE_PROMPT in points
        assert IntegrationPoint.POST_TASK_SPLIT in points
        assert IntegrationPoint.PRE_TOOL_CALL in points
        assert IntegrationPoint.POST_RESULT in points

    def test_audit_logs(self, integrator):
        """测试审计日志"""
        logs = integrator.get_audit_logs()
        assert isinstance(logs, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
