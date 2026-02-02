"""
Format Converter - 智能格式转换器

支持 LLM 语义映射，实现不同格式间的智能转换
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import json
import re


class FormatType(Enum):
    """格式类型"""
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    TEXT = "text"
    OPENAI_CHAT = "openai_chat"
    ANTHROPIC_CHAT = "anthropic_chat"
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"


@dataclass
class ConversionResult:
    """转换结果"""
    success: bool
    source_format: FormatType
    target_format: FormatType
    original_data: Any
    converted_data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "source_format": self.source_format.value,
            "target_format": self.target_format.value,
            "converted_data": self.converted_data,
            "error": self.error,
            "metadata": self.metadata
        }


class FormatConverter:
    """
    智能格式转换器

    支持多种 AI 框架和 LLM 提供商的格式互转
    """

    # OpenAI 角色映射
    OPENAI_ROLE_MAP = {
        "user": "user",
        "assistant": "assistant",
        "system": "system",
        "human": "user",
        "ai": "assistant",
        "Human": "user",
        "Assistant": "assistant",
    }

    # Anthropic 角色映射
    ANTHROPIC_ROLE_MAP = {
        "user": "user",
        "assistant": "assistant",
        "human": "user",
        "ai": "assistant",
        "Human": "user",
        "Assistant": "assistant",
    }

    def __init__(self):
        self._converters: Dict[tuple, Callable] = {}
        self._register_builtin_converters()

    def _register_builtin_converters(self):
        """注册内置转换器"""
        # OpenAI -> Anthropic
        self.register_converter(
            FormatType.OPENAI_CHAT,
            FormatType.ANTHROPIC_CHAT,
            self._openai_to_anthropic
        )

        # Anthropic -> OpenAI
        self.register_converter(
            FormatType.ANTHROPIC_CHAT,
            FormatType.OPENAI_CHAT,
            self._anthropic_to_openai
        )

        # LangChain -> OpenAI
        self.register_converter(
            FormatType.LANGCHAIN,
            FormatType.OPENAI_CHAT,
            self._langchain_to_openai
        )

        # OpenAI -> LangChain
        self.register_converter(
            FormatType.OPENAI_CHAT,
            FormatType.LANGCHAIN,
            self._openai_to_langchain
        )

    def register_converter(
        self,
        source: FormatType,
        target: FormatType,
        converter: Callable[[Any], Any]
    ) -> None:
        """注册格式转换器"""
        self._converters[(source, target)] = converter

    def convert(
        self,
        data: Any,
        source_format: FormatType,
        target_format: FormatType
    ) -> ConversionResult:
        """
        执行格式转换

        Args:
            data: 源数据
            source_format: 源格式
            target_format: 目标格式

        Returns:
            转换结果
        """
        if source_format == target_format:
            return ConversionResult(
                success=True,
                source_format=source_format,
                target_format=target_format,
                original_data=data,
                converted_data=data
            )

        converter = self._converters.get((source_format, target_format))

        if not converter:
            return ConversionResult(
                success=False,
                source_format=source_format,
                target_format=target_format,
                original_data=data,
                converted_data=None,
                error=f"不支持从 {source_format.value} 到 {target_format.value} 的转换"
            )

        try:
            converted = converter(data)
            return ConversionResult(
                success=True,
                source_format=source_format,
                target_format=target_format,
                original_data=data,
                converted_data=converted
            )
        except Exception as e:
            return ConversionResult(
                success=False,
                source_format=source_format,
                target_format=target_format,
                original_data=data,
                converted_data=None,
                error=str(e)
            )

    def _openai_to_anthropic(self, data: Dict) -> Dict:
        """OpenAI 格式转 Anthropic 格式"""
        messages = data.get("messages", [])
        system_message = None
        converted_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_message = content
            else:
                converted_role = self.ANTHROPIC_ROLE_MAP.get(role, "user")
                converted_messages.append({
                    "role": converted_role,
                    "content": content
                })

        result = {"messages": converted_messages}
        if system_message:
            result["system"] = system_message

        # 转换其他参数
        if "model" in data:
            result["model"] = self._map_model_name(data["model"], "anthropic")
        if "max_tokens" in data:
            result["max_tokens"] = data["max_tokens"]
        if "temperature" in data:
            result["temperature"] = data["temperature"]

        return result

    def _anthropic_to_openai(self, data: Dict) -> Dict:
        """Anthropic 格式转 OpenAI 格式"""
        messages = []

        # 处理 system 消息
        if "system" in data:
            messages.append({
                "role": "system",
                "content": data["system"]
            })

        # 处理对话消息
        for msg in data.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")

            converted_role = self.OPENAI_ROLE_MAP.get(role, "user")
            messages.append({
                "role": converted_role,
                "content": content
            })

        result = {"messages": messages}

        if "model" in data:
            result["model"] = self._map_model_name(data["model"], "openai")
        if "max_tokens" in data:
            result["max_tokens"] = data["max_tokens"]
        if "temperature" in data:
            result["temperature"] = data["temperature"]

        return result

    def _langchain_to_openai(self, data: Any) -> Dict:
        """LangChain 消息格式转 OpenAI 格式"""
        messages = []

        # 处理 LangChain 消息列表
        if isinstance(data, list):
            for msg in data:
                if hasattr(msg, "type"):
                    role = self.OPENAI_ROLE_MAP.get(msg.type, "user")
                    content = getattr(msg, "content", str(msg))
                elif isinstance(msg, dict):
                    role = self.OPENAI_ROLE_MAP.get(msg.get("type", "user"), "user")
                    content = msg.get("content", "")
                else:
                    role = "user"
                    content = str(msg)

                messages.append({"role": role, "content": content})

        return {"messages": messages}

    def _openai_to_langchain(self, data: Dict) -> List[Dict]:
        """OpenAI 格式转 LangChain 消息格式"""
        messages = []

        for msg in data.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # LangChain 使用 type 而不是 role
            msg_type_map = {
                "user": "human",
                "assistant": "ai",
                "system": "system"
            }

            messages.append({
                "type": msg_type_map.get(role, "human"),
                "content": content
            })

        return messages

    def _map_model_name(self, model: str, target_provider: str) -> str:
        """映射模型名称到目标提供商"""
        # 模型映射表
        model_mappings = {
            "openai": {
                "claude-3-opus": "gpt-4-turbo",
                "claude-3-sonnet": "gpt-4",
                "claude-3-haiku": "gpt-3.5-turbo",
            },
            "anthropic": {
                "gpt-4-turbo": "claude-3-opus-20240229",
                "gpt-4": "claude-3-sonnet-20240229",
                "gpt-3.5-turbo": "claude-3-haiku-20240307",
            }
        }

        mappings = model_mappings.get(target_provider, {})
        return mappings.get(model, model)

    def detect_format(self, data: Any) -> Optional[FormatType]:
        """自动检测数据格式"""
        if isinstance(data, str):
            try:
                json.loads(data)
                return FormatType.JSON
            except json.JSONDecodeError:
                return FormatType.TEXT

        if isinstance(data, dict):
            # 检测 OpenAI 格式
            if "messages" in data and isinstance(data["messages"], list):
                messages = data["messages"]
                if messages and "role" in messages[0]:
                    return FormatType.OPENAI_CHAT

            # 检测 Anthropic 格式
            if "messages" in data and "system" in data:
                return FormatType.ANTHROPIC_CHAT

        if isinstance(data, list):
            # 检测 LangChain 格式
            if data and (hasattr(data[0], "type") or
                        (isinstance(data[0], dict) and "type" in data[0])):
                return FormatType.LANGCHAIN

        return None


class SemanticMapper:
    """
    语义映射器

    使用 LLM 进行智能格式转换和语义理解
    """

    def __init__(self, llm_client: Any = None):
        self.llm_client = llm_client

    def map_fields(
        self,
        source_schema: Dict,
        target_schema: Dict,
        sample_data: Dict
    ) -> Dict[str, str]:
        """
        使用 LLM 智能映射字段

        Returns:
            字段映射关系 {source_field: target_field}
        """
        # 如果没有 LLM 客户端，使用规则匹配
        if not self.llm_client:
            return self._rule_based_mapping(source_schema, target_schema)

        # TODO: 使用 LLM 进行智能映射
        return self._rule_based_mapping(source_schema, target_schema)

    def _rule_based_mapping(
        self,
        source_schema: Dict,
        target_schema: Dict
    ) -> Dict[str, str]:
        """基于规则的字段映射"""
        mappings = {}

        # 常见字段同义词
        synonyms = {
            "message": ["content", "text", "body"],
            "user": ["human", "customer", "sender"],
            "assistant": ["ai", "bot", "agent"],
            "role": ["type", "sender_type"],
        }

        source_fields = set(source_schema.keys())
        target_fields = set(target_schema.keys())

        for source_field in source_fields:
            # 直接匹配
            if source_field in target_fields:
                mappings[source_field] = source_field
                continue

            # 同义词匹配
            for key, syns in synonyms.items():
                if source_field.lower() == key or source_field.lower() in syns:
                    for target_field in target_fields:
                        if target_field.lower() == key or target_field.lower() in syns:
                            mappings[source_field] = target_field
                            break

        return mappings
