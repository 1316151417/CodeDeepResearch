"""
OpenAI-compatible API client - configurable via settings.
"""
import os
import time

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


def call_openai(messages, base_url=None, api_key=None, model=None, max_tokens=None, response_format=None, **kwargs):
    """OpenAI-compatible synchronous call with configurable endpoint."""
    client = _create_client(api_key=api_key, base_url=base_url)
    response = _with_retry(
        lambda: client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens,
            timeout=DEFAULT_TIMEOUT, response_format=response_format, **kwargs
        ),
        "LLM 调用",
    )
    return response.choices[0].message


def call_stream_openai(messages, base_url=None, api_key=None, model=None, max_tokens=None, response_format=None, **kwargs):
    """OpenAI-compatible streaming call with configurable endpoint."""
    client = _create_client(api_key=api_key, base_url=base_url)
    return _with_retry(
        lambda: client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens,
            stream=True, timeout=DEFAULT_TIMEOUT, response_format=response_format, **kwargs
        ),
        "LLM 流式调用",
    )
