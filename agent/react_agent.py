import json
from provider.adaptor import LLMAdaptor
from base.types import EventType, ToolMessage, AssistantMessage

MAX_LLM_CALL_CNT = 30


def react(messages, tools, provider="anthropic"):
    adaptor = LLMAdaptor(provider=provider)
    react_finished = False
    llm_call_cnt = 0

    while (not react_finished) and llm_call_cnt < MAX_LLM_CALL_CNT:
        llm_call_cnt = llm_call_cnt + 1

        content = ""
        thinking = ""
        raw_tool_calls = []
        tool_results = {}

        for event in adaptor.stream(
            messages,
            tools=tools,
        ):
            if event.type == EventType.CONTENT_START:
                print("[Content Start]")
            elif event.type == EventType.CONTENT_DELTA:
                content += event.content
                print(event.content, end="", flush=True)
            elif event.type == EventType.CONTENT_END:
                print("\n[Content End]")
            elif event.type == EventType.THINKING_START:
                print("[Thinking Start]")
            elif event.type == EventType.THINKING_DELTA:
                thinking += event.content
                print(event.content, end="", flush=True)
            elif event.type == EventType.THINKING_END:
                print("\n[Thinking End]")
            elif event.type == EventType.TOOL_CALL:
                raw_tool_calls.append(event.raw)
                tool_results[event.tool_id] = {"result": None, "error": None}
                print(f"[Tool Call] {event.tool_name}({event.tool_arguments})")
                try:
                    exec_tool = next((t for t in tools if t.name == event.tool_name), None)
                    if exec_tool is None:
                        raise ValueError(f"Tool '{event.tool_name}' not found")
                    exec_tool_arguments = json.loads(event.tool_arguments) if event.tool_arguments else {}
                    result = exec_tool(**exec_tool_arguments)
                    print(f"[Tool Result] {result}")
                    tool_results[event.tool_id]["result"] = result
                except Exception as e:
                    tool_results[event.tool_id]["error"] = str(e)

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
    return content or "finished"
