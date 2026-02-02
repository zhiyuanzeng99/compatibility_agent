"""
Adapter Agent - AI安全工具适配部署Agent（完整版）

四层两体系架构:
- 接入层 (Access Layer): api/
- 核心能力层 (Core Layer): core/
- 基础支撑层 (Infrastructure Layer): infrastructure/
- 数据与训练体系: training/
- 统一运维监控体系: monitoring/

插件系统:
- 安全工具插件: plugins/safety_tools/
- AI应用集成插件: plugins/app_integrators/
"""

__version__ = "1.0.0"
__author__ = "GuardAdapter Team"

# 核心模块
from .core.scanner import ProjectScanner, ProjectProfile
from .core.matcher import ToolMatcher, ToolRecommendation
from .core.generator import CodeGenerator, GeneratedCode
from .core.deployer import Deployer, DeploymentResult
from .core.validator import Validator, ValidationReport
from .core.fixer import Fixer, FixResult
from .core.lifecycle import LifecycleController, CheckpointResult
from .core.orchestrator import CrossToolOrchestrator, PipelineResult
from .core.disaster_recovery import DisasterRecovery, FailoverResult

# 接入层
from .api import (
    ProtocolAdapter,
    ProtocolType,
    FormatConverter,
    Router,
    Gateway,
    GatewayConfig,
)

# 监控模块
from .monitoring import (
    MetricsCollector,
    AlertManager,
    AlertLevel,
    HealthChecker,
    HealthStatus,
    Dashboard,
)

# 插件
from .plugins.base import PluginManager, BasePlugin, PluginStatus

# 安全工具插件
from .plugins.safety_tools import (
    OpenGuardrailsPlugin,
    NeMoGuardrailsPlugin,
    LlamaGuardPlugin,
    LlamaFirewallPlugin,
    GuardrailsAIPlugin,
)

# 应用集成插件
from .plugins.app_integrators import (
    LangChainIntegrator,
    LlamaIndexIntegrator,
    ClaudeBotIntegrator,
)

# 训练模块
from .training import (
    SFTTrainer,
    SFTConfig,
    DPOTrainer,
    DPOConfig,
    get_recommended_config_for_4x4090,
    DataCollector,
    RAGBuilder,
    Evaluator,
)

__all__ = [
    # Core
    "ProjectScanner",
    "ProjectProfile",
    "ToolMatcher",
    "ToolRecommendation",
    "CodeGenerator",
    "GeneratedCode",
    "Deployer",
    "DeploymentResult",
    "Validator",
    "ValidationReport",
    "Fixer",
    "FixResult",
    "LifecycleController",
    "CheckpointResult",
    "CrossToolOrchestrator",
    "PipelineResult",
    "DisasterRecovery",
    "FailoverResult",
    # API
    "ProtocolAdapter",
    "ProtocolType",
    "FormatConverter",
    "Router",
    "Gateway",
    "GatewayConfig",
    # Monitoring
    "MetricsCollector",
    "AlertManager",
    "AlertLevel",
    "HealthChecker",
    "HealthStatus",
    "Dashboard",
    # Plugins
    "PluginManager",
    "BasePlugin",
    "PluginStatus",
    # Safety Tools
    "OpenGuardrailsPlugin",
    "NeMoGuardrailsPlugin",
    "LlamaGuardPlugin",
    "LlamaFirewallPlugin",
    "GuardrailsAIPlugin",
    # Integrators
    "LangChainIntegrator",
    "LlamaIndexIntegrator",
    "ClaudeBotIntegrator",
    # Training
    "SFTTrainer",
    "SFTConfig",
    "DPOTrainer",
    "DPOConfig",
    "get_recommended_config_for_4x4090",
    "DataCollector",
    "RAGBuilder",
    "Evaluator",
]
