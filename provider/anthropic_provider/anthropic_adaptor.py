from dataclasses import dataclass
from enum import Enum
from provider.anthropic_provider.deepseek_anthropic_api import call_stream


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


class LLMAdaptor:
    def stream(self, messages, **kwargs):
        tools = {}
        stop_reason = None

        for event in call_stream(messages, **kwargs):
            if event.type == "message_start":
                yield Event(EventType.MESSAGE_START)

            elif event.type == "content_block_start":
                if event.content_block.type == "tool_use":
                    idx = event.index
                    tools[idx] = {
                        "name": event.content_block.name,
                        "arguments": "",
                        "ended": False,
                    }
                    yield Event(
                        EventType.TOOL_START,
                        tool_index=idx,
                        tool_name=tools[idx]["name"],
                    )

            elif event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    yield Event(EventType.CONTENT_DELTA, content=event.delta.text)

                elif event.delta.type == "input_json_delta":
                    idx = event.index
                    if idx in tools:
                        tools[idx]["arguments"] += event.delta.partial_json

            elif event.type == "content_block_stop":
                idx = event.index
                if idx in tools and not tools[idx]["ended"]:
                    tools[idx]["ended"] = True
                    yield Event(
                        EventType.TOOL_END,
                        tool_index=idx,
                        tool_name=tools[idx]["name"],
                        tool_arguments=tools[idx]["arguments"],
                    )

            elif event.type == "message_delta":
                if event.delta.stop_reason:
                    stop_reason = event.delta.stop_reason

            elif event.type == "message_stop":
                yield Event(EventType.MESSAGE_END, finish_reason=stop_reason)
                return
