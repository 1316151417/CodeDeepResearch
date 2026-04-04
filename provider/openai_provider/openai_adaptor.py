import json
from dataclasses import dataclass
from enum import Enum
from deepseek_openai_api import call_stream


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
        state = "idle"
        tools = {}

        for chunk in call_stream(messages, **kwargs):
            choice = chunk.choices[0]
            delta = choice.delta

            if state == "idle":
                if delta.role == "assistant" or delta.content or delta.tool_calls:
                    state = "streaming"
                    yield Event(EventType.MESSAGE_START)

            if delta.content:
                yield Event(EventType.CONTENT_DELTA, content=delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tools:
                        tools[idx] = {
                            "name": tc.function.name or "",
                            "arguments": "",
                            "started": False,
                            "ended": False,
                        }

                    if tc.function.name and not tools[idx]["started"]:
                        tools[idx]["started"] = True
                        yield Event(
                            EventType.TOOL_START,
                            tool_index=idx,
                            tool_name=tools[idx]["name"],
                        )

                    if tc.function.arguments:
                        tools[idx]["arguments"] += tc.function.arguments

                        if not tools[idx]["ended"]:
                            args = tools[idx]["arguments"]
                            if self._is_complete_json(args):
                                tools[idx]["ended"] = True
                                yield Event(
                                    EventType.TOOL_END,
                                    tool_index=idx,
                                    tool_name=tools[idx]["name"],
                                    tool_arguments=args,
                                )

            if choice.finish_reason is not None:
                yield Event(EventType.MESSAGE_END, finish_reason=choice.finish_reason)
                return

    def _is_complete_json(self, s: str) -> bool:
        try:
            json.loads(s)
            return True
        except (json.JSONDecodeError, ValueError):
            return False
