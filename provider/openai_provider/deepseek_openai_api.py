import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


def call(messages, model="deepseek-chat", **kwargs):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        **kwargs,
    )
    return response.choices[0].message


def call_stream(messages, model="deepseek-chat", **kwargs):
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        **kwargs,
    )
    for chunk in stream:
        yield chunk
