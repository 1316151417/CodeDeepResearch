import os
import anthropic

client = anthropic.Anthropic(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/anthropic",
)


def call(messages, model="deepseek-reasoner", max_tokens=4096, **kwargs):
    return client.messages.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        **kwargs,
    )


def call_stream(messages, model="deepseek-reasoner", max_tokens=4096, **kwargs):
    print(f"call_stream messages: {messages}")
    return client.messages.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=True,
        **kwargs,
    )
