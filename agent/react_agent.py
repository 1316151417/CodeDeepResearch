import json
from provider.adaptor import LLMAdaptor
from base.types import Event, EventType, ToolMessage, AssistantMessage

MAX_STEP_CNT = 30


def stream(messages, tools, provider="anthropic", max_steps=MAX_STEP_CNT):
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

        for event in adaptor.stream(
            messages,
            tools=tools,
        ):
            # 直接转发事件
            yield event
            # 内部处理
            if event.type == EventType.CONTENT_START:
                pass
            elif event.type == EventType.CONTENT_DELTA:
                content += event.content
            elif event.type == EventType.CONTENT_END:
                pass
            elif event.type == EventType.THINKING_START:
                pass
            elif event.type == EventType.THINKING_DELTA:
                thinking += event.content
            elif event.type == EventType.THINKING_END:
                pass
            elif event.type == EventType.TOOL_CALL:
                raw_tool_calls.append(event.raw)
                tool_results[event.tool_id] = {"result": None, "error": None}
                try:
                    exec_tool = next((t for t in tools if t.name == event.tool_name), None)
                    if exec_tool is None:
                        raise ValueError(f"Tool '{event.tool_name}' not found")
                    print(f"  [DEBUG] tool_arguments repr={repr(event.tool_arguments)[:200]}", flush=True)
                    exec_tool_arguments = json.loads(event.tool_arguments) if event.tool_arguments else {}
                    print(f"  [DEBUG] exec_tool_arguments={exec_tool_arguments}", flush=True)
                    result = exec_tool(**exec_tool_arguments)
                    tool_results[event.tool_id]["result"] = result
                    yield Event(type=EventType.TOOL_CALL_SUCCESS, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_result=result)
                except Exception as e:
                    import traceback
                    err_msg = f"工具执行失败 {event.tool_name}: {e}, 参数: {event.tool_arguments}, 堆栈: {traceback.format_exc()}"
                    print(f"  !!! {err_msg}", flush=True)
                    tool_results[event.tool_id]["error"] = str(e)
                    yield Event(type=EventType.TOOL_CALL_FAILED, tool_id=event.tool_id, tool_name=event.tool_name, tool_arguments=event.tool_arguments, tool_error=e)

        yield Event(type=EventType.STEP_END, content=content, step=cur_step)
        # 判断是否结束
        if not raw_tool_calls:
            react_finished = True
            break

        # 封装下一轮消息
        messages.append(AssistantMessage(content=content, tool_calls=raw_tool_calls))
        for raw_tc in raw_tool_calls:
            tid = raw_tc["id"]
            tr = tool_results[tid]
            messages.append(ToolMessage(
                tool_id=tid,
                tool_name=raw_tc["name"],
                tool_result=tr["result"],
                tool_error=tr["error"],
            ))