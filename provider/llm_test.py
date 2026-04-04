from provider.llm_base import EventType
from provider.llm_adaptor import LLMAdaptor

anthropic_tools = [
    {
        "name": "get_weather",
        "description": "获取一个城市的天气",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "城市名称",
                },
            },
            "required": ["city"],
        },
    }
]

openai_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取一个城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称",
                    },
                },
                "required": ["city"],
            },
        },
    }
]

def print_event(event):
    if event.type == EventType.MESSAGE_START:
        print("[MESSAGE_START]")
    elif event.type == EventType.CONTENT_DELTA:
        print(event.content, end="", flush=True)
    elif event.type == EventType.TOOL_START:
        print(f"\n[TOOL_START#{event.tool_index}] name={event.tool_name}")
    elif event.type == EventType.TOOL_END:
        print(f"\n[TOOL_END#{event.tool_index}] name={event.tool_name} args={event.tool_arguments}")
    elif event.type == EventType.MESSAGE_END:
        print(f"\n[MESSAGE_END: {event.finish_reason}]")

def anthropic_test():
    adaptor = LLMAdaptor(provider="anthropic")

    for event in adaptor.stream(
        messages=[
            {"role": "system", "content": "你是一个天气预报助手。注意：你可以在一次响应中调用多次工具"},
            {"role": "user", "content": "今天北京和上海的天气怎么样？"},
        ],
        tools=anthropic_tools,
    ):
        print_event(event)

def openai_test():
    adaptor = LLMAdaptor(provider="openai")

    for event in adaptor.stream(
        messages=[
            {"role": "system", "content": "你是一个天气预报助手。注意：你可以在一次响应中调用多次工具"},
            {"role": "user", "content": "今天北京和上海的天气怎么样？"},
        ],
        tools=openai_tools,
    ):
        print_event(event)

if __name__ == "__main__":
    print("=== OpenAI Test ===")
    openai_test()
    print("\n\n=== Anthropic Test ===")
    anthropic_test()
