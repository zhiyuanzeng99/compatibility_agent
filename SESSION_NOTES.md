# Session Notes (2026-02-04)

## High-level goals
- V0: prove OpenClaw + OpenGuardrails can be deployed and validated.
- V1: “one-click” deployment for OpenClaw + OpenGuardrails (smart-ish pipeline).
- V2: multi-tool + any project with agent-like decision + repair + training loop.

## Key repos/paths
- Local repo: `/Users/zhiyuan/compatibility_agent`
- Remote repos: `/root/project/openclaw`, `/root/project/openguardrails`, `/root/project/compatibility_agent`
- OpenGuardrails backend: `/root/project/openguardrails/backend`
- OpenClaw config: `~/.openclaw/openclaw.json`

## V0 status
- `adapter_agent` V0 pipeline writes OpenClaw config and verifies health.
- Health checks:
  - Detection: `http://127.0.0.1:5001/health`
  - Proxy: `http://127.0.0.1:5002/health`
- V0 run command (remote):
  ```bash
  cd /root/project/compatibility_agent/adapter-agent
  python -m adapter_agent.cli v0 --project-path /root/project/openclaw --verify
  ```
- V0 result: `detect_health: true`, `proxy_health: true`.

## V1 status (one-click)
- V1 one-click path calls V0 under the hood and returns details.
- Command:
  ```bash
  cd /root/project/compatibility_agent/adapter-agent
  python -m adapter_agent.cli v1 \
    --project-path /root/project/openclaw \
    --one-click \
    --target-app openclaw \
    --tool openguardrails \
    --validate
  ```
- Successful output includes detection_result JSON (after OG_API_KEY set).

## OpenGuardrails services
- Admin UI: 5500
- Admin: 5000
- Detection: 5001
- Proxy: 5002

## Postgres
- Running on 5432 (cluster: 16 main).
- OpenGuardrails expects DB via `.env` (created from `.env.example`).
- `.env` fix: set DATABASE_URL to 5432 and correct password.

## OG_API_KEY
- Login endpoint can hit 429 rate limit.
- DB fallback:
  ```bash
  su - postgres -c "psql -d openguardrails -c '\\d api_keys'"
  su - postgres -c "psql -d openguardrails -c \"select key, created_at from api_keys where is_active=true order by created_at desc limit 5;\""
  ```
- Use the `key` field as OG_API_KEY.

## OPENAI_API_KEY
- Must be created in OpenAI API console (API Keys page).
- Needed for OpenGuardrails to call OpenAI.

## GitHub remote issues
- HTTPS clone unstable from pod; SSH over 443 works.
- Add SSH key and use:
  ```bash
  git clone ssh://git@ssh.github.com:443/zhiyuanzeng99/compatibility_agent.git
  ```

## Demo page
- Files in `adapter-agent/demo/`.
- Supports file upload to bypass file:// fetch restrictions.
- Scenarios:
  - V1 deployment compare (before/after JSON)
  - Danger command compare (删除所有邮件) using static JSON
- Static danger JSON:
  - `demo_result_before_danger.json`
  - `demo_result_after_danger.json`

## Demo JSON capture
- Script: `scripts/capture_demo_result.sh`
- Run from `adapter-agent/` dir:
  ```bash
  MODE=before PROJECT_PATH=/root/project/openclaw OUTPUT_DIR=/root/project/compatibility_agent/adapter-agent/demo \
    ../scripts/capture_demo_result.sh

  MODE=after PROJECT_PATH=/root/project/openclaw OUTPUT_DIR=/root/project/compatibility_agent/adapter-agent/demo \
    ../scripts/capture_demo_result.sh
  ```

## Important code changes
- `adapter-agent/adapter_agent/v1/pipeline.py`: added one-click path for OpenClaw + OpenGuardrails.
- `adapter-agent/adapter_agent/cli.py`: added v1 options + __main__ entry; JSON dumps with default=str.
- `adapter-agent/V0_PIPELINE.md`: added simplified demo flow + clarified keys.
- `adapter-agent/V1_PIPELINE.md`: one-click usage.
- `adapter-agent/demo/*`: upgraded UI + scenario switch + upload support.

## V2 design summary
- Agent-ness shows up when it:
  - Auto-decides tool strategy
  - Auto-fixes failures
  - Records failures and feeds training data
- V2 plan: V2.0 (decision+auto-fix), V2.1 (multi-tool), V2.2 (any project + training loop).
