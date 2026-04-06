import json
import threading
from queue import Queue, Empty

from base.types import EventType, SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import DECOMPOSER_SYSTEM, DECOMPOSER_USER

CALL_LLM_TIMEOUT = 60


def _call_llm_with_timeout(adaptor, messages, timeout):
    """对 adaptor.stream() 的迭代包装超时保护"""
    result_queue = Queue()

    def worker():
        try:
            for event in adaptor.stream(messages):
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


def decompose_into_modules(ctx: PipelineContext) -> None:
    file_list = "\n".join(
        f"  {f.path} ({f.size}B)"
        for f in ctx.important_files
    )
    user_msg = DECOMPOSER_USER.format(
        project_name=ctx.project_name,
        tree_text=ctx.tree_text,
        file_list=file_list,
    )

    response = _call_llm(ctx.provider, DECOMPOSER_SYSTEM, user_msg)

    try:
        raw_modules = json.loads(_extract_json(response))
    except json.JSONDecodeError:
        # 回退：按顶层目录分组
        ctx.modules = _fallback_decompose(ctx.important_files)
        return

    modules = []
    for m in raw_modules:
        name = m.get("name", "unknown")
        description = m.get("description", "")
        files = m.get("files", [])
        # 过滤掉不存在的文件
        existing_paths = {f.path for f in ctx.important_files}
        valid_files = [f for f in files if f in existing_paths]
        if valid_files:
            modules.append(Module(name=name, description=description, files=valid_files))

    ctx.modules = modules if modules else _fallback_decompose(ctx.important_files)


def _fallback_decompose(files) -> list[Module]:
    """按顶层目录分组作为回退策略"""
    groups = {}
    for f in files:
        parts = f.path.split("/")
        group_key = parts[0] if len(parts) > 1 else "root"
        groups.setdefault(group_key, []).append(f.path)

    return [
        Module(name=key, description=f"Files in {key}/", files=paths)
        for key, paths in groups.items()
    ]


def _extract_json(text: str) -> str:
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start != end:
            inner = text[start:end]
            first_newline = inner.find("\n")
            if first_newline != -1:
                inner = inner[first_newline + 1:]
            return inner.strip()
    for i, ch in enumerate(text):
        if ch in "[{":
            return text[i:]
    return text
