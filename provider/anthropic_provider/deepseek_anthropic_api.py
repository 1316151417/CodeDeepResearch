import os
import anthropic

client = anthropic.Anthropic(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


def call(messages, model="deepseek-chat", **kwargs):
    return client.messages.create(
        model=model,
        messages=messages,
        **kwargs,
    )


def call_stream(messages, model="deepseek-chat", **kwargs):
    return client.messages.create(
        model=model,
        messages=messages,
        stream=True,
        **kwargs,
    )
