from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from ..core.scanner import ProjectScanner, ProjectProfile
from ..core.matcher import ToolMatcher, SafetyTool, ToolRecommendation
from ..core.generator import CodeGenerator, GeneratedCode
from ..core.deployer import Deployer, DeploymentMode, DeploymentResult
from ..core.orchestrator import PipelineResult, orchestrate
from ..core.lifecycle import LifecycleController, LifecyclePhase
from ..core.validator import Validator, ValidationReport
from ..core.fixer import Fixer, FixResult
from ..v0.pipeline import run_v0


@dataclass
class V1Config:
    project_path: Path
    output_dir: Optional[Path] = None
    tool: Optional[SafetyTool] = None
    tools: Optional[List[SafetyTool]] = None
    deploy: bool = True
    dry_run: bool = False
    mode: DeploymentMode = DeploymentMode.DIRECT
    validate: bool = True
    auto_fix: bool = False
    use_lifecycle: bool = True
    one_click: bool = False
    target_app: Optional[str] = None


@dataclass
class V1Result:
    ok: bool
    message: str
    profile: dict
    recommendations: list[dict]
    selected_tool: Optional[str]
    generated: Optional[dict]
    deployment: Optional[dict]
    validation: Optional[dict]
    fixes: Optional[dict]
    pipeline: Optional[dict]
    lifecycle: Optional[dict]
    details: Optional[dict]


def _select_tool(profile: ProjectProfile, tool: Optional[SafetyTool]) -> ToolRecommendation:
    matcher = ToolMatcher(profile)
    if tool:
        return matcher._evaluate_tool(tool)  # type: ignore[attr-defined]
    best = matcher.get_best_recommendation()
    if not best:
        raise RuntimeError("no tool recommendation found")
    return best


