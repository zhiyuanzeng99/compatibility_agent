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


@dataclass
class V21Result:
    ok: bool
    message: str
    app: str
    guard: str
    mode: str
    decision: dict
    steps: List[str]
    v0: Optional[dict]
    issues: List[str]
    state_path: Optional[str]


@dataclass
class V22Result:
    ok: bool
    message: str
    app: str
    guard: str
    mode: str
    decision: dict
    steps: List[str]
    artifacts: List[str]
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


def run_v21(
    project_path: str,
    app: str,
    guard: str,
    mode: str = "whitebox",
    validate: bool = True,
    dry_run: bool = False,
    state_out: Optional[str] = None,
) -> V21Result:
    project = Path(project_path).expanduser().resolve()
    app = app.strip().lower()
    guard = guard.strip().lower()
    mode = mode.strip().lower()

    steps: List[str] = []
    issues: List[str] = []
    v0_result = None

    decision = {
        "app": app,
        "guard": guard,
        "mode": mode,
        "integration": "gateway" if mode == "blackbox" else "sdk_or_middleware",
    }

    if app != "openclaw":
        issues.append("V2.1 currently supports OpenClaw only")

    if guard not in {"openguardrails", "llama_firewall"}:
        issues.append("Unsupported guard tool for V2.1")

    if mode not in {"whitebox", "blackbox"}:
        issues.append("mode must be whitebox or blackbox")

    if issues:
        return V21Result(
            ok=False,
            message="v2.1 validation failed",
            app=app,
            guard=guard,
            mode=mode,
            decision=decision,
            steps=steps,
            v0=v0_result,
            issues=issues,
            state_path=None,
        )

    if guard == "openguardrails":
        steps.append("write OpenClaw config to point to OpenGuardrails")
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
        if validate and isinstance(v0.detection_result, dict) and v0.detection_result.get("status_code") == 401:
            issues.append("OG_API_KEY missing or invalid (detection unauthorized)")
        if validate and v0.detect_health is False:
            issues.append("detection service health check failed")
        if validate and v0.proxy_health is False:
            issues.append("proxy service health check failed")

    if guard == "llama_firewall":
        steps.append("prepare LlamaFirewall integration stub (whitebox SDK or blackbox gateway)")
        steps.append("manual integration required for LlamaFirewall in V2.1")
        issues.append("LlamaFirewall adapter not implemented yet (V2.2)")

    ok = v0_result is not None and not issues

    state_path = None
    if state_out:
        state_path = str(Path(state_out).expanduser().resolve())
        payload = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "steps": steps,
            "v0": v0_result,
            "issues": issues,
        }
        Path(state_path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    return V21Result(
        ok=ok,
        message="v2.1 completed" if ok else "v2.1 needs attention",
        app=app,
        guard=guard,
        mode=mode,
        decision=decision,
        steps=steps,
        v0=v0_result,
        issues=issues,
        state_path=state_path,
    )


def _write_file(path: Path, content: str, dry_run: bool) -> Optional[str]:
    if dry_run:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def run_v22(
    project_path: str,
    app: str,
    guard: str,
    mode: str = "whitebox",
    validate: bool = True,
    dry_run: bool = False,
    out_dir: Optional[str] = None,
    state_out: Optional[str] = None,
) -> V22Result:
    project = Path(project_path).expanduser().resolve()
    app = app.strip().lower()
    guard = guard.strip().lower()
    mode = mode.strip().lower()

    steps: List[str] = []
    issues: List[str] = []
    artifacts: List[str] = []
    v0_result = None

    decision = {
        "app": app,
        "guard": guard,
        "mode": mode,
        "integration": "gateway" if mode == "blackbox" else "sdk_or_middleware",
    }

    if mode not in {"whitebox", "blackbox"}:
        issues.append("mode must be whitebox or blackbox")

    if app not in {"openclaw", "custom"}:
        issues.append("V2.2 supports app=openclaw or app=custom")

    if guard not in {"openguardrails", "llama_firewall"}:
        issues.append("V2.2 supports guard=openguardrails or guard=llama_firewall")

    output_dir = Path(out_dir).expanduser().resolve() if out_dir else project / ".guardadapter"

    if issues:
        return V22Result(
            ok=False,
            message="v2.2 validation failed",
            app=app,
            guard=guard,
            mode=mode,
            decision=decision,
            steps=steps,
            artifacts=artifacts,
            v0=v0_result,
            issues=issues,
            state_path=None,
        )

    if guard == "openguardrails" and app == "openclaw" and mode == "whitebox":
        steps.append("write OpenClaw config to point to OpenGuardrails (whitebox)")
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
        if validate and isinstance(v0.detection_result, dict) and v0.detection_result.get("status_code") == 401:
            issues.append("OG_API_KEY missing or invalid (detection unauthorized)")
        if validate and v0.detect_health is False:
            issues.append("detection service health check failed")
        if validate and v0.proxy_health is False:
            issues.append("proxy service health check failed")

    if mode == "blackbox":
        steps.append("generate gateway config for blackbox integration")
        gateway_payload = {
            "app": app,
            "guard": guard,
            "mode": "blackbox",
            "upstream": {
                "base_url": "http://your-app-host",
                "protocol": "http",
            },
            "guardrails": {
                "provider": guard,
                "base_url": "http://127.0.0.1:5002/v1" if guard == "openguardrails" else "http://your-llama-firewall",
            },
        }
        gateway_path = output_dir / "gateway_config.json"
        written = _write_file(gateway_path, json.dumps(gateway_payload, indent=2, ensure_ascii=False), dry_run)
        if written:
            artifacts.append(written)

    if guard == "llama_firewall":
        steps.append("generate LlamaFirewall integration stub")
        stub = \"\"\"# LlamaFirewall integration stub\n# TODO: implement real SDK or gateway wiring\n\"\"\"\n        stub_path = output_dir / "llama_firewall_stub.py"
        written = _write_file(stub_path, stub, dry_run)
        if written:
            artifacts.append(written)
        issues.append("LlamaFirewall adapter is stub-only in V2.2")

    if not artifacts and v0_result is None:
        issues.append("no artifacts generated; check inputs")

    ok = not issues

    state_path = None
    if state_out:
        state_path = str(Path(state_out).expanduser().resolve())
        payload = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "steps": steps,
            "artifacts": artifacts,
            "v0": v0_result,
            "issues": issues,
        }
        Path(state_path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    return V22Result(
        ok=ok,
        message="v2.2 completed" if ok else "v2.2 needs attention",
        app=app,
        guard=guard,
        mode=mode,
        decision=decision,
        steps=steps,
        artifacts=artifacts,
        v0=v0_result,
        issues=issues,
        state_path=state_path,
    )
