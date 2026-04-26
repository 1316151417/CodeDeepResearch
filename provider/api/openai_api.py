"""
OpenAI-compatible API client - high-level streaming and sync call interface.
"""
import json
import os
import time

from base.types import Event, EventType

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 1


def _create_client(api_key=None, base_url=None):
    from langfuse.openai import OpenAI
    return OpenAI(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY"),
        base_url=base_url or "https://api.deepseek.com",
        timeout=DEFAULT_TIMEOUT,
    )


def _with_retry(fn, retry_label, *args, **kwargs):
    from openai import APITimeoutError, APIConnectionError
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except (APITimeoutError, APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [{retry_label}超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise


def convert_messages(messages):
    """将统一消息格式转换为 OpenAI 格式。"""
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


def inject_params(params, config):
    """注入 OpenAI 特有的思考模式参数。"""
    thinking = config.get("thinking")
    reasoning_effort = config.get("reasoning_effort")
    if reasoning_effort:
        params["reasoning_effort"] = reasoning_effort
    if thinking is not None:
        params.setdefault("extra_body", {})["thinking"] = {"type": "enabled" if thinking else "disabled"}


def stream_events(messages, config, params, **kwargs):
    """高层流式调用：转换消息 → 创建 client → 流式请求 → yield Event。"""
    inject_params(params, config)
    converted = convert_messages(messages)

    client = _create_client(api_key=config.get("api_key"), base_url=config.get("base_url"))
    stream = _with_retry(
        lambda: client.chat.completions.create(
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
    in_thinking = False
    in_content = False

    for chunk in stream:
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


def call(messages, config, params, **kwargs):
    """高层同步调用：转换消息 → 创建 client → 返回文本内容。"""
    inject_params(params, config)
    converted = convert_messages(messages)

    client = _create_client(api_key=config.get("api_key"), base_url=config.get("base_url"))
    response = _with_retry(
        lambda: client.chat.completions.create(
            model=config.get("model"),
            messages=converted,
            max_tokens=config.get("max_tokens"),
            timeout=DEFAULT_TIMEOUT,
            **params,
            **kwargs,
        ),
        "LLM 调用",
    )
    return response.choices[0].message.content
