"""
Generate tool-use training data (JSONL).

Usage:
  python -m adapter_agent.training.generate_tool_data --output ./tool_data.jsonl --repeat 10
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .tool_trainer import ToolUseTrainer


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate tool-use JSONL data.")
    parser.add_argument("--output", required=True, help="Output JSONL file path.")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat examples N times.")
    args = parser.parse_args()

    trainer = ToolUseTrainer()
    examples = trainer.generate_examples()
    if args.repeat > 1:
        examples = examples * args.repeat

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        for ex in examples:
            data = ex.to_conversation_format()
            data["tools"] = [
                {"name": t.name, "description": t.description, "parameters": t.parameters}
                for t in trainer.config.tools
            ]
            f.write(json.dumps(data, ensure_ascii=True) + "\n")

    print(f"Wrote {len(examples)} examples to {output_path}")


if __name__ == "__main__":
    main()

