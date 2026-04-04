from base.llm import EventType, SystemMessage, UserMessage
from provider.llm_adaptor import LLMAdaptor
from prompt.test_system_prompt import SYSTEM_PROMPT
from tool.test_tool import get_weather, get_temperature

tools = [get_weather, get_temperature]

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
            SystemMessage(SYSTEM_PROMPT),
            UserMessage("今天北京和上海的天气怎么样？"),
        ],
        tools=tools,
    ):
        print_event(event)

def openai_test():
    adaptor = LLMAdaptor(provider="openai")

    for event in adaptor.stream(
        messages=[
            SystemMessage(SYSTEM_PROMPT),
            UserMessage("今天北京和上海的天气怎么样？"),
        ],
        tools=tools,
    ):
        print_event(event)

if __name__ == "__main__":
    print("=== OpenAI Test ===")
    openai_test()
    print("=== Anthropic Test ===")
    anthropic_test()
