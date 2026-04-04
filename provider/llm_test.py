from provider.anthropic_provider.anthropic_adaptor import LLMAdaptor, EventType

tools = [
    {
        "name": "get_weather",
        "description": "Get the current weather in a given location",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city name",
                },
            },
            "required": ["city"],
        },
    }
]

adaptor = LLMAdaptor()

for event in adaptor.stream(
    [
        {"role": "user", "content": "What's the weather in Beijing and Tokyo?"},
    ],
    tools=tools,
):
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
