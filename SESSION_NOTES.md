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

## Update: V2.1 / V2.2 (2026-02-04)

- V2.1: manual selection for app/guard/mode (openclaw + openguardrails/llama_firewall).
  Command:
  ```bash
  python -m adapter_agent.cli v21 \
    --project-path /root/project/openclaw \
    --app openclaw \
    --guard openguardrails \
    --mode whitebox \
    --validate \
    --state-out ./deployment_state_v21.json
  ```

- V2.2: blackbox/whitebox with gateway artifacts and llama_firewall stub.
  Command:
  ```bash
  python -m adapter_agent.cli v22 \
    --project-path /root/project/openclaw \
    --app openclaw \
    --guard openguardrails \
    --mode blackbox \
    --out-dir ./artifacts \
    --state-out ./deployment_state_v22.json
  ```
  Artifacts:
  - `gateway_config.json`
  - `llama_firewall_stub.py` (placeholder)

## Demo UI updates
- `adapter-agent/demo/index.html` now supports scenario switch + file upload.
- Added “dangerous command” compare JSON:
  - `demo_result_before_danger.json`
  - `demo_result_after_danger.json`
- Added V2 status display page:
  - `adapter-agent/demo/state.html`
  - `adapter-agent/demo/state.css`
  - `adapter-agent/demo/state.js`

## Key takeaways
- Current V0/V1/V2 are automation pipelines, not a trained Agent.
- True Agent requires LLM decision layer + SFT/RL training loop + tool execution.
- Next step if needed: Agent V3 with LLM planning + training data feedback.

## Update: V2.2 + V3 (2026-02-04)

- V2.2 adds blackbox/whitebox + gateway artifacts and llama_firewall stub.
  Command:
  ```bash
  python -m adapter_agent.cli v22 \
    --project-path /root/project/openclaw \
    --app openclaw \
    --guard openguardrails \
    --mode blackbox \
    --out-dir ./artifacts \
    --state-out ./deployment_state_v22.json
  ```

- V3 introduces a planning layer (planner + executor):
  - `adapter-agent/adapter_agent/v3/planner.py`
  - `adapter-agent/adapter_agent/v3/executor.py`
  - `adapter-agent/adapter_agent/v3/pipeline.py`
  - `adapter-agent/V3_PIPELINE.md`

- V3 command:
  ```bash
  python -m adapter_agent.cli v3 \
    --project-path /root/project/openclaw \
    --guard openguardrails \
    --mode whitebox \
    --validate \
    --state-out ./deployment_state_v3.json
  ```
  Plan-only mode:
  ```bash
  python -m adapter_agent.cli v3 \
    --project-path /root/project/openclaw \
    --guard openguardrails \
    --mode blackbox \
    --plan-only \
    --state-out ./deployment_state_v3_plan.json
  ```

- Key distinction (no model):
  - V2 = direct pipeline (no explicit plan).
  - V3 = explicit plan + execution separation (agent-like shape), even if plan is rules-based.

[2026-02-04]
- User asked: "那你不用模型的话，你的V3和V2的区别是什么，还有帮我保存对话".
- Response drafted: V3 introduces explicit plan + execute separation (planner outputs steps/state; executor runs), supports plan-only, is agent-shaped but rule-based; V2 is a direct pipeline without explicit planning. V3 becomes meaningfully different once an LLM planner + feedback loop is wired in.

[2026-02-04]
- User reminder: demo UI can be opened at /Users/zhiyuan/compatibility_agent/adapter-agent/demo/state.html.
- User request: from now on, save every conversation line into /Users/zhiyuan/compatibility_agent/SESSION_NOTES.md.

[2026-02-04]
User: OK，然后怎么显示你的结果呢
Assistant: 用 demo/state.html 打开，页面支持上传/选择你的 deployment_state_v3.json 并展示 steps/artifacts/issues。

[2026-02-04]
User: 算了，不用每句都记录了，我让你记的时候你在记吧
Assistant: 了解，之后你明确要求记录时我再写入 SESSION_NOTES.md。
