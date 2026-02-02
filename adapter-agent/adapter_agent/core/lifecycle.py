"""
Lifecycle Module - 生命周期控制器（完整版）

功能：
- 管理适配全流程
- 检查点和恢复
- 状态持久化
- 进度跟踪
"""

import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from enum import Enum

from .scanner import ProjectProfile
from .matcher import ToolRecommendation
from .generator import GeneratedCode
from .deployer import DeploymentResult
from .validator import ValidationReport


class LifecyclePhase(Enum):
    """生命周期阶段"""
    INITIALIZED = "initialized"
    SCANNING = "scanning"
    SCANNED = "scanned"
    MATCHING = "matching"
    MATCHED = "matched"
    GENERATING = "generating"
    GENERATED = "generated"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    VALIDATING = "validating"
    VALIDATED = "validated"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class LifecycleEvent(Enum):
    """生命周期事件"""
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_RESTORED = "checkpoint_restored"
    ROLLBACK_INITIATED = "rollback_initiated"
    ROLLBACK_COMPLETED = "rollback_completed"


@dataclass
class PhaseResult:
    """阶段执行结果"""
    phase: LifecyclePhase
    success: bool
    duration_seconds: float = 0.0
    error: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Checkpoint:
    """检查点"""
    id: str
    phase: LifecyclePhase
    timestamp: str
    project_path: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "phase": self.phase.value,
            "timestamp": self.timestamp,
            "project_path": self.project_path,
            "data": self.data
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(
            id=data["id"],
            phase=LifecyclePhase(data["phase"]),
            timestamp=data["timestamp"],
            project_path=data["project_path"],
            data=data.get("data", {})
        )


@dataclass
class CheckpointResult:
    """检查点操作结果"""
    success: bool
    checkpoint_id: Optional[str] = None
    checkpoint_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class LifecycleState:
    """生命周期状态"""
    project_path: str
    current_phase: LifecyclePhase = LifecyclePhase.INITIALIZED
    phase_history: List[PhaseResult] = field(default_factory=list)
    checkpoints: List[str] = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # 各阶段数据
    profile: Optional[Dict] = None
    recommendations: Optional[List[Dict]] = None
    generated_code: Optional[Dict] = None
    deployment_result: Optional[Dict] = None
    validation_report: Optional[Dict] = None

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "current_phase": self.current_phase.value,
            "phase_history": [
                {
                    "phase": r.phase.value,
                    "success": r.success,
                    "duration": r.duration_seconds,
                    "error": r.error
                }
                for r in self.phase_history
            ],
            "checkpoints": self.checkpoints,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "profile": self.profile,
            "recommendations": self.recommendations,
            "generated_code": self.generated_code,
            "deployment_result": self.deployment_result,
            "validation_report": self.validation_report
        }


