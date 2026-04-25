"""Stage 2: 模块拆分 - 按目录结构 + import 关系划分模块."""
import json

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext, Module
from prompt.langfuse_prompt import get_compiled_messages


def decompose_into_modules(ctx: PipelineContext) -> None:
    files_json = json.dumps([f.path for f in ctx.all_files], ensure_ascii=False, indent=2)

    adaptor = LLMAdaptor(ctx.lite_config)
    messages = get_compiled_messages("decomposer", project_name=ctx.project_name, files_json=files_json)
    response = adaptor.call_for_json(messages, response_format={"type": "json_object"})

    result = json.loads(response)
    modules_data = result.get("modules", [])

    existing_paths = {f.path for f in ctx.all_files}
    ctx.modules = []
    for m in modules_data:
        name = m.get("name", "")
        description = m.get("description", "")
        files = m.get("files", [])
        valid_files = [f for f in files if f in existing_paths]
        if name and valid_files:
            ctx.modules.append(Module(name=name, description=description, files=valid_files))

    if not ctx.modules:
        raise ValueError(f"模块拆分失败：LLM 返回无效结果")
