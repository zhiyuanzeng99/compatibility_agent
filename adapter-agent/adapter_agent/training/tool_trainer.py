"""
Tool Use Trainer - 工具使用训练

训练模型的 Function Calling 能力
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from .sft_trainer import SFTConfig


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class ToolCallExample:
    """工具调用示例"""
    user_input: str
    tool_calls: List[Dict]
    tool_results: List[str]
    final_response: str

    def to_conversation_format(self) -> Dict:
        messages = [{"role": "user", "content": self.user_input}]
        for call, result in zip(self.tool_calls, self.tool_results):
            messages.append({"role": "assistant", "tool_calls": [call]})
            messages.append({"role": "tool", "content": result})
        messages.append({"role": "assistant", "content": self.final_response})
        return {"messages": messages}


@dataclass
class ToolTrainingConfig:
    """工具训练配置"""
    base_config: SFTConfig = field(default_factory=SFTConfig)
    tools: List[ToolDefinition] = field(default_factory=list)
    tool_examples_path: str = ""
    max_tool_calls_per_turn: int = 5


class ToolUseTrainer:
    """工具使用训练器"""

    GUARADAPTER_TOOLS = [
        ToolDefinition(
            name="scan_project",
            description="扫描分析AI应用项目",
            parameters={"type": "object", "properties": {
                "project_path": {"type": "string"}
            }, "required": ["project_path"]}
        ),
        ToolDefinition(
            name="match_guardrail",
            description="匹配安全工具",
            parameters={"type": "object", "properties": {
                "framework": {"type": "string"},
                "llm_provider": {"type": "string"}
            }, "required": ["framework"]}
        ),
        ToolDefinition(
            name="generate_integration_code",
            description="生成集成代码",
            parameters={"type": "object", "properties": {
                "tool_name": {"type": "string"},
                "framework": {"type": "string"}
            }, "required": ["tool_name", "framework"]}
        ),
        ToolDefinition(
            name="deploy",
            description="执行部署",
            parameters={"type": "object", "properties": {
                "project_path": {"type": "string"},
                "mode": {"type": "string", "enum": ["dry_run", "interactive", "auto"]}
            }, "required": ["project_path"]}
        ),
        ToolDefinition(
            name="validate",
            description="验证部署",
            parameters={"type": "object", "properties": {
                "project_path": {"type": "string"},
                "level": {"type": "string", "enum": ["basic", "functional", "comprehensive"]}
            }, "required": ["project_path"]}
        ),
        ToolDefinition(
            name="diagnose_error",
            description="诊断错误",
            parameters={"type": "object", "properties": {
                "error_message": {"type": "string"}
            }, "required": ["error_message"]}
        ),
    ]

    def __init__(self, config: Optional[ToolTrainingConfig] = None):
        self.config = config or ToolTrainingConfig()
        if not self.config.tools:
            self.config.tools = self.GUARADAPTER_TOOLS

    def generate_examples(self) -> List[ToolCallExample]:
        """生成训练示例"""
        return [
            ToolCallExample(
                user_input="帮我给 LangChain 项目添加安全防护",
                tool_calls=[
                    {"id": "1", "name": "scan_project", "arguments": '{"project_path": "."}'},
                    {"id": "2", "name": "match_guardrail", "arguments": '{"framework": "langchain"}'},
                    {"id": "3", "name": "deploy", "arguments": '{"project_path": ".", "mode": "interactive"}'},
                ],
                tool_results=[
                    '{"framework": "langchain", "llm_provider": "openai"}',
                    '{"recommended": ["nemo_guardrails"]}',
                    '{"status": "success"}',
                ],
                final_response="已成功为您的 LangChain 项目部署了 NeMo Guardrails 安全防护！"
            )
        ]

    def prepare_data(self, output_path: str) -> int:
        import json
        examples = self.generate_examples()
        with open(output_path, 'w') as f:
            for ex in examples:
                data = ex.to_conversation_format()
                data["tools"] = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in self.config.tools]
                f.write(json.dumps(data, ensure_ascii=False) + '\n')
        return len(examples)
