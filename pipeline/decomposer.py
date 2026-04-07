"""Stage 3: 模块拆分 - 按目录结构 + import 关系划分模块."""
import json
import time

from provider.llm import call_llm, extract_json
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import DECOMPOSER_SYSTEM, DECOMPOSER_USER
from monitor.event_bus import get_event_bus
from monitor.events import PipelineEvent, PipelineEventType


def decompose_into_modules(ctx: PipelineContext) -> None:
    bus = get_event_bus(server_url=ctx.server_url)
    def pub(et, stage, data, step=1):
        if ctx.run_id:
            bus.publish(PipelineEvent.new(run_id=ctx.run_id, event_type=et, stage=stage, data=data, step=step))

    pub(PipelineEventType.STAGE_START, "decomposer", {"stage_index": 3})

    file_list = "\n".join(f"  {f.path} ({f.size}B)" for f in ctx.important_files)
    user_msg = DECOMPOSER_USER.format(project_name=ctx.project_name, tree_text=ctx.tree_text, file_list=file_list)

    start = time.time()
    response = call_llm(ctx.provider, DECOMPOSER_SYSTEM, user_msg, model=ctx.lite_model)
    duration_ms = int((time.time() - start) * 1000)

    pub(PipelineEventType.LLM_CALL, "decomposer", {
        "model": ctx.lite_model,
        "prompt_preview": user_msg[:200],
        "duration_ms": duration_ms,
        "response_len": len(response),
    })

    try:
        raw_modules = json.loads(extract_json(response))
    except json.JSONDecodeError:
        ctx.modules = _fallback_decompose(ctx.important_files)
        return

    modules = []
    existing_paths = {f.path for f in ctx.important_files}
    for m in raw_modules:
        name = m.get("name", "unknown")
        description = m.get("description", "")
        files = m.get("files", [])
        valid_files = [f for f in files if f in existing_paths]
        if valid_files:
            modules.append(Module(name=name, description=description, files=valid_files))

    ctx.modules = modules if modules else _fallback_decompose(ctx.important_files)

    pub(PipelineEventType.STAGE_DECOMPOSE_COMPLETE, "decomposer", {
        "module_count": len(ctx.modules),
        "module_names": [m.name for m in ctx.modules],
    })
    pub(PipelineEventType.STAGE_END, "decomposer", {
        "output_summary": f"{len(ctx.modules)} modules decomposed"
    })


def _fallback_decompose(files) -> list[Module]:
    groups = {}
    for f in files:
        parts = f.path.split("/")
        group_key = parts[0] if len(parts) > 1 else "root"
        groups.setdefault(group_key, []).append(f.path)
    return [Module(name=key, description=f"Files in {key}/", files=paths) for key, paths in groups.items()]
