import os
import time
import anthropic

DEFAULT_TIMEOUT = 60  # 秒
MAX_RETRIES = 1

client = anthropic.Anthropic(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/anthropic",
    timeout=DEFAULT_TIMEOUT,
)


def _resolve_model():
    try:
        from settings import get_model
        return get_model()
    except Exception:
        return "deepseek-chat"


def _resolve_max_tokens():
    try:
        from settings import get_max_tokens
        return get_max_tokens()
    except Exception:
        return 16384


def call(messages, model=None, max_tokens=None, **kwargs):
    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.messages.create(
                model=model or _resolve_model(),
                messages=messages,
                max_tokens=max_tokens or _resolve_max_tokens(),
                timeout=DEFAULT_TIMEOUT,
                **kwargs,
            )
        except (anthropic.APITimeoutError, anthropic.APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise


def call_stream(messages, model=None, max_tokens=None, **kwargs):
    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.messages.create(
                model=model or _resolve_model(),
                messages=messages,
                max_tokens=max_tokens or _resolve_max_tokens(),
                stream=True,
                timeout=DEFAULT_TIMEOUT,
                **kwargs,
            )
        except (anthropic.APITimeoutError, anthropic.APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 流式调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise
