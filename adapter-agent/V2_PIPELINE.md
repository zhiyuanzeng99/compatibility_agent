# V2 Pipeline（一键智能 Agent 版）

## 目标
V2 引入“自动决策 + 自动部署 + 自动验证 +（可选）自动修复”的最小闭环，
让流程开始体现 Agent 化特征。

本版本聚焦 **OpenClaw + OpenGuardrails**：
- 自动识别目标项目是否为 OpenClaw
- 自动选择 OpenGuardrails
- 自动写入配置并验证健康
- 输出状态记录（可选）

## 使用方法

```bash
cd /Users/zhiyuan/compatibility_agent/adapter-agent

python -m adapter_agent.cli v2 \
  --project-path /root/project/openclaw \
  --validate \
  --state-out ./deployment_state.json
```

## V2.1（手动选择 Guard + 应用 + 模式）
符合你的诉求：人工选择 Guard 和应用，一键部署。

```bash
python -m adapter_agent.cli v21 \
  --project-path /root/project/openclaw \
  --app openclaw \
  --guard openguardrails \
  --mode whitebox \
  --validate \
  --state-out ./deployment_state_v21.json
```

### V2.1 参数说明
- `--app`：目标应用（当前支持 `openclaw`）
- `--guard`：安全工具（支持 `openguardrails` / `llama_firewall`）
- `--mode`：`whitebox` 或 `blackbox`

说明：
- `openguardrails` 会走自动配置与健康检查
- `llama_firewall` 目前输出为“待实现”提示（V2.2 接入）

## V2.2（黑盒/白盒 + Gateway 产物）
V2.2 引入黑盒模式（Gateway 配置生成），并为 LlamaFirewall 生成占位集成文件。

```bash
python -m adapter_agent.cli v22 \
  --project-path /root/project/openclaw \
  --app openclaw \
  --guard openguardrails \
  --mode blackbox \
  --out-dir ./artifacts \
  --state-out ./deployment_state_v22.json
```

### V2.2 说明
- `--mode blackbox` 会生成 `gateway_config.json`
- `--guard llama_firewall` 会生成 `llama_firewall_stub.py`（占位）
- `--out-dir` 默认写入 `project/.guardadapter`

### 参数说明
- `--project-path`：目标项目路径（必须）
- `--validate/--no-validate`：是否执行健康检查
- `--auto-fix/--no-auto-fix`：失败时尝试修复（V2.0 仅提示）
- `--dry-run`：仅生成，不写入配置
- `--state-out`：输出状态 JSON（建议用于演示/回溯）

## 输出说明
V2 输出包含：
- `decision`：自动决策结果（目标应用 + 工具 + 原因）
- `v0`：底层执行结果（配置写入 + health + detection）
- `issues`：发现的问题（例如 OG_API_KEY 未设置）
- `state_path`：状态文件位置（若提供）

## V2.0 与 V2.1/2.2 的差异
- V2.0：单工具 + 单应用（OpenClaw + OpenGuardrails）
- V2.1：多工具协同编排
- V2.2：任意项目 + 自动集成策略
