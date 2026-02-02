"""
Core Layer - 核心能力层

包含所有核心模块:
- Scanner: 项目扫描分析
- Matcher: 工具匹配推荐
- Generator: 代码生成
- Deployer: 部署执行
- Validator: 验证测试
- Fixer: 自动修复
- Lifecycle: 全流程管控
- Orchestrator: 跨工具协同
- DisasterRecovery: 容灾兜底
"""

from .scanner import ProjectScanner, ProjectProfile
from .matcher import ToolMatcher, ToolRecommendation, SafetyTool
from .generator import CodeGenerator, GeneratedCode
from .deployer import Deployer, DeploymentResult, DeploymentMode
from .validator import Validator, ValidationReport, ValidationLevel
from .fixer import Fixer, FixResult
from .lifecycle import LifecycleController, CheckpointResult
from .orchestrator import CrossToolOrchestrator, PipelineResult
from .disaster_recovery import DisasterRecovery, FailoverResult, DisasterRecoveryConfig

__all__ = [
    # Scanner
    "ProjectScanner",
    "ProjectProfile",
    # Matcher
    "ToolMatcher",
    "ToolRecommendation",
    "SafetyTool",
    # Generator
    "CodeGenerator",
    "GeneratedCode",
    # Deployer
    "Deployer",
    "DeploymentResult",
    "DeploymentMode",
    # Validator
    "Validator",
    "ValidationReport",
    "ValidationLevel",
    # Fixer
    "Fixer",
    "FixResult",
    # Lifecycle
    "LifecycleController",
    "CheckpointResult",
    # Orchestrator
    "CrossToolOrchestrator",
    "PipelineResult",
    # Disaster Recovery
    "DisasterRecovery",
    "FailoverResult",
    "DisasterRecoveryConfig",
]
