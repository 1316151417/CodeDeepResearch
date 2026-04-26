"""
ReAct Agent - implements the Observe -> Think -> Act loop with streaming events.
"""
import json

from dataclasses import dataclass, field

from log.logger import logger
from provider.adaptor import LLMAdaptor
from base.types import Event, EventType, ToolMessage, AssistantMessage

from langfuse import observe

MAX_STEP_CNT = 30


@dataclass
class _Step:
    """Accumulates streaming events within a single ReAct step."""
    content: str = ""
    thinking: str = ""
    tool_calls: list = field(default_factory=list)
    tool_results: dict = field(default_factory=dict)

    def process(self, event: Event) -> None:
        if event.type == EventType.THINKING_DELTA:
            self.thinking += event.content or ""
        elif event.type == EventType.CONTENT_DELTA:
            self.content += event.content or ""
        elif event.type == EventType.TOOL_CALL:
            self.tool_calls.append(event.raw)

    def build_messages(self) -> list:
        """Build AssistantMessage + ToolMessages for appending to conversation."""
        msgs = [AssistantMessage(
            content=self.content,
            tool_calls=self.tool_calls,
            thinking=self.thinking,
        )]
        for tc in self.tool_calls:
            tr = self.tool_results[tc["id"]]
            msgs.append(ToolMessage(
                tool_id=tc["id"],
                tool_name=tc["name"],
                tool_result=tr["result"],
                tool_error=tr["error"],
            ))
        return msgs


def _parse_arguments(arguments_str: str) -> dict:
    """Parse tool call arguments JSON."""
    if not arguments_str:
        return {}
    try:
        return json.loads(arguments_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in tool arguments: {arguments_str[:100]}... ({e})")


@observe(name="react_agent_stream")
def stream(messages, tools, config: dict, max_steps=MAX_STEP_CNT):
    """ReAct stream generator: yields events for each step."""
    adaptor = LLMAdaptor(config)
    tool_map = {t.name: t for t in tools}

    for step in range(1, max_steps + 1):
        compressed = adaptor.compress_if_needed(messages)
        if compressed is not messages:
            messages.clear()
            messages.extend(compressed)

        yield Event(type=EventType.STEP_START, step=step)
        step_state = _Step()

        for event in adaptor.stream(messages, tools):
            yield event
            step_state.process(event)

            if event.type == EventType.TOOL_CALL:
                tool = tool_map.get(event.tool_name)
                if tool is None:
                    raise RuntimeError(f"Tool '{event.tool_name}' not found")

                logger.debug(f"[ReAct] 调用工具: {event.tool_name}({(event.tool_arguments or '')[:80]}...)")
                try:
                    result = tool(**_parse_arguments(event.tool_arguments))
                    error = None
                    logger.debug(f"[ReAct] 工具结果: {str(result)[:100]}...")
                except Exception as e:
                    result = None
                    error = str(e)
                    logger.debug(f"[ReAct] 工具执行失败 {tool.name}: {e}")

                step_state.tool_results[event.tool_id] = {"result": result, "error": error}
                yield Event(
                    type=EventType.TOOL_CALL_SUCCESS if not error else EventType.TOOL_CALL_FAILED,
                    tool_id=event.tool_id,
                    tool_name=event.tool_name,
                    tool_arguments=event.tool_arguments,
                    tool_result=result,
                    tool_error=error,
                )

        yield Event(type=EventType.STEP_END, content=step_state.content, step=step)

        if not step_state.tool_calls:
            break

        messages.extend(step_state.build_messages())
