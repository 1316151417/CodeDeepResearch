from .llm_base import EventType, Event


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
        params = {}

        if self._provider == "anthropic":
            system_msg = None
            user_messages = []

            for msg in messages:
                if msg.get("role") == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)

            if system_msg:
                params["system"] = system_msg

            messages = user_messages

        if tools:
            params["tools"] = tools

        if self._provider == "openai":
            yield from self._stream_openai(messages, params, **kwargs)
        else:
            yield from self._stream_anthropic(messages, params, **kwargs)

    def _stream_openai(self, messages, params, **kwargs):
        state = "idle"
        tools = {}

        for chunk in self._call_stream(messages, **params, **kwargs):
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

            if choice.finish_reason is not None:
                for idx, tool in tools.items():
                    yield Event(
                        EventType.TOOL_END,
                        tool_index=idx,
                        tool_name=tool["name"],
                        tool_arguments=tool["arguments"],
                    )

                yield Event(EventType.MESSAGE_END, finish_reason=choice.finish_reason)
                return

    def _stream_anthropic(self, messages, params, **kwargs):
        tools = {}
        stop_reason = None

        for event in self._call_stream(messages, **params, **kwargs):
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
