import inspect
import re
from typing import Callable, Optional, Dict, List, Union
from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    MESSAGE_START = "message_start"
    CONTENT_DELTA = "content_delta"
    THINKING_DELTA = "thinking_delta"
    TOOL_CALL = "tool_call"
    MESSAGE_END = "message_end"


@dataclass
class Event:
    type: EventType
    content: Optional[str] = None
    tool_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_arguments: Optional[str] = None
    stop_reason: Optional[str] = None
    usage: Optional[dict] = None


@dataclass
class ToolProperty:
    type: str
    description: str
    enum: Optional[List[str]] = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, ToolProperty]
    required: List[str] = field(default_factory=list)
    func: Optional[Callable] = None

    def to_openai(self) -> dict:
        properties = {}
        for key, prop in self.parameters.items():
            prop_dict = {
                "type": prop.type,
                "description": prop.description,
            }
            if prop.enum:
                prop_dict["enum"] = prop.enum
            properties[key] = prop_dict

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": self.required,
                },
            },
        }

    def to_anthropic(self) -> dict:
        properties = {}
        for key, prop in self.parameters.items():
            prop_dict = {
                "type": prop.type,
                "description": prop.description,
            }
            if prop.enum:
                prop_dict["enum"] = prop.enum
            properties[key] = prop_dict

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": self.required,
            },
        }

    def __call__(self, *args, **kwargs):
        if self.func is None:
            raise RuntimeError(f"Tool {self.name} has no associated function")
        return self.func(*args, **kwargs)


@dataclass
class Message:
    role: str
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class SystemMessage(Message):
    def __init__(self, content: str):
        super().__init__("system", content)


class UserMessage(Message):
    def __init__(self, content: str):
        super().__init__("user", content)


class AssistantMessage(Message):
    def __init__(self, content: str):
        super().__init__("assistant", content)


class ToolMessage(Message):
    def __init__(self, tool_id: str, tool_name: str, tool_result=None, tool_error=None):
        super().__init__("tool", str({
            "tool_id": tool_id,
            "tool_name": tool_name,
            "tool_result": tool_result,
            "tool_error": tool_error,
        }))


def _parse_param_descriptions(docstring: str) -> Dict[str, str]:
    if not docstring:
        return {}

    descriptions = {}

    args_match = re.search(r'Args:\s*\n(.*?)(?=\n\n|\Z)', docstring, re.DOTALL)
    if not args_match:
        return {}

    args_text = args_match.group(1)

    for line in args_text.split('\n'):
        stripped = line.lstrip()
        if not stripped:
            continue

        match = re.match(r'(\w+):\s*(.+)', stripped)
        if match:
            param_name = match.group(1)
            param_desc = match.group(2).strip()
            if param_name and param_desc:
                descriptions[param_name] = param_desc

    return descriptions


def tool(func=None, *, name=None, description=None):
    def decorator(f):
        tool_name = name or f.__name__
        tool_description = description or f.__doc__ or ""

        sig = inspect.signature(f)
        parameters = {}
        required = []

        param_descriptions = _parse_param_descriptions(f.__doc__)

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                param_type = "string"
            else:
                param_type = _get_type_string(param_type)

            if param.default == inspect.Parameter.empty:
                required.append(param_name)

            parameters[param_name] = ToolProperty(
                type=param_type,
                description=param_descriptions.get(param_name, param_name),
            )

        return Tool(
            name=tool_name,
            description=tool_description.strip(),
            parameters=parameters,
            required=required,
            func=f,
        )

    if func is None:
        return decorator
    return decorator(func)


def _get_type_string(type_hint) -> str:
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    return type_map.get(type_hint, "string")


def normalize_messages(messages: List[Union[Message, dict]]) -> List[dict]:
    normalized = []
    for msg in messages:
        if isinstance(msg, Message):
            normalized.append(msg.to_dict())
        else:
            normalized.append(msg)
    return normalized
