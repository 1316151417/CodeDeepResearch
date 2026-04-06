import os
import time
from openai import OpenAI, APITimeoutError, APIConnectionError

DEFAULT_TIMEOUT = 30  # 秒
MAX_RETRIES = 1

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
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


def call(messages, model=None, max_tokens=None, response_format=None, **kwargs):
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model or _resolve_model(),
                messages=messages,
                max_tokens=max_tokens or _resolve_max_tokens(),
                timeout=DEFAULT_TIMEOUT,
                response_format=response_format or {"type": "json_object"},
                **kwargs,
            )
            return response.choices[0].message
        except (APITimeoutError, APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise


def call_stream(messages, model=None, max_tokens=None, response_format=None, **kwargs):
    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(
                model=model or _resolve_model(),
                messages=messages,
                max_tokens=max_tokens or _resolve_max_tokens(),
                stream=True,
                timeout=DEFAULT_TIMEOUT,
                response_format=response_format or {"type": "json_object"},
                **kwargs,
            )
        except (APITimeoutError, APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 流式调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise
