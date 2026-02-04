#!/usr/bin/env bash
set -euo pipefail

PROJECT_PATH=${PROJECT_PATH:-/root/project/openclaw}
OUTPUT_DIR=${OUTPUT_DIR:-/root/project/compatibility_agent/adapter-agent/demo}
MODE=${MODE:-after} # before|after

mkdir -p "$OUTPUT_DIR"

python -m adapter_agent.cli v1 \
  --project-path "$PROJECT_PATH" \
  --one-click \
  --target-app openclaw \
  --tool openguardrails \
  --validate \
  > "$OUTPUT_DIR/demo_result_${MODE}.json"

echo "saved: $OUTPUT_DIR/demo_result_${MODE}.json"
