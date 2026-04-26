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

    def stream_for_text(self, messages, tools=None, response_format=None, **kwargs):
        """流式调用，收集完整文本内容返回。"""
        from pipeline.utils import collect_stream_text
        return collect_stream_text(self.stream(messages, tools, response_format, **kwargs))

    def stream_for_json(self, messages, tools=None, response_format=None, **kwargs):
        """流式调用，收集内容并提取 JSON 返回。"""
        from pipeline.utils import extract_json
        return extract_json(self.stream_for_text(messages, tools, response_format, **kwargs))

    def call(self, messages, response_format=None):
        """同步调用，返回完整文本内容。"""
        messages = normalize_messages(messages)
        params = self._build_params(None, response_format)
        return self._api.call(messages, self._config, params)

    def call_for_json(self, messages, response_format=None):
        """同步调用，返回提取后的 JSON 文本。"""
        from pipeline.utils import extract_json
        return extract_json(self.call(messages, response_format=response_format))

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
