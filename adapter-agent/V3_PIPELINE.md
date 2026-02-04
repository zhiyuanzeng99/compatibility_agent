# V3 Pipeline（Agent 化：计划 + 执行）

V3 让部署流程更像“Agent”：
- 先生成计划（Plan）
- 再执行计划（Execute）
- 输出状态文件（State）

## 使用方式

```bash
cd /Users/zhiyuan/compatibility_agent/adapter-agent

python -m adapter_agent.cli v3 \
  --project-path /root/project/openclaw \
  --guard openguardrails \
  --mode whitebox \
  --validate \
  --state-out ./deployment_state_v3.json
```

### 仅生成计划（不执行）
```bash
python -m adapter_agent.cli v3 \
  --project-path /root/project/openclaw \
  --guard openguardrails \
  --mode blackbox \
  --plan-only \
  --state-out ./deployment_state_v3_plan.json
```

## 输出说明
- `plan`：部署计划（步骤/风险/产物）
- `execution`：执行结果（若未 `--plan-only`）
- `issues`：发现的问题
- `state_out`：状态文件
