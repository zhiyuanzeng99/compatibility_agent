"""
Matcher Module - 安全工具匹配器（完整版）

功能：
- 根据项目特征推荐合适的安全工具
- 计算兼容性分数
- 多维度评估
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from .scanner import ProjectProfile, FrameworkType, LLMProvider


class SafetyTool(Enum):
    """支持的安全工具"""
    OPENGUARDRAILS = "openguardrails"
    NEMO_GUARDRAILS = "nemo_guardrails"
    LLAMA_GUARD = "llama_guard"
    LLAMA_FIREWALL = "llama_firewall"
    GUARDRAILS_AI = "guardrails_ai"
    CUSTOM = "custom"


@dataclass
class CompatibilityScore:
    """兼容性评分"""
    framework_score: float = 0.0  # 框架兼容性 0-1
    llm_score: float = 0.0        # LLM 兼容性 0-1
    feature_score: float = 0.0    # 功能覆盖度 0-1
    maintenance_score: float = 0.0  # 维护活跃度 0-1
    community_score: float = 0.0   # 社区支持度 0-1

    @property
    def total_score(self) -> float:
        """计算总分（加权平均）"""
        weights = {
            'framework': 0.25,
            'llm': 0.20,
            'feature': 0.25,
            'maintenance': 0.15,
            'community': 0.15,
        }
        return (
            self.framework_score * weights['framework'] +
            self.llm_score * weights['llm'] +
            self.feature_score * weights['feature'] +
            self.maintenance_score * weights['maintenance'] +
            self.community_score * weights['community']
        )

    @property
    def compatibility_level(self) -> str:
        """兼容性等级"""
        score = self.total_score
        if score >= 0.8:
            return "high"
        elif score >= 0.5:
            return "medium"
        else:
            return "low"


@dataclass
class ToolCapability:
    """工具能力"""
    prompt_injection_detection: bool = False
    content_safety: bool = False
    pii_detection: bool = False
    tool_call_validation: bool = False
    output_validation: bool = False
    rate_limiting: bool = False
    audit_logging: bool = False
    custom_rules: bool = False


@dataclass
class ToolRecommendation:
    """工具推荐结果"""
    tool: SafetyTool
    compatibility: CompatibilityScore
    capabilities: ToolCapability
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    integration_complexity: str = "medium"  # low, medium, high
    estimated_effort: str = ""  # 预估集成工作量

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "tool": self.tool.value,
            "compatibility_score": self.compatibility.total_score,
            "compatibility_level": self.compatibility.compatibility_level,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "integration_complexity": self.integration_complexity,
            "estimated_effort": self.estimated_effort,
        }


class ToolMatcher:
    """
    安全工具匹配器

    根据项目扫描结果推荐最合适的安全工具
    """

    # 工具与框架的兼容性矩阵
    FRAMEWORK_COMPATIBILITY = {
        SafetyTool.OPENGUARDRAILS: {
            FrameworkType.LANGCHAIN: 0.9,
            FrameworkType.LLAMAINDEX: 0.85,
            FrameworkType.HAYSTACK: 0.7,
            FrameworkType.AUTOGEN: 0.8,
            FrameworkType.CREWAI: 0.75,
            FrameworkType.CUSTOM: 0.6,
        },
        SafetyTool.NEMO_GUARDRAILS: {
            FrameworkType.LANGCHAIN: 0.95,  # 官方支持
            FrameworkType.LLAMAINDEX: 0.7,
            FrameworkType.HAYSTACK: 0.5,
            FrameworkType.AUTOGEN: 0.6,
            FrameworkType.CREWAI: 0.55,
            FrameworkType.CUSTOM: 0.5,
        },
        SafetyTool.LLAMA_GUARD: {
            FrameworkType.LANGCHAIN: 0.8,
            FrameworkType.LLAMAINDEX: 0.9,  # Meta 系列
            FrameworkType.HAYSTACK: 0.65,
            FrameworkType.AUTOGEN: 0.7,
            FrameworkType.CREWAI: 0.65,
            FrameworkType.CUSTOM: 0.6,
        },
        SafetyTool.LLAMA_FIREWALL: {
            FrameworkType.LANGCHAIN: 0.85,
            FrameworkType.LLAMAINDEX: 0.95,  # Meta 系列
            FrameworkType.HAYSTACK: 0.6,
            FrameworkType.AUTOGEN: 0.75,
            FrameworkType.CREWAI: 0.7,
            FrameworkType.CUSTOM: 0.65,
        },
        SafetyTool.GUARDRAILS_AI: {
            FrameworkType.LANGCHAIN: 0.85,
            FrameworkType.LLAMAINDEX: 0.8,
            FrameworkType.HAYSTACK: 0.75,
            FrameworkType.AUTOGEN: 0.7,
            FrameworkType.CREWAI: 0.65,
            FrameworkType.CUSTOM: 0.7,
        },
    }

    # 工具与 LLM 提供商的兼容性
    LLM_COMPATIBILITY = {
        SafetyTool.OPENGUARDRAILS: {
            LLMProvider.OPENAI: 0.95,
            LLMProvider.ANTHROPIC: 0.9,
            LLMProvider.VERTEXAI: 0.8,
            LLMProvider.AZURE: 0.85,
            LLMProvider.BEDROCK: 0.75,
            LLMProvider.LOCAL: 0.7,
        },
        SafetyTool.NEMO_GUARDRAILS: {
            LLMProvider.OPENAI: 0.95,
            LLMProvider.ANTHROPIC: 0.8,
            LLMProvider.VERTEXAI: 0.7,
            LLMProvider.AZURE: 0.85,
            LLMProvider.BEDROCK: 0.65,
            LLMProvider.LOCAL: 0.6,
        },
        SafetyTool.LLAMA_GUARD: {
            LLMProvider.OPENAI: 0.7,
            LLMProvider.ANTHROPIC: 0.65,
            LLMProvider.VERTEXAI: 0.75,
            LLMProvider.AZURE: 0.7,
            LLMProvider.BEDROCK: 0.6,
            LLMProvider.LOCAL: 0.95,  # Llama 本地部署
        },
        SafetyTool.LLAMA_FIREWALL: {
            LLMProvider.OPENAI: 0.75,
            LLMProvider.ANTHROPIC: 0.7,
            LLMProvider.VERTEXAI: 0.75,
            LLMProvider.AZURE: 0.7,
            LLMProvider.BEDROCK: 0.65,
            LLMProvider.LOCAL: 0.95,
        },
        SafetyTool.GUARDRAILS_AI: {
            LLMProvider.OPENAI: 0.9,
            LLMProvider.ANTHROPIC: 0.85,
            LLMProvider.VERTEXAI: 0.8,
            LLMProvider.AZURE: 0.85,
            LLMProvider.BEDROCK: 0.75,
            LLMProvider.LOCAL: 0.7,
        },
    }

    # 工具能力定义
    TOOL_CAPABILITIES = {
        SafetyTool.OPENGUARDRAILS: ToolCapability(
            prompt_injection_detection=True,
            content_safety=True,
            pii_detection=True,
            tool_call_validation=True,
            output_validation=True,
            rate_limiting=True,
            audit_logging=True,
            custom_rules=True,
        ),
        SafetyTool.NEMO_GUARDRAILS: ToolCapability(
            prompt_injection_detection=True,
            content_safety=True,
            pii_detection=False,
            tool_call_validation=True,
            output_validation=True,
            rate_limiting=False,
            audit_logging=True,
            custom_rules=True,
        ),
        SafetyTool.LLAMA_GUARD: ToolCapability(
            prompt_injection_detection=True,
            content_safety=True,
            pii_detection=False,
            tool_call_validation=False,
            output_validation=True,
            rate_limiting=False,
            audit_logging=False,
            custom_rules=False,
        ),
        SafetyTool.LLAMA_FIREWALL: ToolCapability(
            prompt_injection_detection=True,
            content_safety=True,
            pii_detection=True,
            tool_call_validation=True,
            output_validation=True,
            rate_limiting=False,
            audit_logging=True,
            custom_rules=True,
        ),
        SafetyTool.GUARDRAILS_AI: ToolCapability(
            prompt_injection_detection=False,
            content_safety=False,
            pii_detection=True,
            tool_call_validation=False,
            output_validation=True,
            rate_limiting=False,
            audit_logging=False,
            custom_rules=True,
        ),
    }

    # 工具维护和社区分数（基于活跃度、文档质量等）
    MAINTENANCE_SCORES = {
        SafetyTool.OPENGUARDRAILS: 0.85,
        SafetyTool.NEMO_GUARDRAILS: 0.9,  # NVIDIA 维护
        SafetyTool.LLAMA_GUARD: 0.85,     # Meta 维护
        SafetyTool.LLAMA_FIREWALL: 0.85,  # Meta 维护
        SafetyTool.GUARDRAILS_AI: 0.8,
    }

    COMMUNITY_SCORES = {
        SafetyTool.OPENGUARDRAILS: 0.75,
        SafetyTool.NEMO_GUARDRAILS: 0.9,
        SafetyTool.LLAMA_GUARD: 0.85,
        SafetyTool.LLAMA_FIREWALL: 0.8,
        SafetyTool.GUARDRAILS_AI: 0.85,
    }

    def __init__(self, project_profile: ProjectProfile):
        self.profile = project_profile

    def match(self) -> list[ToolRecommendation]:
        """
        执行匹配，返回推荐列表（按分数排序）
        """
        recommendations = []

        for tool in SafetyTool:
            if tool == SafetyTool.CUSTOM:
                continue

            recommendation = self._evaluate_tool(tool)
            recommendations.append(recommendation)

        # 按总分排序
        recommendations.sort(key=lambda r: r.compatibility.total_score, reverse=True)

        return recommendations

    def _evaluate_tool(self, tool: SafetyTool) -> ToolRecommendation:
        """评估单个工具"""
        compatibility = CompatibilityScore()
        reasons = []
        warnings = []

        # 1. 框架兼容性
        framework_compat = self.FRAMEWORK_COMPATIBILITY.get(tool, {})
        compatibility.framework_score = framework_compat.get(self.profile.framework, 0.3)

        if compatibility.framework_score >= 0.9:
            reasons.append(f"与 {self.profile.framework.value} 框架有官方/良好支持")
        elif compatibility.framework_score < 0.5:
            warnings.append(f"与 {self.profile.framework.value} 框架兼容性较低")

        # 2. LLM 兼容性
        llm_compat = self.LLM_COMPATIBILITY.get(tool, {})
        compatibility.llm_score = llm_compat.get(self.profile.llm_provider, 0.3)

        if compatibility.llm_score >= 0.9:
            reasons.append(f"与 {self.profile.llm_provider.value} 有很好的集成支持")

        # 3. 功能覆盖度
        capabilities = self.TOOL_CAPABILITIES.get(tool, ToolCapability())
        compatibility.feature_score = self._calculate_feature_score(capabilities)

        # 4. 维护和社区
        compatibility.maintenance_score = self.MAINTENANCE_SCORES.get(tool, 0.5)
        compatibility.community_score = self.COMMUNITY_SCORES.get(tool, 0.5)

        # 生成推荐理由
        self._generate_reasons(tool, capabilities, reasons, warnings)

        # 评估集成复杂度
        complexity = self._estimate_complexity(tool)

        return ToolRecommendation(
            tool=tool,
            compatibility=compatibility,
            capabilities=capabilities,
            reasons=reasons,
            warnings=warnings,
            integration_complexity=complexity,
            estimated_effort=self._estimate_effort(complexity),
        )

    def _calculate_feature_score(self, capabilities: ToolCapability) -> float:
        """计算功能覆盖度分数"""
        required_features = []

        # 根据安全需求确定需要的功能
        for req in self.profile.security_requirements:
            if req.category == "prompt_injection":
                required_features.append("prompt_injection_detection")
            elif req.category == "content_safety":
                required_features.append("content_safety")
            elif req.category == "pii":
                required_features.append("pii_detection")
            elif req.category == "tool_security":
                required_features.append("tool_call_validation")

        if not required_features:
            required_features = ["prompt_injection_detection", "content_safety"]

        # 计算覆盖率
        covered = sum(
            1 for f in required_features
            if getattr(capabilities, f, False)
        )

        return covered / len(required_features) if required_features else 0.5

    def _generate_reasons(
        self,
        tool: SafetyTool,
        capabilities: ToolCapability,
        reasons: list,
        warnings: list
    ) -> None:
        """生成推荐理由"""
        # 基于工具特点
        if tool == SafetyTool.NEMO_GUARDRAILS:
            reasons.append("NVIDIA 官方维护，文档完善")
            if self.profile.framework == FrameworkType.LANGCHAIN:
                reasons.append("与 LangChain 有原生集成支持")

        elif tool == SafetyTool.OPENGUARDRAILS:
            reasons.append("功能全面，支持自定义规则")
            reasons.append("通用性强，适用于多种场景")

        elif tool == SafetyTool.LLAMA_GUARD:
            reasons.append("Meta 开源，针对 Llama 模型优化")
            if self.profile.llm_provider == LLMProvider.LOCAL:
                reasons.append("适合本地部署的 Llama 模型")

        elif tool == SafetyTool.LLAMA_FIREWALL:
            reasons.append("Meta 最新安全框架，功能全面")
            reasons.append("支持工具调用安全检查")

        elif tool == SafetyTool.GUARDRAILS_AI:
            reasons.append("强调输出验证和结构化校验")
            reasons.append("支持自定义验证规则")

        # 基于能力生成警告
        if not capabilities.prompt_injection_detection:
            if any(r.category == "prompt_injection" for r in self.profile.security_requirements):
                warnings.append("不支持 Prompt Injection 检测")

        if not capabilities.pii_detection:
            if any(r.category == "pii" for r in self.profile.security_requirements):
                warnings.append("不支持 PII 检测")

    def _estimate_complexity(self, tool: SafetyTool) -> str:
        """评估集成复杂度"""
        # 基于框架兼容性和工具特点
        framework_compat = self.FRAMEWORK_COMPATIBILITY.get(tool, {})
        score = framework_compat.get(self.profile.framework, 0.3)

        if score >= 0.9:
            return "low"
        elif score >= 0.7:
            return "medium"
        else:
            return "high"

    def _estimate_effort(self, complexity: str) -> str:
        """估算集成工作量"""
        effort_map = {
            "low": "约 1-2 小时",
            "medium": "约 2-4 小时",
            "high": "约 4-8 小时",
        }
        return effort_map.get(complexity, "未知")

    def get_best_recommendation(self) -> Optional[ToolRecommendation]:
        """获取最佳推荐"""
        recommendations = self.match()
        return recommendations[0] if recommendations else None


def match_tools(profile: ProjectProfile) -> list[ToolRecommendation]:
    """便捷函数：匹配安全工具"""
    matcher = ToolMatcher(profile)
    return matcher.match()
