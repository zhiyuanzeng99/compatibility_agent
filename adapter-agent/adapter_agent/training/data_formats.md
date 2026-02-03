# 训练数据格式（V0）

本仓库 V0 训练使用两类 JSONL 数据：SFT（指令微调）与 Tool-Use（工具调用）。

## 1) SFT JSONL

每行一个 JSON 对象，推荐结构：

```json
{
  "conversations": [
    {"role": "user", "content": "描述项目并请求安全集成。"},
    {"role": "assistant", "content": "说明步骤并生成代码/配置。"}
  ],
  "metadata": {
    "task": "integration",
    "framework": "langchain",
    "tool": "nemo_guardrails"
  }
}
```

可接受的变体：
- 可使用 `messages` 替代 `conversations`
- 最小结构：`{"prompt": "...", "response": "..."}`（会自动转换）

支持的角色：`system`、`user`、`assistant`、`tool`

## 2) Tool-Use JSONL

每行一个 JSON 对象，推荐结构：

```json
{
  "messages": [
    {"role": "user", "content": "帮我给 LangChain 加安全防护。"},
    {"role": "assistant", "tool_calls": [
      {"id": "1", "name": "scan_project", "arguments": "{\"project_path\": \".\"}"}
    ]},
    {"role": "tool", "content": "{\"framework\": \"langchain\", \"llm_provider\": \"openai\"}"},
    {"role": "assistant", "tool_calls": [
      {"id": "2", "name": "match_guardrail", "arguments": "{\"framework\": \"langchain\"}"}
    ]},
    {"role": "tool", "content": "{\"recommended\": [\"nemo_guardrails\"]}"},
    {"role": "assistant", "content": "已部署 NeMo Guardrails 并完成验证。"}
  ],
  "tools": [
    {"name": "scan_project", "description": "扫描 AI 项目", "parameters": {"type": "object"}},
    {"name": "match_guardrail", "description": "匹配安全工具", "parameters": {"type": "object"}}
  ],
  "metadata": {
    "task": "tool_use"
  }
}
```

说明：
- `tool_calls` 是 `{id, name, arguments}` 列表，其中 `arguments` 为 JSON 字符串。
- `tools` 描述该样本可用的工具列表。

