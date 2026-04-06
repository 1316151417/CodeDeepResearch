import json
import threading
from queue import Queue, Empty

from base.types import EventType, SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import SCORER_SYSTEM, SCORER_USER

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


def score_and_rank_modules(ctx: PipelineContext) -> None:
    module_list = "\n".join(
        f"  - {m.name}: {m.description} (files: {', '.join(m.files)})"
        for m in ctx.modules
    )
    user_msg = SCORER_USER.format(
        project_name=ctx.project_name,
        module_list=module_list,
    )

    response = _call_llm(ctx.provider, SCORER_SYSTEM, user_msg)

    try:
        scores = json.loads(_extract_json(response))
    except json.JSONDecodeError:
        # 回退：平均分配分数
        scores = {m.name: 50 for m in ctx.modules}

    # 给每个模块赋分
    for m in ctx.modules:
        m.importance_score = float(scores.get(m.name, 50))

    # 按分数降序排列
    ctx.ranked_modules = sorted(ctx.modules, key=lambda m: m.importance_score, reverse=True)

    # 取前 N 个
    ctx.selected_modules = ctx.ranked_modules[: ctx.max_sub_agents]


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
