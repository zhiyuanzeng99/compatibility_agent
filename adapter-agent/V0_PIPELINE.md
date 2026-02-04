# V0 Pipeline（OpenClaw + OpenGuardrails）

## 目标
最小可用闭环：
1) 识别 OpenClaw 项目
2) 生成 OpenClaw 配置（指向 OpenGuardrails）
3) 可选：验证 OpenGuardrails 健康状态与检测能力

## 使用方法（一步到位）

```bash
cd /Users/zhiyuan/compatibility_agent/adapter-agent

export OPENCLAW_GATEWAY_TOKEN="your-token"
export OPENAI_API_KEY="sk-xxai-..."
export OG_API_KEY="sk-xxai-..."

python -m adapter_agent.cli v0 \
  --project-path /path/to/openclaw \
  --config-path ~/.openclaw/openclaw.json \
  --model-id gpt-4 \
  --verify \
  --verify-script /Users/zhiyuan/compatibility_agent/scripts/verify_og_openclaw.sh
```

## 简化演示版（推荐）
面向展示/验收的最短路径，仅证明“可部署 + 健康检查通过”：

```bash
cd /root/project/compatibility_agent/adapter-agent

# 最小必要环境变量（其余可先不设置）
export OPENCLAW_GATEWAY_TOKEN="my-openclaw-token"
export OPENAI_API_KEY="sk-..."

python -m adapter_agent.cli v0 \
  --project-path /root/project/openclaw \
  --verify
```

成功标志：
- `config_written: true`
- `proxy_health: true`
- `detect_health: true`

说明：
- `detection_result` 为空/401 不影响“部署成功”的结论，只表示没做检测样例或未设置 `OG_API_KEY`。

### 参数说明
- `--project-path`：OpenClaw 项目路径（必须）
- `--config-path`：OpenClaw 配置写入位置（默认 `~/.openclaw/openclaw.json`）
- `--model-id`：OpenClaw 侧模型 ID（默认 `gpt-4`）
- `--verify`：开启内置健康检查（5001/5002）
- `--verify-script`：额外验证脚本，输出 JSON 汇总

### 环境变量说明
- `OPENCLAW_GATEWAY_TOKEN`（可选）：写入 `gateway.auth.token`
- `OPENAI_API_KEY`（必须）：OpenGuardrails 调用模型提供方（如 OpenAI）所用 key
- `OG_API_KEY`（可选）：用于 OpenGuardrails 检测接口 `/v1/guardrails`

## verify_og_openclaw.sh 说明
脚本路径：
`/Users/zhiyuan/compatibility_agent/scripts/verify_og_openclaw.sh`

脚本输出为 JSON，包含：
- `detect_listen` / `proxy_listen`：端口监听情况
- `detect_health` / `proxy_health`：健康检查响应
- `detect_result`：一次 `/v1/guardrails` 的检测结果
- `og_api_key_set`：是否设置了 `OG_API_KEY`

## Token 获取方式

### OPENCLAW_GATEWAY_TOKEN
这是你自己设置的访问口令，用于保护 OpenClaw Gateway，不是系统生成。
示例：
```bash
export OPENCLAW_GATEWAY_TOKEN="zhiyuan-2026-strong-token"
```

### OPENAI_API_KEY
这是 OpenGuardrails 调用模型提供方（如 OpenAI）时使用的 key。
需要在 OpenAI 控制台创建，不等同于 OG_API_KEY。

### OG_API_KEY（OpenGuardrails API Key）
通过 OpenGuardrails Admin API 登录获取（无 UI 时推荐）：
```bash
curl -s -X POST http://127.0.0.1:5500/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourdomain.com","password":"MyPass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key'))"
```
输出形如 `sk-xxai-...`，用于：
- `OG_API_KEY`（检测接口 `/v1/guardrails`）
