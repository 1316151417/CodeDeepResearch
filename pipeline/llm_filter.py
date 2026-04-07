"""Stage 2: LLM 智能过滤 - 基于项目类型判断文件重要性."""
import json
import time

from base.types import SystemMessage, UserMessage
from provider.llm import call_llm, extract_json
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import FILE_FILTER_SYSTEM, FILE_FILTER_USER
from monitor.event_bus import get_event_bus
from monitor.events import PipelineEvent, PipelineEventType


def llm_filter_files(ctx: PipelineContext) -> None:
    bus = get_event_bus(server_url=ctx.server_url)
    def pub(et, stage, data, step=1):
        if ctx.run_id:
            bus.publish(PipelineEvent.new(run_id=ctx.run_id, event_type=et, stage=stage, data=data, step=step))

    pub(PipelineEventType.STAGE_START, "llm_filter", {"stage_index": 2})

    file_list = "\n".join(f"  {f.path} ({f.size}B)" for f in ctx.filtered_files)
    user_msg = FILE_FILTER_USER.format(project_name=ctx.project_name, tree_text=ctx.tree_text, file_list=file_list)

    start = time.time()
    response = call_llm(ctx.provider, FILE_FILTER_SYSTEM, user_msg, model=ctx.lite_model, response_format={"type": "json_object"})
    duration_ms = int((time.time() - start) * 1000)

    pub(PipelineEventType.LLM_CALL, "llm_filter", {
        "model": ctx.lite_model,
        "prompt_preview": user_msg[:200],
        "duration_ms": duration_ms,
        "response_len": len(response),
    })

    try:
        important_paths = json.loads(extract_json(response))
    except json.JSONDecodeError:
        ctx.important_files = list(ctx.filtered_files)
        return

    path_set = set(important_paths)
    ctx.important_files = [f for f in ctx.filtered_files if f.path in path_set]

    if len(ctx.important_files) < 3:
        ctx.important_files = list(ctx.filtered_files)

    pub(PipelineEventType.STAGE_FILTER_COMPLETE, "llm_filter", {
        "filtered_in_count": len(ctx.important_files),
        "filtered_out_count": len(ctx.filtered_files) - len(ctx.important_files),
    })
    pub(PipelineEventType.STAGE_END, "llm_filter", {
        "output_summary": f"{len(ctx.important_files)} important files after LLM filter"
    })
