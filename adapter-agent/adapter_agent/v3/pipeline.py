from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from ..core.scanner import ProjectScanner
from .planner import generate_plan, DeploymentPlan
from .executor import execute_plan, ExecutionResult


@dataclass
class V3Result:
    ok: bool
    message: str
    plan: dict
    execution: Optional[dict]
    issues: List[str]
    state_path: Optional[str]


def run_v3(
    project_path: str,
    guard: str,
    mode: str = "whitebox",
    validate: bool = True,
    dry_run: bool = False,
    plan_only: bool = False,
    out_dir: Optional[str] = None,
    state_out: Optional[str] = None,
) -> V3Result:
    project = Path(project_path).expanduser().resolve()
    scanner = ProjectScanner(str(project))
    _ = scanner.scan()

    plan: DeploymentPlan = generate_plan(str(project), guard=guard, mode=mode)
    execution: Optional[ExecutionResult] = None
    issues: List[str] = []

    if not plan_only:
        execution = execute_plan(
            plan=plan,
            project_path=str(project),
            validate=validate,
            dry_run=dry_run,
            out_dir=out_dir,
        )
        issues.extend(execution.issues)

    ok = execution.ok if execution else True
    message = "v3 agent completed" if ok else "v3 agent needs attention"

    state_path = None
    if state_out:
        state_path = str(Path(state_out).expanduser().resolve())
        payload = {
            "timestamp": datetime.now().isoformat(),
            "plan": plan.to_dict(),
            "execution": execution.__dict__ if execution else None,
            "issues": issues,
        }
        Path(state_path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    return V3Result(
        ok=ok,
        message=message,
        plan=plan.to_dict(),
        execution=execution.__dict__ if execution else None,
        issues=issues,
        state_path=state_path,
    )
