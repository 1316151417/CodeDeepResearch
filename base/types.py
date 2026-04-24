import inspect
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Dict, List, Union, Any


class EventType(Enum):
    MESSAGE_START = "message_start"
    THINKING_START = "thinking_start"
    THINKING_DELTA = "thinking_delta"
    THINKING_END = "thinking_end"
    CONTENT_START = "content_start"
    CONTENT_DELTA = "content_delta"
    CONTENT_END = "content_end"
    TOOL_CALL = "tool_call"
    MESSAGE_END = "message_end"
    # ReAct 相关
    STEP_START = "step_start"
    STEP_END = "step_end"
    TOOL_CALL_SUCCESS = "tool_call_success"
    TOOL_CALL_FAILED = "tool_call_failed"


@dataclass
class Event:
    type: EventType
    content: Optional[str] = None
    raw: Optional[dict] = None
    # Tool 相关
    tool_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_arguments: Optional[str] = None
    tool_result: Optional[str] = None
    tool_error: Optional[str] = None
    # 消息结束相关信息
    stop_reason: Optional[str] = None
    usage: Optional[dict] = None
    # 步骤编号
    step: Optional[int] = None


@dataclass
class ToolProperty:
    type: str
    description: str
    enum: Optional[List[str]] = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, ToolProperty] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    func: Optional[Callable] = None

    def _build_schema(self) -> Dict[str, Any]:
        """构建参数 schema（OpenAI 和 Anthropic 共用）。"""
        properties = {}
        for key, prop in self.parameters.items():
            prop_dict = {"type": prop.type, "description": prop.description}
            if prop.enum:
                prop_dict["enum"] = prop.enum
            properties[key] = prop_dict
        return {"type": "object", "properties": properties, "required": self.required}

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._build_schema(),
            },
        }

    def to_anthropic(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self._build_schema(),
        }

    def __call__(self, *args, **kwargs):
        if self.func is None:
            raise RuntimeError(f"Tool {self.name} has no associated function")
        return self.func(*args, **kwargs)


# =====================================================================
# Message Classes
# =====================================================================

@dataclass
class Message:
    role: str
    content: str = ""

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class SystemMessage(Message):
    def __init__(self, content: str):
        super().__init__("system", content)


@dataclass
class UserMessage(Message):
    def __init__(self, content: str):
        super().__init__("user", content)


@dataclass
class AssistantMessage(Message):
    def __init__(self, content: str = "", tool_calls: Optional[List[dict]] = None, thinking: str = ""):
        self.tool_calls = tool_calls or []
        self.thinking = thinking
        super().__init__("assistant", content)

    def to_dict(self) -> dict:
        d = {"role": "assistant"}
        if self.thinking:
            d["reasoning_content"] = self.thinking
        if self.content:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d


@dataclass
class ToolMessage(Message):
    def __init__(self, tool_id: str, tool_name: str, tool_result: Any = None, tool_error: Any = None):
        self.tool_id = tool_id
        self.tool_name = tool_name
        self.tool_result = tool_result
        self.tool_error = tool_error
        super().__init__("tool", "")

    def to_dict(self) -> dict:
        return {
            "role": "tool",
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "tool_result": self.tool_result,
            "tool_error": self.tool_error,
        }


# =====================================================================
# @tool Decorator
# =====================================================================

def _parse_param_descriptions(docstring: str) -> Dict[str, str]:
    if not docstring:
        return {}
    args_match = re.search(r'Args:\s*\n(.*?)(?=\n\n|\Z)', docstring, re.DOTALL)
    if not args_match:
        return {}
    descriptions = {}
    for line in args_match.group(1).split('\n'):
        stripped = line.lstrip()
        if not stripped:
            continue
        match = re.match(r'(\w+):\s*(.+)', stripped)
        if match:
            descriptions[match.group(1)] = match.group(2).strip()
    return descriptions


_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def tool(func: Callable = None, *, name: str = None, description: str = None):
    """Decorator that converts a function into a Tool object."""
    def decorator(f: Callable) -> Tool:
        tool_name = name or f.__name__
        tool_description = description or (f.__doc__ or "").strip().split('\n')[0] or tool_name

        sig = inspect.signature(f)
        parameters = {}
        required = []
        param_descriptions = _parse_param_descriptions(f.__doc__ or "")

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            param_type = _TYPE_MAP.get(param.annotation, "string") if param.annotation != inspect.Parameter.empty else "string"
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
            parameters[param_name] = ToolProperty(
                type=param_type,
                description=param_descriptions.get(param_name, param_name),
            )

        return Tool(
            name=tool_name,
            description=tool_description,
            parameters=parameters,
            required=required,
            func=f,
        )

    if func is None:
        return decorator
    return decorator(func)


def normalize_messages(messages: List[Union[Message, dict]]) -> List[dict]:
    normalized = []
    for msg in messages:
        if isinstance(msg, Message):
            normalized.append(msg.to_dict())
        else:
            normalized.append(msg)
    return normalized
