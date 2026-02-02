"""
LlamaIndex Integrator - LlamaIndex 框架集成插件

支持:
- Query Engine 包装
- Agent 拦截
- Tool 安全检查
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
class LlamaIndexConfig(IntegratorConfig):
    """LlamaIndex 集成配置"""
    wrap_query_engine: bool = True
    wrap_chat_engine: bool = True
    wrap_agents: bool = True


class LlamaIndexIntegrator(BaseIntegratorPlugin):
    """
    LlamaIndex 集成插件

    为 LlamaIndex 应用提供安全防护集成
    """

    NAME = "llamaindex_integrator"
    VERSION = "1.0.0"
    DESCRIPTION = "LlamaIndex 框架集成，支持 QueryEngine/ChatEngine/Agent 安全防护"
    AUTHOR = "GuardAdapter"
    FRAMEWORK_NAME = "llamaindex"

    SUPPORTED_POINTS = [
        IntegrationPoint.PRE_PROMPT,
        IntegrationPoint.PRE_LLM_CALL,
        IntegrationPoint.POST_LLM_CALL,
        IntegrationPoint.PRE_TOOL_CALL,
        IntegrationPoint.POST_RESULT,
    ]

    def __init__(self, config: Optional[LlamaIndexConfig] = None):
        super().__init__(config)
        self.li_config = config or LlamaIndexConfig(
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

        return IntegrationResult(
            success=True,
            point=point,
            modified_data=data,
            latency_ms=(time.perf_counter() - start_time) * 1000
        )

    def get_wrapper_code(self) -> str:
        """获取 LlamaIndex 包装器代码"""
        return '''
"""
GuardAdapter LlamaIndex Wrapper
自动生成的安全防护包装器
"""

from typing import Any, Optional
from llama_index.core.callbacks import CallbackManager, LlamaDebugHandler
from llama_index.core.callbacks.base import BaseCallbackHandler
from llama_index.core.callbacks.schema import CBEventType


class GuardAdapterCallbackHandler(BaseCallbackHandler):
    """GuardAdapter 回调处理器"""

    def __init__(self, safety_checker):
        super().__init__(
            event_starts_to_ignore=[],
            event_ends_to_ignore=[]
        )
        self.safety_checker = safety_checker

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[dict] = None,
        event_id: str = "",
        **kwargs
    ) -> str:
        """事件开始"""
        if event_type == CBEventType.LLM:
            # 检查 LLM 输入
            if payload and "messages" in payload:
                for msg in payload["messages"]:
                    content = msg.get("content", "")
                    result = self.safety_checker.check_input(content)
                    if not result.is_safe:
                        raise ValueError(f"输入安全检查失败: {result.reason}")

        elif event_type == CBEventType.FUNCTION_CALL:
            # 检查工具调用
            if payload:
                tool_name = payload.get("tool", {}).get("name", "unknown")
                result = self.safety_checker.check_tool_call(tool_name, payload)
                if not result.is_safe:
                    raise ValueError(f"工具调用安全检查失败: {result.reason}")

        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[dict] = None,
        event_id: str = "",
        **kwargs
    ) -> None:
        """事件结束"""
        if event_type == CBEventType.LLM:
            # 检查 LLM 输出
            if payload and "response" in payload:
                response = str(payload["response"])
                result = self.safety_checker.check_output(response)
                if not result.is_safe:
                    raise ValueError(f"输出安全检查失败: {result.reason}")

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        pass

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[dict] = None
    ) -> None:
        pass


def wrap_query_engine(query_engine, safety_checker):
    """包装 QueryEngine 添加安全检查"""
    callback_handler = GuardAdapterCallbackHandler(safety_checker)

    # 添加到 callback manager
    if hasattr(query_engine, "callback_manager"):
        query_engine.callback_manager.add_handler(callback_handler)
    else:
        query_engine.callback_manager = CallbackManager([callback_handler])

    return query_engine


def wrap_chat_engine(chat_engine, safety_checker):
    """包装 ChatEngine 添加安全检查"""
    callback_handler = GuardAdapterCallbackHandler(safety_checker)

    if hasattr(chat_engine, "callback_manager"):
        chat_engine.callback_manager.add_handler(callback_handler)
    else:
        chat_engine.callback_manager = CallbackManager([callback_handler])

    return chat_engine
'''

    def get_middleware_code(self) -> str:
        """获取中间件代码"""
        return '''
"""
GuardAdapter LlamaIndex Middleware
用于 LlamaIndex 服务的中间件
"""

from typing import Any, Callable
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


class GuardAdapterLlamaIndexMiddleware(BaseHTTPMiddleware):
    """GuardAdapter LlamaIndex 中间件"""

    def __init__(self, app, safety_checker):
        super().__init__(app)
        self.safety_checker = safety_checker

    async def dispatch(self, request: Request, call_next: Callable):
        if request.method == "POST":
            try:
                body = await request.json()
                query = body.get("query", body.get("message", ""))

                if query:
                    result = await self.safety_checker.check_input(query)
                    if not result.is_safe:
                        raise HTTPException(
                            status_code=403,
                            detail=f"安全检查失败: {result.reason}"
                        )
            except HTTPException:
                raise
            except Exception:
                pass

        response = await call_next(request)
        return response
'''
