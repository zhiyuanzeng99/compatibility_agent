from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from ..v2.pipeline import run_v22
from .planner import DeploymentPlan


@dataclass
class ExecutionResult:
    ok: bool
    message: str
    issues: List[str]
    v22: Optional[dict]


def execute_plan(
    plan: DeploymentPlan,
    project_path: str,
    validate: bool = True,
    dry_run: bool = False,
    out_dir: Optional[str] = None,
) -> ExecutionResult:
    """
    Execute a deployment plan by delegating to V2.2 (gateway artifacts + stubs).
    This keeps V3 minimal and lets us evolve plan-to-action mapping later.
    """
    result = run_v22(
        project_path=project_path,
        app=plan.target_app,
        guard=plan.guard,
        mode=plan.mode,
        validate=validate,
        dry_run=dry_run,
        out_dir=out_dir,
        state_out=None,
    )
    return ExecutionResult(
        ok=result.ok,
        message=result.message,
        issues=result.issues,
        v22=result.__dict__,
    )
