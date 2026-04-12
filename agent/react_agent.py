"""
ReAct Agent - implements the Observe -> Think -> Act loop with streaming events.
"""
import json
import re

from log.logger import logger
from provider.adaptor import LLMAdaptor
from base.types import Event, EventType, ToolMessage, AssistantMessage

MAX_STEP_CNT = 30


def _stream(adaptor, messages, tools, model):
    """直接透传 adaptor.stream() 的迭代器。"""
    kwargs = {}
    if model:
        kwargs["model"] = model
    yield from adaptor.stream(messages, tools=tools, **kwargs)


def _parse_tool_arguments(arguments_str: str) -> dict:
    """安全解析 tool arguments JSON字符串。"""
    if not arguments_str:
        return {}
    try:
        return json.loads(arguments_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in tool arguments: {arguments_str[:100]}... ({e})")


def _execute_tool(tool, tool_arguments: str):
    """执行工具，返回 (result, error)。"""
    try:
        args = _parse_tool_arguments(tool_arguments)
        result = tool(**args)
        logger.debug(f"[ReAct] 工具结果: {str(result)[:100]}...")
        return result, None
    except Exception as e:
        logger.debug(f"[ReAct] 工具执行失败 {tool.name}: {e}")
        return None, str(e)


def stream(messages, tools, provider="anthropic", model=None, max_steps=MAX_STEP_CNT):
    """ReAct stream generator: yields events for each step."""
    logger.debug(f"[ReAct] 开始 (provider={provider}, model={model}, max_steps={max_steps})")
    for msg in messages:
        logger.debug(f"[ReAct] 消息: {msg}")
    logger.debug(f"[ReAct] 工具定义: {[t.name for t in tools]}")

    adaptor = LLMAdaptor(provider=provider)
    react_finished = False
    step = 1

    while (not react_finished) and step <= max_steps:
        cur_step = step
        yield Event(type=EventType.STEP_START, step=cur_step)
        step = step + 1

        content = ""
        thinking = ""
        raw_tool_calls = []
        tool_results = {}

        logger.debug(f"[ReAct] 步骤 {cur_step} 开始")

        for event in _stream(adaptor, messages, tools, model):
            yield event
            if event.type == EventType.THINKING_DELTA:
                thinking += event.content or ""
                if event.content:
                    logger.debug(event.content, end="")
            elif event.type == EventType.CONTENT_DELTA:
                content += event.content or ""
                if event.content:
                    logger.debug(event.content, end="")
            elif event.type == EventType.TOOL_CALL:
                raw_tool_calls.append(event.raw)
                logger.debug(f"\n[ReAct] 调用工具: {event.tool_name}({event.tool_arguments[:80] if event.tool_arguments else ''}...)")
                tool = next((t for t in tools if t.name == event.tool_name), None)
                if tool is None:
                    raise RuntimeError(f"Tool '{event.tool_name}' not found")
                result, error = _execute_tool(tool, event.tool_arguments)
                tool_results[event.tool_id] = {"result": result, "error": error}
                yield Event(type=EventType.TOOL_CALL_SUCCESS if not error else EventType.TOOL_CALL_FAILED, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_result=result, tool_error=error)

        logger.debug(f"[ReAct] 步骤 {cur_step} 结束，输出长度: {len(content)}")

        yield Event(type=EventType.STEP_END, content=content, step=cur_step)

        if not raw_tool_calls:
            react_finished = True
            break

        messages.append(AssistantMessage(content=content, tool_calls=raw_tool_calls, thinking=thinking))
        for raw_tc in raw_tool_calls:
            tid = raw_tc["id"]
            tr = tool_results[tid]
            messages.append(ToolMessage(tool_id=tid, tool_name=raw_tc["name"], tool_result=tr["result"], tool_error=tr["error"]))

    logger.debug(f"[ReAct] 结束")
