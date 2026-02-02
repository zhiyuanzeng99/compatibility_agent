"""
Orchestrator Module - 跨工具编排器（完整版）

功能：
- 多安全工具协同部署
- 流水线编排
- 工具间依赖管理
- 冲突检测和解决
"""

import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Set
from datetime import datetime
from enum import Enum

from .scanner import ProjectProfile
from .matcher import SafetyTool, ToolRecommendation, ToolMatcher
from .generator import CodeGenerator, GeneratedCode
from .deployer import Deployer, DeploymentResult, DeploymentStatus


class PipelineStatus(Enum):
    """流水线状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(Enum):
    """步骤类型"""
    GENERATE = "generate"
    DEPLOY = "deploy"
    VALIDATE = "validate"
    CUSTOM = "custom"


@dataclass
class PipelineStep:
    """流水线步骤"""
    id: str
    name: str
    step_type: StepType
    tool: Optional[SafetyTool] = None
    dependencies: List[str] = field(default_factory=list)
    status: PipelineStatus = PipelineStatus.PENDING
    error: Optional[str] = None
    result: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0


@dataclass
class ToolConflict:
    """工具冲突"""
    tool1: SafetyTool
    tool2: SafetyTool
    conflict_type: str  # "incompatible", "redundant", "config_conflict"
    description: str
    resolution: str


@dataclass
class PipelineResult:
    """流水线执行结果"""
    success: bool
    status: PipelineStatus
    steps: List[PipelineStep] = field(default_factory=list)
    conflicts: List[ToolConflict] = field(default_factory=list)
    deployed_tools: List[SafetyTool] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_duration_seconds: float = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": self.status.value,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "status": s.status.value,
                    "tool": s.tool.value if s.tool else None,
                    "error": s.error,
                    "duration": s.duration_seconds
                }
                for s in self.steps
            ],
            "conflicts": [
                {
                    "tool1": c.tool1.value,
                    "tool2": c.tool2.value,
                    "type": c.conflict_type,
                    "description": c.description
                }
                for c in self.conflicts
            ],
            "deployed_tools": [t.value for t in self.deployed_tools],
            "errors": self.errors,
            "total_duration_seconds": self.total_duration_seconds
        }


class CrossToolOrchestrator:
    """
    跨工具编排器 - 完整版

    支持多安全工具的协同部署和管理
    """

    # 工具兼容性矩阵（True=兼容，False=不兼容）
    COMPATIBILITY_MATRIX = {
        (SafetyTool.OPENGUARDRAILS, SafetyTool.NEMO_GUARDRAILS): True,
        (SafetyTool.OPENGUARDRAILS, SafetyTool.LLAMA_GUARD): True,
        (SafetyTool.OPENGUARDRAILS, SafetyTool.LLAMA_FIREWALL): True,
        (SafetyTool.OPENGUARDRAILS, SafetyTool.GUARDRAILS_AI): True,
        (SafetyTool.NEMO_GUARDRAILS, SafetyTool.LLAMA_GUARD): True,
        (SafetyTool.NEMO_GUARDRAILS, SafetyTool.LLAMA_FIREWALL): False,  # 功能重叠
        (SafetyTool.NEMO_GUARDRAILS, SafetyTool.GUARDRAILS_AI): True,
        (SafetyTool.LLAMA_GUARD, SafetyTool.LLAMA_FIREWALL): True,  # 同系列可协同
        (SafetyTool.LLAMA_GUARD, SafetyTool.GUARDRAILS_AI): True,
        (SafetyTool.LLAMA_FIREWALL, SafetyTool.GUARDRAILS_AI): True,
    }

    # 工具执行顺序优先级（数字越小优先级越高）
    TOOL_PRIORITY = {
        SafetyTool.LLAMA_FIREWALL: 1,     # 全面防护优先
        SafetyTool.OPENGUARDRAILS: 2,
        SafetyTool.NEMO_GUARDRAILS: 3,
        SafetyTool.LLAMA_GUARD: 4,
        SafetyTool.GUARDRAILS_AI: 5,      # 输出验证最后
    }

    def __init__(self, profile: ProjectProfile):
        self.profile = profile
        self.project_path = Path(profile.project_path)
        self._pipeline: List[PipelineStep] = []
        self._step_counter = 0

    def detect_conflicts(self, tools: List[SafetyTool]) -> List[ToolConflict]:
        """
        检测工具间冲突

        Args:
            tools: 要部署的工具列表

        Returns:
            冲突列表
        """
        conflicts = []

        for i, tool1 in enumerate(tools):
            for tool2 in tools[i+1:]:
                # 检查兼容性
                key = (tool1, tool2) if tool1.value < tool2.value else (tool2, tool1)
                is_compatible = self.COMPATIBILITY_MATRIX.get(key, True)

                if not is_compatible:
                    conflicts.append(ToolConflict(
                        tool1=tool1,
                        tool2=tool2,
                        conflict_type="incompatible",
                        description=f"{tool1.value} 和 {tool2.value} 功能重叠，不建议同时使用",
                        resolution=f"建议只使用 {tool1.value} 或 {tool2.value} 之一"
                    ))

                # 检查冗余
                if self._are_redundant(tool1, tool2):
                    conflicts.append(ToolConflict(
                        tool1=tool1,
                        tool2=tool2,
                        conflict_type="redundant",
                        description=f"{tool1.value} 和 {tool2.value} 有冗余功能",
                        resolution="可以保留，但可能增加延迟"
                    ))

        return conflicts

    def _are_redundant(self, tool1: SafetyTool, tool2: SafetyTool) -> bool:
        """检查两个工具是否功能冗余"""
        redundant_pairs = [
            (SafetyTool.LLAMA_GUARD, SafetyTool.LLAMA_FIREWALL),  # Firewall 包含 Guard
        ]
        return (tool1, tool2) in redundant_pairs or (tool2, tool1) in redundant_pairs

    def create_pipeline(
        self,
        tools: List[SafetyTool],
        recommendations: Optional[Dict[SafetyTool, ToolRecommendation]] = None
    ) -> List[PipelineStep]:
        """
        创建部署流水线

        Args:
            tools: 要部署的工具列表
            recommendations: 工具推荐结果（可选）

        Returns:
            流水线步骤列表
        """
        self._pipeline = []
        self._step_counter = 0

        # 按优先级排序
        sorted_tools = sorted(tools, key=lambda t: self.TOOL_PRIORITY.get(t, 99))

        for tool in sorted_tools:
            recommendation = recommendations.get(tool) if recommendations else None

            # 生成步骤
            gen_step = self._create_step(
                f"generate_{tool.value}",
                f"生成 {tool.value} 集成代码",
                StepType.GENERATE,
                tool
            )
            self._pipeline.append(gen_step)

            # 部署步骤
            deploy_step = self._create_step(
                f"deploy_{tool.value}",
                f"部署 {tool.value}",
                StepType.DEPLOY,
                tool,
                dependencies=[gen_step.id]
            )
            self._pipeline.append(deploy_step)

            # 验证步骤
            validate_step = self._create_step(
                f"validate_{tool.value}",
                f"验证 {tool.value} 集成",
                StepType.VALIDATE,
                tool,
                dependencies=[deploy_step.id]
            )
            self._pipeline.append(validate_step)

        return self._pipeline

    def _create_step(
        self,
        step_id: str,
        name: str,
        step_type: StepType,
        tool: Optional[SafetyTool] = None,
        dependencies: List[str] = None
    ) -> PipelineStep:
        """创建流水线步骤"""
        self._step_counter += 1
        return PipelineStep(
            id=f"{self._step_counter}_{step_id}",
            name=name,
            step_type=step_type,
            tool=tool,
            dependencies=dependencies or []
        )

    async def execute_pipeline(
        self,
        parallel: bool = False,
        stop_on_failure: bool = True
    ) -> PipelineResult:
        """
        执行流水线

        Args:
            parallel: 是否并行执行无依赖的步骤
            stop_on_failure: 失败时是否停止

        Returns:
            执行结果
        """
        result = PipelineResult(
            success=True,
            status=PipelineStatus.RUNNING
        )

        start_time = datetime.now()

        # 检测冲突
        tools = [s.tool for s in self._pipeline if s.tool]
        result.conflicts = self.detect_conflicts(list(set(tools)))

        # 执行步骤
        completed_steps: Set[str] = set()

        for step in self._pipeline:
            # 检查依赖
            if not all(dep in completed_steps for dep in step.dependencies):
                continue

            step.status = PipelineStatus.RUNNING
            step.start_time = datetime.now()

            try:
                await self._execute_step(step)
                step.status = PipelineStatus.COMPLETED
                completed_steps.add(step.id)

                if step.tool and step.step_type == StepType.DEPLOY:
                    result.deployed_tools.append(step.tool)

            except Exception as e:
                step.status = PipelineStatus.FAILED
                step.error = str(e)
                result.errors.append(f"步骤 '{step.name}' 失败: {str(e)}")

                if stop_on_failure:
                    result.success = False
                    result.status = PipelineStatus.FAILED
                    break

            finally:
                step.end_time = datetime.now()

            result.steps.append(step)

        # 完成
        if result.success:
            result.status = PipelineStatus.COMPLETED

        result.total_duration_seconds = (datetime.now() - start_time).total_seconds()

        return result

    async def _execute_step(self, step: PipelineStep) -> None:
        """执行单个步骤"""
        if step.step_type == StepType.GENERATE:
            await self._execute_generate(step)
        elif step.step_type == StepType.DEPLOY:
            await self._execute_deploy(step)
        elif step.step_type == StepType.VALIDATE:
            await self._execute_validate(step)

    async def _execute_generate(self, step: PipelineStep) -> None:
        """执行生成步骤"""
        if not step.tool:
            return

        # 创建推荐
        matcher = ToolMatcher(self.profile)
        recommendations = matcher.match()

        # 找到对应工具的推荐
        rec = next((r for r in recommendations if r.tool == step.tool), None)
        if not rec:
            raise ValueError(f"未找到 {step.tool.value} 的推荐配置")

        # 生成代码
        generator = CodeGenerator(self.profile, rec)
        code = generator.generate()

        step.result = {
            "files": [f.path for f in code.files],
            "dependencies": code.dependencies
        }

    async def _execute_deploy(self, step: PipelineStep) -> None:
        """执行部署步骤"""
        if not step.tool:
            return

        # 获取生成步骤的结果
        gen_step_id = f"{step.id.split('_')[0]}_{step.id.split('_')[1]}_generate_{step.tool.value}"

        # 重新生成并部署
        matcher = ToolMatcher(self.profile)
        recommendations = matcher.match()
        rec = next((r for r in recommendations if r.tool == step.tool), None)

        if rec:
            generator = CodeGenerator(self.profile, rec)
            code = generator.generate()

            deployer = Deployer(self.profile, code)
            result = deployer.deploy()

            if not result.success:
                raise RuntimeError(f"部署失败: {result.errors}")

            step.result = {"deployed_files": result.deployed_files}

    async def _execute_validate(self, step: PipelineStep) -> None:
        """执行验证步骤"""
        from .validator import Validator

        validator = Validator(self.profile)
        report = validator.validate()

        step.result = {
            "status": report.overall_status.value,
            "passed": report.passed_count,
            "failed": report.failed_count
        }

        if report.failed_count > 0:
            raise RuntimeError(f"验证失败: {report.failed_count} 项检查未通过")

    def get_recommended_combination(self) -> List[SafetyTool]:
        """
        获取推荐的工具组合

        Returns:
            推荐的工具列表
        """
        matcher = ToolMatcher(self.profile)
        recommendations = matcher.match()

        # 选择前 2 个兼容的工具
        selected = []
        for rec in recommendations:
            if len(selected) >= 2:
                break

            # 检查与已选工具的兼容性
            compatible = True
            for existing in selected:
                key = (existing, rec.tool) if existing.value < rec.tool.value else (rec.tool, existing)
                if not self.COMPATIBILITY_MATRIX.get(key, True):
                    compatible = False
                    break

            if compatible:
                selected.append(rec.tool)

        return selected


def orchestrate(
    profile: ProjectProfile,
    tools: List[SafetyTool]
) -> PipelineResult:
    """便捷函数：编排多工具部署"""
    orchestrator = CrossToolOrchestrator(profile)
    orchestrator.create_pipeline(tools)
    return asyncio.run(orchestrator.execute_pipeline())
