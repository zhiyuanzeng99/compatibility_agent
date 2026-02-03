#!/usr/bin/env bash
set -euo pipefail

detect_listen=false
proxy_listen=false
detect_health=""
proxy_health=""
detect_result=""

if command -v rg >/dev/null 2>&1; then
  match_cmd="rg -q"
else
  match_cmd="grep -q"
fi

if ss -ltnp | eval "${match_cmd} ':5001'"; then
  detect_listen=true
fi
if ss -ltnp | eval "${match_cmd} ':5002'"; then
  proxy_listen=true
fi

proxy_health=$(curl -s http://127.0.0.1:5002/health || true)
detect_health=$(curl -s http://127.0.0.1:5001/guardrails/health || true)

if [[ -n "${OG_API_KEY:-}" ]]; then
  detect_result=$(curl -s http://127.0.0.1:5001/v1/guardrails \
    -H "Authorization: Bearer ${OG_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "OpenGuardrails-Text",
      "messages": [
        {"role": "user", "content": "请记录：张三邮箱 zhangsan@example.com，金额 25000"}
      ]
    }' || true)
fi

export DETECT_LISTEN="${detect_listen}"
export PROXY_LISTEN="${proxy_listen}"
export DETECT_HEALTH="${detect_health}"
export PROXY_HEALTH="${proxy_health}"
export DETECT_RESULT="${detect_result}"

python - <<'PY'
import json, os, sys

def norm(s):
    s = s.strip()
    return s if s else None

payload = {
    "detect_listen": os.environ.get("DETECT_LISTEN") == "true",
    "proxy_listen": os.environ.get("PROXY_LISTEN") == "true",
    "detect_health": norm(os.environ.get("DETECT_HEALTH", "")),
    "proxy_health": norm(os.environ.get("PROXY_HEALTH", "")),
    "detect_result": norm(os.environ.get("DETECT_RESULT", "")),
    "og_api_key_set": bool(os.environ.get("OG_API_KEY")),
}
print(json.dumps(payload, ensure_ascii=True, indent=2))
PY
