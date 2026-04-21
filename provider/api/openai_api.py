"""
OpenAI-compatible API client - configurable via settings.
"""
import os
import time

import dotenv
dotenv.load_dotenv()  # Load environment variables from .env file

DEFAULT_TIMEOUT = 60
MAX_RETRIES = 1


def call_openai(messages, base_url=None, api_key=None, model=None, max_tokens=None, response_format=None, **kwargs):
    """OpenAI-compatible synchronous call with configurable endpoint."""
    from langfuse.openai import OpenAI
    from openai import APITimeoutError, APIConnectionError

    client = OpenAI(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY"),
        base_url=base_url or "https://api.deepseek.com",
        timeout=DEFAULT_TIMEOUT,
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=DEFAULT_TIMEOUT,
                response_format=response_format,
                **kwargs,
            )
            return response.choices[0].message
        except (APITimeoutError, APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise


def call_stream_openai(messages, base_url=None, api_key=None, model=None, max_tokens=None, response_format=None, **kwargs):
    """OpenAI-compatible streaming call with configurable endpoint."""
    from langfuse.openai import OpenAI
    from openai import APITimeoutError, APIConnectionError

    client = OpenAI(
        api_key=api_key or os.environ.get("DEEPSEEK_API_KEY"),
        base_url=base_url or "https://api.deepseek.com",
        timeout=DEFAULT_TIMEOUT,
    )

    for attempt in range(MAX_RETRIES + 1):
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                timeout=DEFAULT_TIMEOUT,
                response_format=response_format,
                **kwargs,
            )
        except (APITimeoutError, APIConnectionError, TimeoutError) as e:
            if attempt < MAX_RETRIES:
                print(f"  [LLM 流式调用超时，重试 {attempt+1}/{MAX_RETRIES}]: {e}")
                time.sleep(1)
            else:
                raise
