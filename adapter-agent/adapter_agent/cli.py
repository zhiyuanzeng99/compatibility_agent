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
    click.echo(json.dumps(result.__dict__, indent=2, ensure_ascii=True))
    if not result.ok:
        sys.exit(1)
