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
        tool_call_dict = {}

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
                # 工具调用
                tool_id = event.tool_id
                tool_name = event.tool_name
                tool_arguments = event.tool_arguments
                # 定义结构
                tool_call = {
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "tool_arguments": tool_arguments,
                    "tool_result": None,
                    "tool_error": None,
                }
                # 存入字典
                tool_call_dict[tool_id] = tool_call
                # 开始执行
                print(f"[Tool Call] {tool_name}({tool_arguments})")
                try:
                    # 匹配工具
                    exec_tool = next((t for t in tools if t.name == tool_name), None)
                    if exec_tool is None:
                        raise ValueError(f"Tool '{tool_name}' not found")
                    # 参数解析
                    exec_tool_arguments = json.loads(tool_arguments) if tool_arguments else {}
                    # 执行工具
                    result = exec_tool(**exec_tool_arguments)
                    print(f"[Tool Result] {result}")
                    # 更新工具调用结果
                    tool_call["tool_result"] = result
                except Exception as e:
                    # 更新工具调用错误
                    tool_call["tool_error"] = str(e)

        # 判断是否结束
        if not tool_call_dict:
            react_finished = True
            break
        
        # 没有结束封装下一轮消息
        # 封装LLM返回消息
        if tool_call_dict:
            # 有工具调用时，封装assistant消息（含工具调用信息）
            assistant_msg = {"role": "assistant"}
            if content:
                assistant_msg["content"] = content
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["tool_id"],
                    "name": tc["tool_name"],
                    "arguments": tc["tool_arguments"],
                }
                for tc in tool_call_dict.values()
            ]
            messages.append(assistant_msg)
        elif content:
            messages.append(AssistantMessage(content))
        # 封装工具调用结果消息
        for tool_call in tool_call_dict.values():
            messages.append(ToolMessage(
                tool_id=tool_call["tool_id"],
                tool_name=tool_call["tool_name"],
                tool_result=tool_call["tool_result"],
                tool_error=tool_call["tool_error"],
            ))
    return content or "finished"
