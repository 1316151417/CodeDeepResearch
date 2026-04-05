from base.types import EventType, SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from prompt.test_system_prompt import SYSTEM_PROMPT
from tool.test_tool import get_weather, get_temperature
from agent.react_agent import react

tools = [get_weather]

def print_event(event):
    if event.type == EventType.MESSAGE_START:
        print("[MESSAGE_START]")
    elif event.type == EventType.THINKING_START:
        print("[THINKING_START]")
    elif event.type == EventType.THINKING_DELTA:
        print(event.content, end="", flush=True)
    elif event.type == EventType.THINKING_END:
        print("\n[THINKING_END]")
    elif event.type == EventType.CONTENT_START:
        print("[CONTENT_START]")
    elif event.type == EventType.CONTENT_DELTA:
        print(event.content, end="", flush=True)
    elif event.type == EventType.CONTENT_END:
        print("\n[CONTENT_END]")
    elif event.type == EventType.TOOL_CALL:
        print(f"\n[TOOL_CALL] id={event.tool_id} name={event.tool_name} args={event.tool_arguments}")
    elif event.type == EventType.MESSAGE_END:
        print(f"\n[MESSAGE_END] stop_reason={event.stop_reason} usage={event.usage}")

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

def react_test():
    messages = [
        SystemMessage(SYSTEM_PROMPT),
        UserMessage("今天北京和上海的天气怎么样？"),
    ]
    result = react(messages, tools, provider="anthropic")
    # result = react(messages, tools, provider="openai")
    # print(f"\n[Final Result]\n{result}")

if __name__ == "__main__":
    # print("=== OpenAI Test ===")
    # openai_test()
    # print("=== Anthropic Test ===")
    # anthropic_test()
    print("=== React Agent Test ===")
    react_test()
