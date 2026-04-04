from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    MESSAGE_START = "message_start"
    CONTENT_DELTA = "content_delta"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    MESSAGE_END = "message_end"


@dataclass
class Event:
    type: EventType
    content: str | None = None
    tool_index: int | None = None
    tool_name: str | None = None
    tool_arguments: str | None = None
    finish_reason: str | None = None
