"""
Anthropic-compatible API client - high-level streaming and sync call interface.
"""
import json
import os
import time

from base.types import Event, EventType

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 1


def _create_client(api_key=None, base_url=None):
    import anthropic
    return anthropic.Anthropic(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY"),
        base_url=base_url or "https://api.deepseek.com/anthropic",
        timeout=DEFAULT_TIMEOUT,
    )


def _with_retry(fn, retry_label, *args, **kwargs):
    import anthropic
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except (anthropic.APITimeoutError, anthropic.APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [{retry_label}超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise


def convert_messages(messages, params):
    """将统一消息格式转换为 Anthropic 格式。提取 system 消息到 params["system"]。"""
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


def inject_params(params, config):
    """注入 Anthropic 特有的思考模式参数。"""
    thinking = config.get("thinking")
    reasoning_effort = config.get("reasoning_effort")
    if thinking is None and not reasoning_effort:
        return
    extra_body = params.setdefault("extra_body", {})
    if thinking is not None:
        extra_body["thinking"] = {"type": "enabled" if thinking else "disabled"}
    if reasoning_effort:
        extra_body["output_config"] = {"effort": reasoning_effort}


def stream_events(messages, config, params, **kwargs):
    """高层流式调用：转换消息 → 创建 client → 流式请求 → yield Event。"""
    inject_params(params, config)
    converted = convert_messages(messages, params)

    client = _create_client(api_key=config.get("api_key"), base_url=config.get("base_url"))
    stream = _with_retry(
        lambda: client.messages.create(
            model=config.get("model"),
            messages=converted,
            max_tokens=config.get("max_tokens"),
            stream=True,
            timeout=DEFAULT_TIMEOUT,
            **params,
            **kwargs,
        ),
        "LLM 流式调用",
    )

    tools = {}
    block_types = {}
    stop_reason = None
    usage = None

    for event in stream:
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


def call(messages, config, params, **kwargs):
    """高层同步调用：转换消息 → 创建 client → 返回文本内容。"""
    inject_params(params, config)
    converted = convert_messages(messages, params)

    client = _create_client(api_key=config.get("api_key"), base_url=config.get("base_url"))
    response = _with_retry(
        lambda: client.messages.create(
            model=config.get("model"),
            messages=converted,
            max_tokens=config.get("max_tokens"),
            timeout=DEFAULT_TIMEOUT,
            **params,
            **kwargs,
        ),
        "LLM 调用",
    )
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""
