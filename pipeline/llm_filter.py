import json
import threading
from queue import Queue, Empty

from base.types import EventType, SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import FILE_FILTER_SYSTEM, FILE_FILTER_USER

CALL_LLM_TIMEOUT = 60  # 秒


def _call_llm_with_timeout(adaptor, messages, timeout):
    """对 adaptor.stream() 的迭代包装超时保护"""
    result_queue = Queue()

    def worker():
        try:
            for event in adaptor.stream(messages, response_format={"type": "json_object"}):
                result_queue.put(("event", event))
            result_queue.put(("done", None))
        except Exception as e:
            result_queue.put(("exception", str(e)))

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    content = ""
    while True:
        try:
            tag, data = result_queue.get(timeout=timeout)
            if tag == "done":
                return content
            if tag == "exception":
                raise RuntimeError(f"LLM stream exception: {data}")
            if data.type == EventType.CONTENT_DELTA:
                content += data.content
        except Empty:
            raise TimeoutError(f"LLM call timeout after {timeout}s")


def _call_llm(provider: str, system: str, user: str) -> str:
    adaptor = LLMAdaptor(provider=provider)
    messages = [SystemMessage(system), UserMessage(user)]
    try:
        return _call_llm_with_timeout(adaptor, messages, CALL_LLM_TIMEOUT)
    except TimeoutError as e:
        print(f"  [LLM 调用超时] {e}", flush=True)
        return ""


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
