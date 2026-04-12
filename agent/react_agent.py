"""
ReAct Agent - implements the Observe -> Think -> Act loop with streaming events.
"""
import json
import re
import threading
from queue import Queue, Empty

from log.logger import logger
from provider.adaptor import LLMAdaptor
from base.types import Event, EventType, ToolMessage, AssistantMessage

TOOL_CALL_RE = re.compile(r'^tool_use\([^)]*\).*$', re.MULTILINE)
MAX_STEP_CNT = 30
STREAM_TIMEOUT_PER_STEP = 120


def _stream_with_timeout(adaptor, messages, tools, model, timeout):
    """对 adaptor.stream() 的迭代包装超时保护。"""
    result_queue = Queue()

    def worker():
        try:
            kwargs = {}
            if model:
                kwargs["model"] = model
            for event in adaptor.stream(messages, tools=tools, **kwargs):
                result_queue.put(("event", event))
            result_queue.put(("done", None))
        except Exception as e:
            result_queue.put(("exception", str(e)))

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    remaining = timeout
    while True:
        try:
            tag, data = result_queue.get(timeout=remaining)
            if tag == "done":
                return
            if tag == "exception":
                raise RuntimeError(f"Stream exception: {data}")
            yield data
        except Empty:
            raise TimeoutError(f"LLM stream timeout after {timeout}s (no events received)")


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

        try:
            stream_iter = _stream_with_timeout(adaptor, messages, tools, model, STREAM_TIMEOUT_PER_STEP)
        except TimeoutError as e:
            logger.debug(f"[ReAct] 步骤 {cur_step} 超时: {e}")
            yield Event(type=EventType.STEP_END, content="[超时，内容无法获取]", step=cur_step)
            break

        try:
            for event in stream_iter:
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
                        tool_results[event.tool_id] = {"result": None, "error": f"Tool '{event.tool_name}' not found"}
                        yield Event(type=EventType.TOOL_CALL_FAILED, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_error=f"Tool '{event.tool_name}' not found")
                    else:
                        result, error = _execute_tool(tool, event.tool_arguments)
                        tool_results[event.tool_id] = {"result": result, "error": error}
                        yield Event(type=EventType.TOOL_CALL_SUCCESS if not error else EventType.TOOL_CALL_FAILED, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_result=result, tool_error=error)
        except TimeoutError as e:
            logger.debug(f"[ReAct] 步骤 {cur_step} 超时: {e}")
            yield Event(type=EventType.STEP_END, content="[超时，内容无法获取]", step=cur_step)
            break

        filtered_content = TOOL_CALL_RE.sub('', content).strip()
        logger.debug(f"[ReAct] 步骤 {cur_step} 结束，输出长度: {len(filtered_content)}")

        yield Event(type=EventType.STEP_END, content=filtered_content, step=cur_step)

        if not raw_tool_calls:
            react_finished = True
            break

        messages.append(AssistantMessage(content=content, tool_calls=raw_tool_calls, thinking=thinking))
        for raw_tc in raw_tool_calls:
            tid = raw_tc["id"]
            tr = tool_results[tid]
            messages.append(ToolMessage(tool_id=tid, tool_name=raw_tc["name"], tool_result=tr["result"], tool_error=tr["error"]))

    logger.debug(f"[ReAct] 结束")
