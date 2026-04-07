"""Stage 4: 模块打分排序 - 核心度/依赖度/入口/领域独特性评分."""
import json
import time

from provider.llm import call_llm, extract_json
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import SCORER_SYSTEM, SCORER_USER
from monitor.event_bus import get_event_bus
from monitor.events import PipelineEvent, PipelineEventType


def score_and_rank_modules(ctx: PipelineContext) -> None:
    bus = get_event_bus(server_url=ctx.server_url)
    def pub(et, stage, data, step=1):
        if ctx.run_id:
            bus.publish(PipelineEvent.new(run_id=ctx.run_id, event_type=et, stage=stage, data=data, step=step))

    pub(PipelineEventType.STAGE_START, "scorer", {"stage_index": 4})

    module_list = "\n".join(f"  - {m.name}: {m.description} (files: {', '.join(m.files)})" for m in ctx.modules)
    user_msg = SCORER_USER.format(project_name=ctx.project_name, module_list=module_list)

    start = time.time()
    response = call_llm(ctx.provider, SCORER_SYSTEM, user_msg, model=ctx.lite_model)
    duration_ms = int((time.time() - start) * 1000)

    pub(PipelineEventType.LLM_CALL, "scorer", {
        "model": ctx.lite_model,
        "prompt_preview": user_msg[:200],
        "duration_ms": duration_ms,
        "response_len": len(response),
    })

    try:
        scores = json.loads(extract_json(response))
    except json.JSONDecodeError:
        scores = {m.name: 50 for m in ctx.modules}

    for m in ctx.modules:
        m.importance_score = float(scores.get(m.name, 50))

    ctx.ranked_modules = sorted(ctx.modules, key=lambda m: m.importance_score, reverse=True)
    ctx.selected_modules = ctx.ranked_modules[: ctx.max_sub_agents]

    module_scores = {m.name: m.importance_score for m in ctx.modules}
    pub(PipelineEventType.STAGE_SCORE_COMPLETE, "scorer", {
        "module_scores": module_scores,
        "selected_count": len(ctx.selected_modules),
    })
    pub(PipelineEventType.STAGE_END, "scorer", {
        "output_summary": f"scored {len(ctx.modules)} modules, selected top {len(ctx.selected_modules)}"
    })
