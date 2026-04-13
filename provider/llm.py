"""
Shared LLM utilities for pipeline modules.
"""
from base.types import SystemMessage, UserMessage


def call_llm(config: dict, system: str, user: str, response_format=None) -> str:
    """简单的同步 LLM 调用封装。"""
    from provider.adaptor import LLMAdaptor
    adaptor = LLMAdaptor(config)
    messages = [SystemMessage(system), UserMessage(user)]
    return adaptor.call(messages, response_format=response_format)
