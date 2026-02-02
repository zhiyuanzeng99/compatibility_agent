"""
App Integrators - AI应用集成插件

支持的AI应用框架:
- LangChain
- LlamaIndex
- Haystack
- AutoGen
- CrewAI
- ClaudeBot (Anthropic Claude)
"""

from .base_integrator import BaseIntegratorPlugin, IntegrationResult, IntegrationPoint
from .langchain_integrator import LangChainIntegrator
from .llamaindex_integrator import LlamaIndexIntegrator
from .claudebot_integrator import ClaudeBotIntegrator

__all__ = [
    "BaseIntegratorPlugin",
    "IntegrationResult",
    "IntegrationPoint",
    "LangChainIntegrator",
    "LlamaIndexIntegrator",
    "ClaudeBotIntegrator",
]
