"""
Evaluator - 模型评估器

评估训练后模型的各项指标
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class EvaluationTask(Enum):
    """评估任务"""
    TOOL_SELECTION = "tool_selection"
    CODE_GENERATION = "code_generation"
    ERROR_DIAGNOSIS = "error_diagnosis"
    DEPLOYMENT_SUCCESS = "deployment_success"


@dataclass
class EvaluationMetrics:
    """核心评估指标"""
    deployment_success_rate: float = 0.0    # 目标 ≥90%
    auto_fix_rate: float = 0.0              # 目标 ≥70%
    code_accuracy: float = 0.0              # 目标 ≥95%
    tool_recommendation_accuracy: float = 0.0  # 目标 ≥85%
    avg_inference_latency_ms: float = 0.0   # 目标 ≤100ms
    cross_tool_validation_success: float = 0.0  # 目标 ≥95%
    boundary_case_accuracy: float = 0.0     # 目标 ≥85%

    def check_targets(self) -> Dict[str, bool]:
        return {
            "deployment_success_rate": self.deployment_success_rate >= 0.90,
            "auto_fix_rate": self.auto_fix_rate >= 0.70,
            "code_accuracy": self.code_accuracy >= 0.95,
            "tool_recommendation_accuracy": self.tool_recommendation_accuracy >= 0.85,
            "avg_inference_latency_ms": self.avg_inference_latency_ms <= 100,
            "cross_tool_validation_success": self.cross_tool_validation_success >= 0.95,
            "boundary_case_accuracy": self.boundary_case_accuracy >= 0.85
        }


@dataclass
class TestCase:
    """测试用例"""
    id: str
    task: EvaluationTask
    input_data: Dict[str, Any]
    expected_output: Any


@dataclass
class EvaluationResult:
    """评估结果"""
    task: EvaluationTask
    samples_evaluated: int
    passed_samples: int
    failed_cases: List[Dict] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed_samples / self.samples_evaluated if self.samples_evaluated else 0


class Evaluator:
    """模型评估器"""

    def __init__(self, model=None):
        self._model = model
        self._test_cases: Dict[EvaluationTask, List[TestCase]] = {}
        self._load_default_cases()

    def _load_default_cases(self):
        self._test_cases[EvaluationTask.TOOL_SELECTION] = [
            TestCase(
                id="ts_001",
                task=EvaluationTask.TOOL_SELECTION,
                input_data={"framework": "langchain", "llm_provider": "openai"},
                expected_output=["nemo_guardrails", "openguardrails"]
            ),
        ]

    def evaluate_task(self, task: EvaluationTask) -> EvaluationResult:
        cases = self._test_cases.get(task, [])
        passed = len(cases)  # 占位
        return EvaluationResult(task=task, samples_evaluated=len(cases), passed_samples=passed)

    def evaluate_all(self) -> EvaluationMetrics:
        metrics = EvaluationMetrics()
        ts = self.evaluate_task(EvaluationTask.TOOL_SELECTION)
        metrics.tool_recommendation_accuracy = ts.pass_rate
        cg = self.evaluate_task(EvaluationTask.CODE_GENERATION)
        metrics.code_accuracy = cg.pass_rate
        return metrics

    def generate_report(self) -> str:
        metrics = self.evaluate_all()
        targets = metrics.check_targets()
        return f"""
# GuardAdapter 评估报告

| 指标 | 当前值 | 达标 |
|------|--------|------|
| 部署成功率 | {metrics.deployment_success_rate:.1%} | {"✅" if targets["deployment_success_rate"] else "❌"} |
| 自动修复率 | {metrics.auto_fix_rate:.1%} | {"✅" if targets["auto_fix_rate"] else "❌"} |
| 代码准确率 | {metrics.code_accuracy:.1%} | {"✅" if targets["code_accuracy"] else "❌"} |
| 工具推荐准确率 | {metrics.tool_recommendation_accuracy:.1%} | {"✅" if targets["tool_recommendation_accuracy"] else "❌"} |
"""
