#!/usr/bin/env bash
set -euo pipefail

echo "[check] OpenGuardrails detection/proxy ports"
ss -ltnp | rg -q ":5001" && echo "  - detection (5001): listening" || echo "  - detection (5001): NOT listening"
ss -ltnp | rg -q ":5002" && echo "  - proxy     (5002): listening" || echo "  - proxy     (5002): NOT listening"

echo
echo "[check] OpenGuardrails health"
curl -s http://127.0.0.1:5002/health || true
echo
curl -s http://127.0.0.1:5001/guardrails/health || true
echo

if [[ -z "${OG_API_KEY:-}" ]]; then
  echo "[warn] OG_API_KEY not set. Export it first:"
  echo "  export OG_API_KEY=\"sk-xxai-...\""
  exit 0
fi

echo "[check] OpenGuardrails /v1/guardrails test"
curl -s http://127.0.0.1:5001/v1/guardrails \
  -H "Authorization: Bearer ${OG_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "OpenGuardrails-Text",
    "messages": [
      {"role": "user", "content": "请记录：张三邮箱 zhangsan@example.com，金额 25000"}
    ]
  }'
echo
