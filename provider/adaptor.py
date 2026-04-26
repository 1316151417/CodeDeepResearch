"""
LLMAdaptor - thin facade routing to provider-specific API modules.
"""
from base.types import Tool, normalize_messages


class LLMAdaptor:
    def __init__(self, config: dict):
        self._config = config
        self._provider = config.get("provider", "openai")

        if self._provider == "openai":
            from provider.api import openai_api as api
        elif self._provider == "anthropic":
            from provider.api import anthropic_api as api
        else:
            raise ValueError(f"Unknown provider: {self._provider}")
        self._api = api

    def stream(self, messages, tools=None, response_format=None, **kwargs):
        """底层流式调用，yield Event。"""
        messages = normalize_messages(messages)
        params = self._build_params(tools, response_format)
        yield from self._api.stream_events(messages, self._config, params, **kwargs)

    def stream_react(self, messages, tools, max_steps=30):
        """ReAct 循环：LLM 调工具 → 执行 → 回传 → 继续，yield 事件。"""
        from agent.react_agent import stream as react_stream
        yield from react_stream(messages, tools, self._config, max_steps)

    def react_for_text(self, messages, tools, max_steps=30):
        """ReAct 循环，收集最终文本内容返回。"""
        from pipeline.utils import collect_report
        return collect_report(self.stream_react(messages, tools, max_steps))

    def react_for_json(self, messages, tools, max_steps=30):
        """ReAct 循环，收集内容并提取 JSON 返回。"""
        from pipeline.utils import extract_json
        return extract_json(self.react_for_text(messages, tools, max_steps))

    def _build_params(self, tools, response_format):
        params = {}
        if tools:
            if all(isinstance(t, Tool) for t in tools):
                convert = lambda t: t.to_openai() if self._provider == "openai" else t.to_anthropic()
                params["tools"] = [convert(t) for t in tools]
            else:
                params["tools"] = tools
        if response_format is not None and self._provider == "openai":
            params["response_format"] = response_format
        return params
