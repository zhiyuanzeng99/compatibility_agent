from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from ..core.scanner import ProjectScanner
from ..core.matcher import ToolMatcher, SafetyTool
from ..v0.pipeline import run_v0, detect_openclaw_project


@dataclass
class V2Decision:
    target_app: str
    tool: str
    reasons: List[str]


@dataclass
class V2Result:
    ok: bool
    message: str
    profile: dict
    decision: dict
    v0: Optional[dict]
    issues: List[str]
    state_path: Optional[str]


def _decide(profile_path: Path) -> V2Decision:
    ok, reason = detect_openclaw_project(profile_path)
    if ok:
        return V2Decision(
            target_app="openclaw",
            tool="openguardrails",
            reasons=["OpenClaw detected", reason],
        )
    return V2Decision(
        target_app="unknown",
        tool="openguardrails",
        reasons=["OpenClaw not detected; fallback to best-effort"],
    )


def run_v2(
    project_path: str,
    validate: bool = True,
    auto_fix: bool = False,
    dry_run: bool = False,
    state_out: Optional[str] = None,
) -> V2Result:
    project = Path(project_path).expanduser().resolve()
    scanner = ProjectScanner(str(project))
    profile = scanner.scan()

    decision = _decide(project)
    matcher = ToolMatcher(profile)
    _ = matcher.match()

    v0_result = None
    issues: List[str] = []

    if decision.target_app == "openclaw":
        v0 = run_v0(
            project_path=str(project),
            config_path=None,
            og_base_url=None,
            og_detect_url=None,
            model_id="gpt-4",
            dry_run=dry_run,
            verify=validate,
            verify_script=None,
        )
        v0_result = v0.__dict__

        if validate:
            if v0.detect_health is False:
                issues.append("detection service health check failed")
            if v0.proxy_health is False:
                issues.append("proxy service health check failed")
            if isinstance(v0.detection_result, dict) and v0.detection_result.get("status_code") == 401:
                issues.append("OG_API_KEY missing or invalid (detection unauthorized)")

    if auto_fix and issues:
        issues.append("auto_fix not implemented in V2.0 (manual action required)")

    ok = bool(v0_result) and not any("failed" in i for i in issues)

    state_path = None
    if state_out:
        state_path = str(Path(state_out).expanduser().resolve())
        payload = {
            "timestamp": datetime.now().isoformat(),
            "profile": profile.to_dict(),
            "decision": decision.__dict__,
            "v0": v0_result,
            "issues": issues,
        }
        Path(state_path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    return V2Result(
        ok=ok,
        message="v2 one-click agent completed" if ok else "v2 one-click agent needs attention",
        profile=profile.to_dict(),
        decision=decision.__dict__,
        v0=v0_result,
        issues=issues,
        state_path=state_path,
    )
