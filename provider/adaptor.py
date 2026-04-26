"""
LLMAdaptor - unified streaming interface for OpenAI and Anthropic protocols.
"""
import json

from base.types import EventType, Event, Tool, normalize_messages

MAX_CONTEXT_CHARS = 200_000
COMPRESS_KEEP_RECENT = 6


def _extract_json(text: str) -> str:
    """从 LLM 响应中提取 JSON（可能被 markdown 代码块包裹）。"""
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start != end:
            inner = text[start:end]
            first_newline = inner.find("\n")
            if first_newline != -1:
                inner = inner[first_newline + 1:]
            return inner.strip()
    for i, ch in enumerate(text):
        if ch in "[{":
            return text[i:]
    return text


class LLMAdaptor:
    def __init__(self, config: dict):
        """
        Initialize adaptor with tier-specific config.

        Args:
            config: dict containing {provider, base_url, api_key, model, max_tokens}
        """
        self._config = config
        self._provider = config.get("provider", "anthropic")

        if self._provider == "openai":
            from provider.api.openai_api import call_stream_openai, call_openai
            self._call_stream = call_stream_openai
            self._call = call_openai
        elif self._provider == "anthropic":
            from provider.api.anthropic_api import call_stream_anthropic, call_anthropic
            self._call_stream = call_stream_anthropic
            self._call = call_anthropic
        else:
            raise ValueError(f"Unknown provider: {self._provider}")

    def stream(self, messages, tools=None, response_format=None, **kwargs):
        messages = normalize_messages(messages)
        params = {}

        if self._provider == "anthropic":
            messages = self._convert_messages_anthropic(messages, params)
        else:
            messages = self._convert_messages_openai(messages)

        if response_format is not None and self._provider == "openai":
            params["response_format"] = response_format

        if tools:
            if all(isinstance(t, Tool) for t in tools):
                tools_dict = [t.to_openai() if self._provider == "openai" else t.to_anthropic() for t in tools]
                params["tools"] = tools_dict
            else:
                params["tools"] = tools

        self._inject_thinking_params(params)

        if self._provider == "openai":
            yield from self._stream_openai(messages, params, **kwargs)
        else:
            yield from self._stream_anthropic(messages, params, **kwargs)

    def compress_if_needed(self, messages) -> list:
        messages = normalize_messages(messages)
        total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
        if total_chars <= MAX_CONTEXT_CHARS:
            return messages

        print(f"\n  [上下文压缩] {total_chars} 字符超过阈值 {MAX_CONTEXT_CHARS}，开始压缩...")

        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        if len(other_msgs) <= COMPRESS_KEEP_RECENT:
            return messages

        to_compress = other_msgs[:-COMPRESS_KEEP_RECENT]
        to_keep = other_msgs[-COMPRESS_KEEP_RECENT:]

        # 跳过 to_keep 开头的孤立 tool 消息（对应的 tool_use 已在压缩部分）
        while to_keep and to_keep[0].get("role") == "tool":
            to_keep.pop(0)
        summary = self._summarize_messages(to_compress)

        compressed = list(system_msgs)
        if summary:
            compressed.append({"role": "user", "content": f"[以下是之前对话的摘要]\n{summary}"})
            compressed.append({"role": "assistant", "content": "好的，我已了解之前的分析内容，继续进行。"})
        compressed.extend(to_keep)

        new_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in compressed)
        print(f"  [上下文压缩] 完成：{total_chars} → {new_chars} 字符")
        return compressed

    def call(self, messages, response_format=None):
        """同步调用，返回完整文本内容。"""
        messages = normalize_messages(messages)
        params = {
            "base_url": self._config.get("base_url"),
            "api_key": self._config.get("api_key"),
            "model": self._config.get("model"),
            "max_tokens": self._config.get("max_tokens"),
        }
        if self._provider == "anthropic":
            messages = self._convert_messages_anthropic(messages, params)
        else:
            messages = self._convert_messages_openai(messages)
        if response_format is not None and self._provider == "openai":
            params["response_format"] = response_format

        self._inject_thinking_params(params)

        response = self._call(messages, **params)

        if self._provider == "anthropic":
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    return block.text
            return ""
        else:
            return response.content

    def call_for_json(self, messages, response_format=None):
        """同步调用，返回提取后的 JSON 文本。"""
        content = self.call(messages, response_format=response_format)
        return _extract_json(content)

    def _inject_thinking_params(self, params):
        """从 config 提取思考模式参数，注入到 API 调用 params 中。"""
        thinking = self._config.get("thinking")
        reasoning_effort = self._config.get("reasoning_effort")

        if thinking is None and not reasoning_effort:
            return

        if self._provider == "openai":
            if reasoning_effort:
                params["reasoning_effort"] = reasoning_effort
            if thinking is not None:
                params.setdefault("extra_body", {})["thinking"] = {"type": "enabled" if thinking else "disabled"}
        elif self._provider == "anthropic":
            extra_body = params.setdefault("extra_body", {})
            if thinking is not None:
                extra_body["thinking"] = {"type": "enabled" if thinking else "disabled"}
            if reasoning_effort:
                extra_body["output_config"] = {"effort": reasoning_effort}

    def _summarize_messages(self, messages: list) -> str:
        from prompt.langfuse_prompt import get_compiled_messages
        conversation_text = self._format_messages_for_summary(messages)
        if not conversation_text.strip():
            return ""

        try:
            compiled = get_compiled_messages("compress", conversation=conversation_text[:30000])
            return self.call(compiled)
        except Exception as e:
            print(f"  [上下文压缩] 压缩失败: {e}")
            return ""

    def _format_messages_for_summary(self, messages: list) -> str:
        lines = []
        for m in messages:
            role = m.get("role", "?")
            content = m.get("content", "")

            if role == "assistant":
                lines.append(self._format_assistant_for_summary(content))
            elif role == "user":
                lines.append(self._format_user_for_summary(content))
            elif role == "tool":
                result = m.get("tool_result") or m.get("tool_error") or ""
                lines.append(f"[工具结果({m.get('tool_name', '?')})]: {str(result)[:500]}")
        return "\n".join(lines)

    def _format_assistant_for_summary(self, content) -> str:
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(f"[助手]: {block['text'][:500]}")
                    elif block.get("type") == "tool_use":
                        parts.append(f"[助手调用工具]: {block.get('name', '?')}({json.dumps(block.get('input', {}), ensure_ascii=False)[:200]})")
            return "\n".join(parts) if parts else ""
        elif content:
            return f"[助手]: {str(content)[:500]}"
        return ""

    def _format_user_for_summary(self, content) -> str:
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    parts.append(f"[工具结果]: {str(block.get('content', ''))[:500]}")
            return "\n".join(parts) if parts else ""
        elif content:
            return f"[用户]: {str(content)[:500]}"
        return ""

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
                if msg.get("reasoning_content"):
                    assistant_msg["reasoning_content"] = msg["reasoning_content"]
                if msg.get("content"):
                    assistant_msg["content"] = msg["content"]
                assistant_msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc.get("arguments", "{}")}}
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
                tool_results.append({"type": "tool_result", "tool_use_id": msg["tool_id"], "content": result_content})
            else:
                if tool_results:
                    user_messages.append({"role": "user", "content": tool_results})
                    tool_results = []
                if msg.get("role") == "assistant" and msg.get("tool_calls"):
                    content_blocks = []
                    if msg.get("reasoning_content"):
                        content_blocks.append({"type": "thinking", "thinking": msg["reasoning_content"]})
                    if msg.get("content"):
                        content_blocks.append({"type": "text", "text": msg["content"]})
                    for tc in msg["tool_calls"]:
                        content_blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": json.loads(tc["arguments"]) if tc.get("arguments") else {}})
                    user_messages.append({"role": "assistant", "content": content_blocks})
                else:
                    user_messages.append(msg)

        if tool_results:
            user_messages.append({"role": "user", "content": tool_results})
        if system_msg:
            params["system"] = system_msg
        return user_messages

    def _stream_openai(self, messages, params, **kwargs):
        tools = {}
        in_thinking = False
        in_content = False

        for chunk in self._call_stream(
            messages,
            base_url=self._config.get("base_url"),
            api_key=self._config.get("api_key"),
            model=self._config.get("model"),
            max_tokens=self._config.get("max_tokens"),
            **params,
            **kwargs,
        ):
            choice = chunk.choices[0]
            delta = choice.delta

            if delta.role == "assistant":
                yield Event(EventType.MESSAGE_START)

            # Thinking
            if getattr(delta, 'reasoning_content', None):
                if not in_thinking:
                    in_thinking = True
                    yield Event(EventType.THINKING_START)
                yield Event(EventType.THINKING_DELTA, content=delta.reasoning_content)
            else:
                if in_thinking:
                    in_thinking = False
                    yield Event(EventType.THINKING_END)

            # Content
            if delta.content:
                if not in_content:
                    in_content = True
                    yield Event(EventType.CONTENT_START)
                yield Event(EventType.CONTENT_DELTA, content=delta.content)
            else:
                if in_content:
                    in_content = False
                    yield Event(EventType.CONTENT_END)

            # Tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index + 1
                    if idx not in tools:
                        tools[idx] = {"id": tc.id, "name": tc.function.name or "", "arguments": tc.function.arguments or ""}
                    elif tc.function.arguments:
                        tools[idx]["arguments"] += tc.function.arguments

            # End
            if choice.finish_reason is not None:
                if in_thinking:
                    yield Event(EventType.THINKING_END)
                if in_content:
                    yield Event(EventType.CONTENT_END)
                for idx in sorted(tools.keys()):
                    tool = tools[idx]
                    yield Event(EventType.TOOL_CALL, tool_id=tool["id"], tool_name=tool["name"], tool_arguments=tool["arguments"], raw={"id": tool["id"], "name": tool["name"], "arguments": tool["arguments"]})
                yield Event(EventType.MESSAGE_END, stop_reason=choice.finish_reason, usage=chunk.usage)
                return

    def _stream_anthropic(self, messages, params, **kwargs):
        tools = {}
        block_types = {}
        stop_reason = None
        usage = None

        for event in self._call_stream(
            messages,
            base_url=self._config.get("base_url"),
            api_key=self._config.get("api_key"),
            model=self._config.get("model"),
            max_tokens=self._config.get("max_tokens"),
            **params,
            **kwargs,
        ):
            if event.type == "message_start":
                yield Event(EventType.MESSAGE_START)

            elif event.type == "content_block_start":
                idx = event.index
                block_type = event.content_block.type
                if block_type == "thinking":
                    block_types[idx] = "thinking"
                    yield Event(EventType.THINKING_START)
                elif block_type == "text":
                    block_types[idx] = "text"
                    yield Event(EventType.CONTENT_START)
                elif block_type == "tool_use":
                    tools[idx] = {"id": event.content_block.id, "name": event.content_block.name, "arguments": ""}

            elif event.type == "content_block_delta":
                idx = event.index
                if event.delta.type == "text_delta":
                    yield Event(EventType.CONTENT_DELTA, content=event.delta.text)
                elif event.delta.type == "thinking_delta":
                    yield Event(EventType.THINKING_DELTA, content=getattr(event.delta, 'thinking', ""))
                elif event.delta.type == "input_json_delta":
                    if idx in tools:
                        tools[idx]["arguments"] += event.delta.partial_json

            elif event.type == "content_block_stop":
                idx = event.index
                if idx in tools:
                    yield Event(EventType.TOOL_CALL, tool_id=tools[idx]["id"], tool_name=tools[idx]["name"], tool_arguments=tools[idx]["arguments"], raw={"id": tools[idx]["id"], "name": tools[idx]["name"], "arguments": tools[idx]["arguments"]})
                elif idx in block_types:
                    yield Event(EventType.THINKING_END if block_types[idx] == "thinking" else EventType.CONTENT_END)

            elif event.type == "message_delta":
                if event.delta.stop_reason:
                    stop_reason = event.delta.stop_reason
                    usage = event.usage

            elif event.type == "message_stop":
                yield Event(EventType.MESSAGE_END, stop_reason=stop_reason, usage=usage)
                return
