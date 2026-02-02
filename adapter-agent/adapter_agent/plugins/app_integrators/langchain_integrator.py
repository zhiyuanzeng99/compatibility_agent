"""
LangChain Integrator - LangChain 框架集成插件

支持:
- Chain 包装
- Agent 拦截
- Tool 安全检查
- Callback 集成
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from .base_integrator import (
    BaseIntegratorPlugin,
    IntegrationResult,
    IntegrationPoint,
    IntegratorConfig
)


@dataclass
class LangChainConfig(IntegratorConfig):
    """LangChain 集成配置"""
    # Chain 配置
    wrap_chains: bool = True
    wrap_agents: bool = True
    # Callback 配置
    use_callbacks: bool = True
    # 流式处理
    streaming_enabled: bool = True


class LangChainIntegrator(BaseIntegratorPlugin):
    """
    LangChain 集成插件

    为 LangChain 应用提供无侵入的安全防护集成
    """

    NAME = "langchain_integrator"
    VERSION = "1.0.0"
    DESCRIPTION = "LangChain 框架集成，支持 Chain/Agent/Tool 安全防护"
    AUTHOR = "GuardAdapter"
    FRAMEWORK_NAME = "langchain"

    SUPPORTED_POINTS = [
        IntegrationPoint.PRE_PROMPT,
        IntegrationPoint.PRE_LLM_CALL,
        IntegrationPoint.POST_LLM_CALL,
        IntegrationPoint.PRE_TOOL_CALL,
        IntegrationPoint.POST_RESULT,
    ]

    def __init__(self, config: Optional[LangChainConfig] = None):
        super().__init__(config)
        self.lc_config = config or LangChainConfig(
            name=self.NAME,
            version=self.VERSION
        )

    async def initialize(self) -> bool:
        """初始化"""
        return True

    async def shutdown(self) -> None:
        """关闭"""
        pass

    async def intercept(
        self,
        point: IntegrationPoint,
        data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> IntegrationResult:
        """拦截并处理数据"""
        start_time = time.perf_counter()

        if point not in self.SUPPORTED_POINTS:
            return IntegrationResult(
                success=False,
                point=point,
                metadata={"error": f"不支持的集成点: {point}"}
            )

        # 运行安全检查
        safety_result = await self.run_safety_checks(point, data, context)

        if not safety_result.get("is_safe", True):
            return IntegrationResult(
                success=True,
                point=point,
                blocked=True,
                block_reason=safety_result.get("reason"),
                latency_ms=(time.perf_counter() - start_time) * 1000
            )

        # 根据集成点处理数据
        modified_data = data
        if point == IntegrationPoint.PRE_PROMPT:
            modified_data = await self._process_pre_prompt(data, context)
        elif point == IntegrationPoint.POST_RESULT:
            modified_data = await self._process_post_result(data, context)

        return IntegrationResult(
            success=True,
            point=point,
            modified_data=modified_data,
            latency_ms=(time.perf_counter() - start_time) * 1000
        )

    async def _process_pre_prompt(
        self,
        data: Any,
        context: Optional[Dict[str, Any]]
    ) -> Any:
        """处理输入前的数据"""
        # 可以在这里添加预处理逻辑
        return data

    async def _process_post_result(
        self,
        data: Any,
        context: Optional[Dict[str, Any]]
    ) -> Any:
        """处理输出后的数据"""
        # 可以在这里添加后处理逻辑（如脱敏）
        return data

    def get_wrapper_code(self) -> str:
        """获取 LangChain 包装器代码"""
        return '''
"""
GuardAdapter LangChain Wrapper
自动生成的安全防护包装器
"""

from typing import Any, Dict, List, Optional
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult


class GuardAdapterCallback(BaseCallbackHandler):
    """GuardAdapter 回调处理器"""

    def __init__(self, safety_checker):
        self.safety_checker = safety_checker

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs
    ) -> None:
        """LLM 调用开始前"""
        for prompt in prompts:
            result = self.safety_checker.check_input(prompt)
            if not result.is_safe:
                raise ValueError(f"输入安全检查失败: {result.reason}")

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        """LLM 调用结束后"""
        for generation in response.generations:
            for gen in generation:
                result = self.safety_checker.check_output(gen.text)
                if not result.is_safe:
                    raise ValueError(f"输出安全检查失败: {result.reason}")

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        **kwargs
    ) -> None:
        """工具调用开始前"""
        tool_name = serialized.get("name", "unknown")
        result = self.safety_checker.check_tool_call(tool_name, {"input": input_str})
        if not result.is_safe:
            raise ValueError(f"工具调用安全检查失败: {result.reason}")


def wrap_chain(chain, safety_checker):
    """包装 Chain 添加安全检查"""
    callback = GuardAdapterCallback(safety_checker)

    original_invoke = chain.invoke

    def safe_invoke(input_data, config=None, **kwargs):
        config = config or {}
        callbacks = config.get("callbacks", [])
        callbacks.append(callback)
        config["callbacks"] = callbacks
        return original_invoke(input_data, config=config, **kwargs)

    chain.invoke = safe_invoke
    return chain


def wrap_agent(agent, safety_checker):
    """包装 Agent 添加安全检查"""
    callback = GuardAdapterCallback(safety_checker)

    if hasattr(agent, "callbacks"):
        agent.callbacks = agent.callbacks or []
        agent.callbacks.append(callback)

    return agent
'''

    def get_middleware_code(self) -> str:
        """获取中间件代码"""
        return '''
"""
GuardAdapter LangChain Middleware
用于 LangServe 等服务的中间件
"""

from typing import Any, Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class GuardAdapterMiddleware(BaseHTTPMiddleware):
    """GuardAdapter 中间件"""

    def __init__(self, app, safety_checker):
        super().__init__(app)
        self.safety_checker = safety_checker

    async def dispatch(self, request: Request, call_next: Callable):
        # 检查请求
        if request.method == "POST":
            body = await request.json()
            input_text = body.get("input", "")

            if isinstance(input_text, str):
                result = await self.safety_checker.check_input(input_text)
                if not result.is_safe:
                    return JSONResponse(
                        status_code=403,
                        content={"error": result.reason}
                    )

        # 调用下一个中间件
        response = await call_next(request)
        return response
'''

    def get_runnable_wrapper_code(self) -> str:
        """获取 LCEL Runnable 包装器代码"""
        return '''
"""
GuardAdapter LCEL Runnable Wrapper
用于 LangChain Expression Language 的安全包装器
"""

from typing import Any, Dict, Optional
from langchain_core.runnables import RunnablePassthrough, RunnableLambda


def create_safety_runnable(safety_checker):
    """创建安全检查 Runnable"""

    def check_input(data: Any) -> Any:
        """输入检查"""
        text = str(data) if not isinstance(data, str) else data
        result = safety_checker.check_input(text)
        if not result.is_safe:
            raise ValueError(f"输入安全检查失败: {result.reason}")
        return data

    def check_output(data: Any) -> Any:
        """输出检查"""
        text = str(data) if not isinstance(data, str) else data
        result = safety_checker.check_output(text)
        if not result.is_safe:
            raise ValueError(f"输出安全检查失败: {result.reason}")
        return data

    return {
        "input_checker": RunnableLambda(check_input),
        "output_checker": RunnableLambda(check_output)
    }


def wrap_runnable(runnable, safety_checker):
    """包装 Runnable 添加安全检查"""
    checkers = create_safety_runnable(safety_checker)

    return (
        checkers["input_checker"]
        | runnable
        | checkers["output_checker"]
    )
'''
