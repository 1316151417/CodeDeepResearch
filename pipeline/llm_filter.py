import json

from base.types import EventType, SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import FILE_FILTER_SYSTEM, FILE_FILTER_USER


def _call_llm(provider: str, system: str, user: str) -> str:
    adaptor = LLMAdaptor(provider=provider)
    content = ""
    for event in adaptor.stream(
        [SystemMessage(system), UserMessage(user)],
        response_format={"type": "json_object"},
    ):
        if event.type == EventType.CONTENT_DELTA:
            content += event.content
    return content


def llm_filter_files(ctx: PipelineContext) -> None:
    file_list = "\n".join(
        f"  {f.path} ({f.size}B)"
        for f in ctx.filtered_files
    )
    user_msg = FILE_FILTER_USER.format(
        project_name=ctx.project_name,
        tree_text=ctx.tree_text,
        file_list=file_list,
    )

    response = _call_llm(ctx.provider, FILE_FILTER_SYSTEM, user_msg)

    try:
        important_paths = json.loads(_extract_json(response))
    except json.JSONDecodeError:
        # LLM 返回非法 JSON 时，保留所有文件
        ctx.important_files = list(ctx.filtered_files)
        return

    path_set = set(important_paths)
    ctx.important_files = [f for f in ctx.filtered_files if f.path in path_set]

    # 如果过滤太激进（少于 3 个文件），保留所有文件
    if len(ctx.important_files) < 3:
        ctx.important_files = list(ctx.filtered_files)


def _extract_json(text: str) -> str:
    """从 LLM 响应中提取 JSON（可能被 markdown 代码块包裹）"""
    text = text.strip()
    # 尝试提取 ```json ... ``` 块
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start != end:
            inner = text[start:end]
            # 去掉开头的 ```json 或 ```
            first_newline = inner.find("\n")
            if first_newline != -1:
                inner = inner[first_newline + 1:]
            return inner.strip()
    # 尝试找到 [ 或 { 开始的 JSON
    for i, ch in enumerate(text):
        if ch in "[{":
            return text[i:]
    return text