class LifecycleController:
    """
    生命周期控制器 - 完整版

    管理适配器的完整执行流程，支持：
    - 阶段性执行
    - 检查点创建和恢复
    - 状态持久化
    - 回滚支持
    """

    def __init__(self, project_path: str, checkpoint_dir: Optional[str] = None):
        self.project_path = Path(project_path)
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else self.project_path / ".adapter_checkpoints"
        self.state = LifecycleState(project_path=str(self.project_path))
        self._event_handlers: Dict[LifecycleEvent, List[Callable]] = {}

        # 确保检查点目录存在
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def on(self, event: LifecycleEvent, handler: Callable) -> None:
        """注册事件处理器"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def _emit(self, event: LifecycleEvent, data: Dict[str, Any] = None) -> None:
        """触发事件"""
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(event, data or {})
                except Exception:
                    pass

    def execute_phase(
        self,
        phase: LifecyclePhase,
        action: Callable[[], Any],
        create_checkpoint: bool = True
    ) -> PhaseResult:
        """
        执行生命周期阶段

        Args:
            phase: 目标阶段
            action: 阶段执行函数
            create_checkpoint: 是否创建检查点

        Returns:
            阶段执行结果
        """
        self._emit(LifecycleEvent.PHASE_STARTED, {"phase": phase.value})

        start_time = datetime.now()
        result = PhaseResult(phase=phase, success=True)

        try:
            # 执行阶段动作
            data = action()
            result.data = data if isinstance(data, dict) else {"result": data}

            # 更新状态
            self.state.current_phase = phase
            self._update_state_data(phase, result.data)

            # 创建检查点
            if create_checkpoint:
                self.create_checkpoint()

            self._emit(LifecycleEvent.PHASE_COMPLETED, {"phase": phase.value})

        except Exception as e:
            result.success = False
            result.error = str(e)
            self._emit(LifecycleEvent.PHASE_FAILED, {"phase": phase.value, "error": str(e)})

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        self.state.phase_history.append(result)

        return result

    def _update_state_data(self, phase: LifecyclePhase, data: Dict) -> None:
        """更新状态数据"""
        if phase == LifecyclePhase.SCANNED:
            self.state.profile = data.get("profile")
        elif phase == LifecyclePhase.MATCHED:
            self.state.recommendations = data.get("recommendations")
        elif phase == LifecyclePhase.GENERATED:
            self.state.generated_code = data.get("generated_code")
        elif phase == LifecyclePhase.DEPLOYED:
            self.state.deployment_result = data.get("deployment_result")
        elif phase == LifecyclePhase.VALIDATED:
            self.state.validation_report = data.get("validation_report")

    def create_checkpoint(self) -> CheckpointResult:
        """创建检查点"""
        try:
            # 生成检查点 ID
            checkpoint_id = self._generate_checkpoint_id()

            checkpoint = Checkpoint(
                id=checkpoint_id,
                phase=self.state.current_phase,
                timestamp=datetime.now().isoformat(),
                project_path=str(self.project_path),
                data=self.state.to_dict()
            )

            # 保存检查点
            checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)

            self.state.checkpoints.append(checkpoint_id)

            self._emit(LifecycleEvent.CHECKPOINT_CREATED, {"checkpoint_id": checkpoint_id})

            return CheckpointResult(
                success=True,
                checkpoint_id=checkpoint_id,
                checkpoint_path=str(checkpoint_path)
            )

        except Exception as e:
            return CheckpointResult(success=False, error=str(e))

    def restore_checkpoint(self, checkpoint_id: str) -> CheckpointResult:
        """恢复检查点"""
        try:
            checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"

            if not checkpoint_path.exists():
                return CheckpointResult(success=False, error="检查点不存在")

            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            checkpoint = Checkpoint.from_dict(data)

            # 恢复状态
            self.state.current_phase = checkpoint.phase
            state_data = checkpoint.data
            self.state.profile = state_data.get("profile")
            self.state.recommendations = state_data.get("recommendations")
            self.state.generated_code = state_data.get("generated_code")
            self.state.deployment_result = state_data.get("deployment_result")
            self.state.validation_report = state_data.get("validation_report")

            self._emit(LifecycleEvent.CHECKPOINT_RESTORED, {"checkpoint_id": checkpoint_id})

            return CheckpointResult(
                success=True,
                checkpoint_id=checkpoint_id,
                checkpoint_path=str(checkpoint_path)
            )

        except Exception as e:
            return CheckpointResult(success=False, error=str(e))

    def get_latest_checkpoint(self) -> Optional[str]:
        """获取最新检查点 ID"""
        if self.state.checkpoints:
            return self.state.checkpoints[-1]

        # 从文件系统查找
        checkpoints = list(self.checkpoint_dir.glob("*.json"))
        if checkpoints:
            latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
            return latest.stem

        return None

    def list_checkpoints(self) -> List[Dict]:
        """列出所有检查点"""
        checkpoints = []

        for cp_file in self.checkpoint_dir.glob("*.json"):
            try:
                with open(cp_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                checkpoints.append({
                    "id": data["id"],
                    "phase": data["phase"],
                    "timestamp": data["timestamp"],
                    "path": str(cp_file)
                })
            except Exception:
                pass

        return sorted(checkpoints, key=lambda x: x["timestamp"], reverse=True)

    def _generate_checkpoint_id(self) -> str:
        """生成检查点 ID"""
        data = f"{self.project_path}:{self.state.current_phase.value}:{datetime.now().isoformat()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    def get_progress(self) -> Dict[str, Any]:
        """获取执行进度"""
        phases = list(LifecyclePhase)
        current_idx = phases.index(self.state.current_phase)
        total = len(phases) - 2  # 排除 FAILED 和 ROLLED_BACK

        return {
            "current_phase": self.state.current_phase.value,
            "progress_percent": min(100, int((current_idx / total) * 100)),
            "completed_phases": [p.phase.value for p in self.state.phase_history if p.success],
            "failed_phases": [p.phase.value for p in self.state.phase_history if not p.success],
            "total_duration_seconds": sum(p.duration_seconds for p in self.state.phase_history)
        }

    def run_full_lifecycle(
        self,
        profile: ProjectProfile,
        recommendation: ToolRecommendation,
        auto_deploy: bool = True,
        auto_validate: bool = True
    ) -> Dict[str, Any]:
        """
        运行完整生命周期

        Returns:
            最终结果字典
        """
        from .generator import CodeGenerator
        from .deployer import Deployer
        from .validator import Validator

        results = {}
        self.state.start_time = datetime.now().isoformat()

        # 阶段 1: 扫描已完成（使用传入的 profile）
        self.execute_phase(
            LifecyclePhase.SCANNED,
            lambda: {"profile": profile.to_dict()},
            create_checkpoint=True
        )
        results["profile"] = profile

        # 阶段 2: 匹配已完成（使用传入的 recommendation）
        self.execute_phase(
            LifecyclePhase.MATCHED,
            lambda: {"recommendations": [recommendation.to_dict()]},
            create_checkpoint=True
        )
        results["recommendation"] = recommendation

        # 阶段 3: 生成代码
        def generate():
            generator = CodeGenerator(profile, recommendation)
            code = generator.generate()
            return {"generated_code": code.to_dict()}

        gen_result = self.execute_phase(
            LifecyclePhase.GENERATED,
            generate,
            create_checkpoint=True
        )

        if not gen_result.success:
            self.state.current_phase = LifecyclePhase.FAILED
            results["error"] = gen_result.error
            return results

        # 获取生成的代码对象
        generator = CodeGenerator(profile, recommendation)
        generated_code = generator.generate()
        results["generated_code"] = generated_code

        # 阶段 4: 部署
        if auto_deploy:
            def deploy():
                deployer = Deployer(profile, generated_code)
                result = deployer.deploy()
                return {"deployment_result": result.to_dict()}

            deploy_result = self.execute_phase(
                LifecyclePhase.DEPLOYED,
                deploy,
                create_checkpoint=True
            )

            if not deploy_result.success:
                self.state.current_phase = LifecyclePhase.FAILED
                results["error"] = deploy_result.error
                return results

            deployer = Deployer(profile, generated_code)
            deployment = deployer.deploy()
            results["deployment"] = deployment

        # 阶段 5: 验证
        if auto_validate:
            def validate():
                validator = Validator(profile)
                report = validator.validate()
                return {"validation_report": report.to_dict()}

            val_result = self.execute_phase(
                LifecyclePhase.VALIDATED,
                validate,
                create_checkpoint=True
            )

            validator = Validator(profile)
            validation = validator.validate()
            results["validation"] = validation

        # 完成
        self.state.current_phase = LifecyclePhase.COMPLETED
        self.state.end_time = datetime.now().isoformat()

        return results


def create_controller(project_path: str) -> LifecycleController:
    """便捷函数：创建生命周期控制器"""
    return LifecycleController(project_path)