def run_v1(
    project_path: str,
    output_dir: Optional[str] = None,
    tool: Optional[str] = None,
    tools: Optional[str] = None,
    deploy: bool = True,
    dry_run: bool = False,
    mode: str = "direct",
    validate: bool = True,
    auto_fix: bool = False,
    use_lifecycle: bool = True,
    one_click: bool = False,
    target_app: Optional[str] = None,
) -> V1Result:
    project = Path(project_path).expanduser().resolve()
    scanner = ProjectScanner(str(project))
    profile = scanner.scan()

    matcher = ToolMatcher(profile)
    recommendations = matcher.match()

    selected_tool = SafetyTool(tool) if tool else None
    target = (target_app or "").strip().lower() if target_app else None

    if one_click or (target == "openclaw" and (tool is None or tool == "openguardrails")):
        v0_result = run_v0(
            project_path=str(project),
            config_path=None,
            og_base_url=None,
            og_detect_url=None,
            model_id="gpt-4",
            dry_run=dry_run,
            verify=validate,
            verify_script=None,
        )
        return V1Result(
            ok=v0_result.ok,
            message="v1 one-click (openclaw+openguardrails) completed" if v0_result.ok else v0_result.message,
            profile=profile.to_dict(),
            recommendations=[r.to_dict() for r in recommendations],
            selected_tool="openguardrails",
            generated={
                "config_written": v0_result.config_written,
                "backup_path": str(v0_result.backup_path) if v0_result.backup_path else None,
            },
            deployment=None,
            validation=None,
            fixes=None,
            pipeline=None,
            lifecycle=None,
            details={
                "detect_health": v0_result.detect_health,
                "proxy_health": v0_result.proxy_health,
                "detection_result": v0_result.detection_result,
                "verify_script_ok": v0_result.verify_script_ok,
                "verify_script_output": v0_result.verify_script_output,
            },
        )

    lifecycle: Optional[LifecycleController] = None
    if use_lifecycle:
        lifecycle = LifecycleController(str(project))
        lifecycle.state.start_time = datetime.now().isoformat()
        lifecycle.execute_phase(
            LifecyclePhase.SCANNED,
            lambda: {"profile": profile.to_dict()},
            create_checkpoint=True,
        )
        lifecycle.execute_phase(
            LifecyclePhase.MATCHED,
            lambda: {"recommendations": [r.to_dict() for r in recommendations]},
            create_checkpoint=True,
        )

    pipeline_result: Optional[PipelineResult] = None
    if tools:
        tool_list = [SafetyTool(t.strip()) for t in tools.split(",") if t.strip()]
        if not tool_list:
            return V1Result(
                ok=False,
                message="v1 multi-tool pipeline failed: empty tools list",
                profile=profile.to_dict(),
                recommendations=[r.to_dict() for r in recommendations],
                selected_tool=None,
                generated=None,
                deployment=None,
                validation=None,
                fixes=None,
                pipeline=None,
                lifecycle=lifecycle.state.to_dict() if lifecycle else None,
            )
        pipeline_result = orchestrate(profile, tool_list)
        ok = pipeline_result.success
        if lifecycle:
            lifecycle.state.end_time = datetime.now().isoformat()
        return V1Result(
            ok=ok,
            message="v1 multi-tool pipeline completed" if ok else "v1 multi-tool pipeline failed",
            profile=profile.to_dict(),
            recommendations=[r.to_dict() for r in recommendations],
            selected_tool=",".join([t.value for t in tool_list]) if tool_list else None,
            generated=None,
            deployment=None,
            validation=None,
            fixes=None,
            pipeline=pipeline_result.to_dict(),
            lifecycle=lifecycle.state.to_dict() if lifecycle else None,
            details=None,
        )

    recommendation = _select_tool(profile, selected_tool)
    output = Path(output_dir).expanduser().resolve() if output_dir else None
    generator = CodeGenerator(profile, recommendation, str(output) if output else None)
    generated: GeneratedCode = generator.generate()

    deployment_result: Optional[DeploymentResult] = None
    if deploy and generated.is_success and not dry_run:
        deployer = Deployer(profile, generated, DeploymentMode(mode))
        deployment_result = deployer.deploy(install_deps=False, create_backup=True, force=False)

    validation_report: Optional[ValidationReport] = None
    if validate and generated.is_success:
        validator = Validator(profile, deployment_result)
        validation_report = validator.validate()

    fix_result: Optional[FixResult] = None
    if auto_fix and validation_report and validation_report.failed_count > 0:
        fixer = Fixer(profile, validation_report)
        fix_result = fixer.fix(auto_fix=True)

    if lifecycle:
        if generated.is_success:
            lifecycle.execute_phase(
                LifecyclePhase.GENERATED,
                lambda: {"generated_code": generated.to_dict()},
                create_checkpoint=True,
            )
        if deployment_result:
            lifecycle.execute_phase(
                LifecyclePhase.DEPLOYED,
                lambda: {"deployment_result": deployment_result.to_dict()},
                create_checkpoint=True,
            )
        if validation_report:
            lifecycle.execute_phase(
                LifecyclePhase.VALIDATED,
                lambda: {"validation_report": validation_report.to_dict()},
                create_checkpoint=True,
            )
        lifecycle.state.end_time = datetime.now().isoformat()

    ok = generated.is_success
    return V1Result(
        ok=ok,
        message="v1 pipeline completed" if ok else "v1 generation failed",
        profile=profile.to_dict(),
        recommendations=[r.to_dict() for r in recommendations],
        selected_tool=recommendation.tool.value if recommendation else None,
        generated=generated.to_dict() if generated else None,
        deployment=deployment_result.to_dict() if deployment_result else None,
        validation=validation_report.to_dict() if validation_report else None,
        fixes=fix_result.to_dict() if fix_result else None,
        pipeline=pipeline_result.to_dict() if pipeline_result else None,
        lifecycle=lifecycle.state.to_dict() if lifecycle else None,
        details=None,
    )
