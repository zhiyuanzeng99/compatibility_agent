from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .v0.pipeline import run_v0


@click.group()
def main() -> None:
    """Adapter Agent CLI."""


@main.command("v0")
@click.option("--project-path", required=True, type=click.Path(path_type=Path))
@click.option("--config-path", type=click.Path(path_type=Path), default=None)
@click.option("--og-base-url", default=None)
@click.option("--og-detect-url", default=None)
@click.option("--model-id", default="gpt-4")
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--verify", is_flag=True, default=False)
@click.option("--verify-script", default=None)
def v0_cmd(
    project_path: Path,
    config_path: Path | None,
    og_base_url: str | None,
    og_detect_url: str | None,
    model_id: str,
    dry_run: bool,
    verify: bool,
    verify_script: str | None,
) -> None:
    """Run V0 pipeline for OpenClaw + OpenGuardrails."""
    result = run_v0(
        project_path=str(project_path),
        config_path=str(config_path) if config_path else None,
        og_base_url=og_base_url,
        og_detect_url=og_detect_url,
        model_id=model_id,
        dry_run=dry_run,
        verify=verify,
        verify_script=verify_script,
    )
    click.echo(json.dumps(result.__dict__, indent=2, ensure_ascii=True, default=str))
    if not result.ok:
        sys.exit(1)


@main.command("v1")
@click.option("--project-path", required=True, type=click.Path(path_type=Path))
@click.option("--output-dir", default=None, type=click.Path(path_type=Path))
@click.option("--tool", default=None)
@click.option("--tools", default=None)
@click.option("--deploy/--no-deploy", default=True)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--mode", default="direct")
@click.option("--validate/--no-validate", default=True)
@click.option("--auto-fix/--no-auto-fix", default=False)
@click.option("--lifecycle/--no-lifecycle", default=True)
@click.option("--one-click/--no-one-click", default=False)
@click.option("--target-app", default=None)
def v1_cmd(
    project_path: Path,
    output_dir: Path | None,
    tool: str | None,
    tools: str | None,
    deploy: bool,
    dry_run: bool,
    mode: str,
    validate: bool,
    auto_fix: bool,
    lifecycle: bool,
    one_click: bool,
    target_app: str | None,
) -> None:
    """Run V1 pipeline (multi-tool)."""
    from .v1.pipeline import run_v1

    result = run_v1(
        project_path=str(project_path),
        output_dir=str(output_dir) if output_dir else None,
        tool=tool,
        tools=tools,
        deploy=deploy,
        dry_run=dry_run,
        mode=mode,
        validate=validate,
        auto_fix=auto_fix,
        use_lifecycle=lifecycle,
        one_click=one_click,
        target_app=target_app,
    )
    click.echo(json.dumps(result.__dict__, indent=2, ensure_ascii=True, default=str))
    if not result.ok:
        sys.exit(1)


@main.command("v2")
@click.option("--project-path", required=True, type=click.Path(path_type=Path))
@click.option("--validate/--no-validate", default=True)
@click.option("--auto-fix/--no-auto-fix", default=False)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--state-out", default=None)
def v2_cmd(
    project_path: Path,
    validate: bool,
    auto_fix: bool,
    dry_run: bool,
    state_out: str | None,
) -> None:
    """Run V2 agent pipeline (auto decision + deploy + validate)."""
    from .v2.pipeline import run_v2

    result = run_v2(
        project_path=str(project_path),
        validate=validate,
        auto_fix=auto_fix,
        dry_run=dry_run,
        state_out=state_out,
    )
    click.echo(json.dumps(result.__dict__, indent=2, ensure_ascii=True, default=str))
    if not result.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
