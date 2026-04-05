import json
from base.types import EventType, Event, Tool, normalize_messages
from log import logger


class LLMAdaptor:
    def __init__(self, provider="anthropic"):
        if provider == "openai":
            from .openai.deepseek_api import call_stream
            self._call_stream = call_stream
        elif provider == "anthropic":
            from .anthropic.deepseek_api import call_stream
            self._call_stream = call_stream
        else:
            raise ValueError(f"Unknown provider: {provider}")

        self._provider = provider

    def stream(self, messages, tools=None, **kwargs):
        messages = normalize_messages(messages)
        params = {}

        if self._provider == "anthropic":
            messages = self._convert_messages_anthropic(messages, params)
        else:
            messages = self._convert_messages_openai(messages)

        if tools:
            if all(isinstance(t, Tool) for t in tools):
                if self._provider == "openai":
                    params["tools"] = [t.to_openai() for t in tools]
                else:
                    params["tools"] = [t.to_anthropic() for t in tools]
            else:
                params["tools"] = tools

        logger.debug("LLM call", messages=messages, tools=tools, **kwargs)
        if self._provider == "openai":
            yield from self._stream_openai(messages, params, **kwargs)
        else:
            yield from self._stream_anthropic(messages, params, **kwargs)

    def _convert_messages_openai(self, messages):
        converted = []
        for msg in messages:
            if msg.get("role") == "tool":
                converted.append({
                    "role": "tool",
                    "tool_call_id": msg["tool_id"],
                    "content": str(msg.get("tool_result") or msg.get("tool_error") or ""),
                })
            elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                assistant_msg = {"role": "assistant"}
                if msg.get("content"):
                    assistant_msg["content"] = msg["content"]
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc.get("arguments", "{}"),
                        },
                    }
                    for tc in msg["tool_calls"]
                ]
                converted.append(assistant_msg)
            else:
                converted.append(msg)
        return converted

    def _convert_messages_anthropic(self, messages, params):
        system_msg = None
        user_messages = []
        tool_results = []

        for msg in messages:
            if msg.get("role") == "system":
                system_msg = msg["content"]
            elif msg.get("role") == "tool":
                result_content = str(msg.get("tool_result") or msg.get("tool_error") or "")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": msg["tool_id"],
                    "content": result_content,
                })
            else:
                # 先输出待处理的工具结果
                if tool_results:
                    user_messages.append({"role": "user", "content": tool_results})
                    tool_results = []

                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    # 转换assistant消息（含工具调用信息）
                    content_blocks = []
                    if msg.get("content"):
                        content_blocks.append({"type": "text", "text": msg["content"]})
                    for tc in msg["tool_calls"]:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc["id"],
                            "name": tc["name"],
                            "input": json.loads(tc["arguments"]) if tc.get("arguments") else {},
                        })
                    user_messages.append({"role": "assistant", "content": content_blocks})
                else:
                    user_messages.append(msg)

        # 输出剩余的工具结果
        if tool_results:
            user_messages.append({"role": "user", "content": tool_results})

        if system_msg:
            params["system"] = system_msg

        return user_messages

    def _stream_openai(self, messages, params, **kwargs):
        tools = {}
        in_thinking = False
        in_content = False
        for chunk in self._call_stream(messages, **params, **kwargs):
            # 一般只处理第一个
            choice = chunk.choices[0]
            delta = choice.delta
            usage = chunk.usage
            # 开始事件
            if delta.role == "assistant":
                yield Event(EventType.MESSAGE_START)
            # 思考变更事件（工具调用时不存在该属性）
            if getattr(delta, 'reasoning_content', None):
                if not in_thinking:
                    in_thinking = True
                    yield Event(EventType.THINKING_START)
                yield Event(EventType.THINKING_DELTA, content=delta.reasoning_content)
            else:
                if in_thinking:
                    in_thinking = False
                    yield Event(EventType.THINKING_END)
            # 内容变更事件
            if delta.content:
                if not in_content:
                    in_content = True
                    yield Event(EventType.CONTENT_START)
                yield Event(EventType.CONTENT_DELTA, content=delta.content)
            else:
                if in_content:
                    in_content = False
                    yield Event(EventType.CONTENT_END)
            # 工具调用封装
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    # 工具索引和id
                    idx = tc.index + 1
                    tool_id = tc.id
                    # 工具名称
                    if idx not in tools:
                        tools[idx] = {
                            "id": tool_id,
                            "name": tc.function.name or "",
                            "arguments": tc.function.arguments or "",
                        }
                    # 工具参数
                    if tc.function.arguments:
                        tools[idx]["arguments"] += tc.function.arguments
            # 结束标记
            if choice.finish_reason is not None:
                if in_thinking:
                    yield Event(EventType.THINKING_END)
                if in_content:
                    yield Event(EventType.CONTENT_END)
                # 结束时统一输出工具调用事件
                for idx in sorted(tools.keys()):
                    tool = tools[idx]
                    yield Event(
                        EventType.TOOL_CALL,
                        tool_id=tool["id"],
                        tool_name=tool["name"],
                        tool_arguments=tool["arguments"],
                    )
                # 结束事件
                yield Event(EventType.MESSAGE_END, stop_reason=choice.finish_reason, usage=usage)
                # 终止迭代器
                return

    def _stream_anthropic(self, messages, params, **kwargs):
        tools = {}
        block_types = {}
        for event in self._call_stream(messages, **params, **kwargs):
            # DEBUG
            # print(event.model_dump())
            # 开始事件
            if event.type == "message_start":
                yield Event(EventType.MESSAGE_START)
            # 内容块开始
            elif event.type == "content_block_start":
                # 块索引
                idx = event.index
                block_type = event.content_block.type
                if block_type == "thinking":
                    block_types[idx] = "thinking"
                    yield Event(EventType.THINKING_START)
                elif block_type == "text":
                    block_types[idx] = "text"
                    yield Event(EventType.CONTENT_START)
                elif block_type == "tool_use":
                    tools[idx] = {
                        "id": event.content_block.id,
                        "name": event.content_block.name,
                        "arguments": "",
                    }
            # 内容块变更
            elif event.type == "content_block_delta":
                # 块索引
                idx = event.index
                # 内容变更事件
                if event.delta.type == "text_delta":
                    yield Event(EventType.CONTENT_DELTA, content=event.delta.text)
                # 思考变更事件
                elif event.delta.type == "thinking_delta":
                    thinking_content = event.delta.thinking if hasattr(event.delta, 'thinking') else ""
                    yield Event(EventType.THINKING_DELTA, content=thinking_content)
                # 工具参数
                elif event.delta.type == "input_json_delta":
                    if idx in tools:
                        tools[idx]["arguments"] += event.delta.partial_json
            # 内容块结束
            elif event.type == "content_block_stop":
                # 块索引
                idx = event.index
                # 工具调用事件
                if idx in tools:
                    yield Event(
                        EventType.TOOL_CALL,
                        tool_id=tools[idx]["id"],
                        tool_name=tools[idx]["name"],
                        tool_arguments=tools[idx]["arguments"],
                    )
                # 思考/内容结束事件
                elif idx in block_types:
                    if block_types[idx] == "thinking":
                        yield Event(EventType.THINKING_END)
                    elif block_types[idx] == "text":
                        yield Event(EventType.CONTENT_END)
            # 消息变更事件（stop_reason、usage）
            elif event.type == "message_delta":
                # 消息结束原因
                if event.delta.stop_reason:
                    stop_reason = event.delta.stop_reason
                    usage = event.usage
            # 消息结束事件
            elif event.type == "message_stop":
                yield Event(EventType.MESSAGE_END, stop_reason=stop_reason, usage=usage)
                return
