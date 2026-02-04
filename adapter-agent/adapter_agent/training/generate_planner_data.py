#!/usr/bin/env python3
import argparse
import glob
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SYSTEM_PROMPT = (
    "You are GuardAdapter Planner. Output strict JSON only. "
    "Do not add explanations."
)


APPS = ["openclaw", "langchain", "llamaindex", "custom"]
GUARDS = ["openguardrails", "llama_firewall"]
MODES = ["blackbox", "whitebox"]


def _base_steps(mode: str) -> List[Dict[str, str]]:
    steps = [
        {
            "id": "scan",
            "title": "Scan project",
            "details": "Read dependencies and entry points to confirm integration path",
        }
    ]
    if mode == "blackbox":
        steps.append(
            {
                "id": "integrate",
                "title": "Generate gateway config",
                "details": "Write gateway config and route traffic to guard service",
            }
        )
    else:
        steps.append(
            {
                "id": "integrate",
                "title": "Generate middleware",
                "details": "Wrap app calls and insert guard checks",
            }
        )
    steps.extend(
        [
            {
                "id": "deploy",
                "title": "Deploy and restart",
                "details": "Apply config and restart related services",
            },
            {
                "id": "validate",
                "title": "Health checks",
                "details": "Verify guard service and run sample checks",
            },
        ]
    )
    return steps


def make_plan(app: str, guard: str, mode: str) -> Dict[str, Any]:
    return {
        "target_app": app,
        "guard": guard,
        "mode": mode,
        "steps": _base_steps(mode),
    }


def make_prompt(app: str, guard: str, mode: str) -> str:
    return (
        f"Project: app={app}, guard={guard}, mode={mode}. "
        "Generate deployment plan JSON."
    )


def plan_to_messages(plan: Dict[str, Any]) -> Dict[str, Any]:
    prompt = make_prompt(plan["target_app"], plan["guard"], plan["mode"])
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": json.dumps(plan, ensure_ascii=False)},
        ]
    }


def make_rejected(plan: Dict[str, Any]) -> Dict[str, Any]:
    rejected = dict(plan)
    steps = [step for step in plan.get("steps", []) if step.get("id") != "validate"]
    if steps == plan.get("steps", []):
        steps = plan.get("steps", [])[:-1]
    rejected["steps"] = steps
    return rejected


def plan_to_dpo(plan: Dict[str, Any]) -> Dict[str, Any]:
    prompt = make_prompt(plan["target_app"], plan["guard"], plan["mode"])
    chosen = json.dumps(plan, ensure_ascii=False)
    rejected = json.dumps(make_rejected(plan), ensure_ascii=False)
    return {"prompt": prompt, "chosen": chosen, "rejected": rejected}


def _extract_plan_from_state(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if "plan" in payload and isinstance(payload["plan"], dict):
        return payload["plan"]
    if "decision" in payload and isinstance(payload["decision"], dict):
        # v2 decision shape
        decision = payload["decision"]
        app = decision.get("app") or decision.get("target_app") or "custom"
        guard = decision.get("guard") or "openguardrails"
        mode = decision.get("mode") or "blackbox"
        return make_plan(app, guard, mode)
    return None


def load_state_plans(paths: List[str]) -> List[Dict[str, Any]]:
    plans: List[Dict[str, Any]] = []
    for path in paths:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        plan = _extract_plan_from_state(payload)
        if plan:
            plans.append(plan)
    return plans


def generate_synthetic(count: int, seed: int) -> List[Dict[str, Any]]:
    random.seed(seed)
    plans: List[Dict[str, Any]] = []
    for _ in range(count):
        app = random.choice(APPS)
        guard = random.choice(GUARDS)
        mode = random.choice(MODES)
        plans.append(make_plan(app, guard, mode))
    return plans


def write_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False))
            f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate planner SFT/DPO data")
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out-sft", default="data/planner_sft.jsonl")
    parser.add_argument("--out-dpo", default="data/planner_dpo.jsonl")
    parser.add_argument("--state-glob", default="")
    args = parser.parse_args()

    state_paths: List[str] = []
    if args.state_glob:
        state_paths = glob.glob(args.state_glob)

    plans: List[Dict[str, Any]] = load_state_plans(state_paths)
    remaining = max(args.count - len(plans), 0)
    plans.extend(generate_synthetic(remaining, args.seed))
    plans = plans[: args.count]

    sft_items = [plan_to_messages(p) for p in plans]
    dpo_items = [plan_to_dpo(p) for p in plans]

    write_jsonl(Path(args.out_sft), sft_items)
    write_jsonl(Path(args.out_dpo), dpo_items)

    print(f"wrote SFT: {args.out_sft} ({len(sft_items)})")
    print(f"wrote DPO: {args.out_dpo} ({len(dpo_items)})")


if __name__ == "__main__":
    main()
