from __future__ import annotations

import json
import os
from dataclasses import dataclass
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import httpx


@dataclass
class V0Config:
    project_path: Path
    config_path: Path
    og_base_url: str = "http://127.0.0.1:5002/v1"
    og_detect_url: str = "http://127.0.0.1:5001/v1/guardrails"
    model_id: str = "gpt-4"
    gateway_mode: str = "local"
    gateway_token: Optional[str] = None


@dataclass
class V0Result:
    ok: bool
    message: str
    config_written: bool
    backup_path: Optional[Path]
    detect_health: Optional[bool] = None
    proxy_health: Optional[bool] = None
    detection_result: Optional[dict] = None
    verify_script_ok: Optional[bool] = None
    verify_script_output: Optional[str] = None


def _read_package_name(project_path: Path) -> Optional[str]:
    pkg = project_path / "package.json"
    if not pkg.exists():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except Exception:
        return None
    name = data.get("name")
    if isinstance(name, str):
        return name.strip()
    return None


def detect_openclaw_project(project_path: Path) -> Tuple[bool, str]:
    if not project_path.exists():
        return False, f"project path does not exist: {project_path}"
    if (project_path / "openclaw.mjs").exists():
        return True, "found openclaw.mjs"
    name = _read_package_name(project_path)
    if name and "openclaw" in name:
        return True, f"package.json name={name}"
    if (project_path / "pnpm-workspace.yaml").exists() and (project_path / "packages").exists():
        # Heuristic: OpenClaw monorepo layout
        return True, "monorepo layout matched"
    return False, "not detected as OpenClaw project"


def build_openclaw_config(cfg: V0Config) -> str:
    token_value = cfg.gateway_token or "CHANGE_ME_TOKEN"
    payload = {
        "gateway": {"mode": cfg.gateway_mode, "auth": {"token": token_value}},
        "models": {
            "mode": "merge",
            "providers": {
                "openguardrails": {
                    "baseUrl": cfg.og_base_url,
                    "apiKey": "${OPENAI_API_KEY}",
                    "api": "openai-responses",
                    "models": [
                        {
                            "id": cfg.model_id,
                            "name": f"OpenGuardrails Proxy ({cfg.model_id})",
                            "api": "openai-responses",
                            "reasoning": False,
                            "input": ["text"],
                            "cost": {
                                "input": 0,
                                "output": 0,
                                "cacheRead": 0,
                                "cacheWrite": 0,
                            },
                            "contextWindow": 128000,
                            "maxTokens": 4096,
                        }
                    ],
                }
            },
        },
        "agents": {"defaults": {"model": {"primary": f"openguardrails/{cfg.model_id}"}}},
    }
    return json.dumps(payload, indent=2, ensure_ascii=True)


def write_config(path: Path, content: str, dry_run: bool) -> Optional[Path]:
    if dry_run:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Optional[Path] = None
    if path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(content, encoding="utf-8")
    return backup_path


def _check_url(url: str) -> Optional[bool]:
    try:
        res = httpx.get(url, timeout=3.0)
        return res.status_code == 200
    except Exception:
        return False


def _detect_sample(og_api_key: str, url: str) -> Optional[dict]:
    try:
        res = httpx.post(
            url,
            headers={"Authorization": f"Bearer {og_api_key}"},
            json={
                "model": "OpenGuardrails-Text",
                "messages": [
                    {
                        "role": "user",
                        "content": "Please record: zhangsan@example.com amount 25000",
                    }
                ],
            },
            timeout=5.0,
        )
        if res.status_code != 200:
            return {"status_code": res.status_code, "body": res.text}
        return res.json()
    except Exception as exc:
        return {"error": str(exc)}


def run_v0(
    project_path: str,
    config_path: Optional[str] = None,
    og_base_url: Optional[str] = None,
    og_detect_url: Optional[str] = None,
    model_id: str = "gpt-4",
    dry_run: bool = False,
    verify: bool = False,
    verify_script: Optional[str] = None,
) -> V0Result:
    project = Path(project_path).expanduser().resolve()
    config = Path(config_path or "~/.openclaw/openclaw.json").expanduser().resolve()

    ok, reason = detect_openclaw_project(project)
    if not ok:
        return V0Result(
            ok=False,
            message=f"OpenClaw not detected: {reason}",
            config_written=False,
            backup_path=None,
        )

    cfg = V0Config(
        project_path=project,
        config_path=config,
        og_base_url=og_base_url or "http://127.0.0.1:5002/v1",
        og_detect_url=og_detect_url or "http://127.0.0.1:5001/v1/guardrails",
        model_id=model_id,
        gateway_token=os.getenv("OPENCLAW_GATEWAY_TOKEN"),
    )

    content = build_openclaw_config(cfg)
    backup_path = write_config(cfg.config_path, content, dry_run)

    result = V0Result(
        ok=True,
        message="v0 config generated",
        config_written=not dry_run,
        backup_path=backup_path,
    )

    if verify:
        result.proxy_health = _check_url("http://127.0.0.1:5002/health")
        result.detect_health = _check_url("http://127.0.0.1:5001/guardrails/health")
        og_api_key = os.getenv("OG_API_KEY")
        if og_api_key:
            result.detection_result = _detect_sample(og_api_key, cfg.og_detect_url)
    if verify_script:
        try:
            completed = subprocess.run(
                ["bash", verify_script],
                check=False,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            result.verify_script_ok = completed.returncode == 0
            output = (completed.stdout or "") + (completed.stderr or "")
            result.verify_script_output = output.strip() or None
        except Exception as exc:
            result.verify_script_ok = False
            result.verify_script_output = f"failed to run verify script: {exc}"
    return result
