from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict

from ..v0.pipeline import detect_openclaw_project


@dataclass
class PlanStep:
    id: str
    title: str
    details: str


@dataclass
class DeploymentPlan:
    target_app: str
    guard: str
    mode: str
    steps: List[PlanStep] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_app": self.target_app,
            "guard": self.guard,
            "mode": self.mode,
            "steps": [s.__dict__ for s in self.steps],
            "risks": self.risks,
            "notes": self.notes,
            "artifacts": self.artifacts,
        }


def _basic_plan(app: str, guard: str, mode: str) -> DeploymentPlan:
    plan = DeploymentPlan(target_app=app, guard=guard, mode=mode)
    plan.steps.append(PlanStep("scan", "扫描项目", "读取依赖与入口点，确认集成方式"))
    plan.steps.append(PlanStep("integrate", "生成集成配置", "写入配置或生成 gateway 文件"))
    plan.steps.append(PlanStep("deploy", "部署与重启", "应用配置并重启相关服务"))
    plan.steps.append(PlanStep("validate", "健康检查", "验证 guard 服务与样例检测"))
    return plan


def generate_plan(project_path: str, guard: str, mode: str = "whitebox") -> DeploymentPlan:
    project = Path(project_path).expanduser().resolve()
    app = "openclaw" if detect_openclaw_project(project)[0] else "custom"

    plan = _basic_plan(app, guard, mode)
    if app == "openclaw" and guard == "openguardrails":
        plan.notes.append("OpenClaw detected, use OpenGuardrails proxy config")
        plan.artifacts.append("~/.openclaw/openclaw.json")
    if mode == "blackbox":
        plan.notes.append("Blackbox mode uses gateway integration")
        plan.artifacts.append("gateway_config.json")

    if guard == "llama_firewall":
        plan.risks.append("LlamaFirewall adapter may require manual wiring")

    return plan


def build_planner_prompt(context: Dict[str, str]) -> str:
    """
    Build a prompt that can be used by a real LLM planner later.
    Currently returns a plain template for future wiring.
    """
    return (
        "You are a deployment agent. Given project info and a guard tool, "
        "produce an actionable deployment plan (steps + risks + artifacts).\n\n"
        f"PROJECT: {context.get('project','')}\n"
        f"GUARD: {context.get('guard','')}\n"
        f"MODE: {context.get('mode','')}\n"
        f"NOTES: {context.get('notes','')}\n"
    )
