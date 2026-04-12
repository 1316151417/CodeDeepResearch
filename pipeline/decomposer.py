"""Stage 3: 模块拆分 - 按目录结构 + import 关系划分模块."""
import json

from provider.llm import call_llm, extract_json
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import DECOMPOSER_SYSTEM, DECOMPOSER_USER


def decompose_into_modules(ctx: PipelineContext) -> None:
    important_files = [f for f in ctx.all_files if f.is_important]
    files_json = json.dumps([
        {"path": f.path, "type": f.file_type, "size": f.size}
        for f in important_files
    ], ensure_ascii=False, indent=2)

    user_msg = DECOMPOSER_USER.format(project_name=ctx.project_name, files_json=files_json)
    response = call_llm(ctx.provider, DECOMPOSER_SYSTEM, user_msg, model=ctx.lite_model, response_format={"type": "json_object"})

    result = json.loads(extract_json(response))
    modules_data = result.get("modules", [])

    existing_paths = {f.path for f in important_files}
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


if __name__ == "__main__":
    import os
    from pipeline.llm_filter import llm_filter_files
    from pipeline.scanner import scan_project

    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ctx = PipelineContext(project_path=project_path, project_name="CodeDeepResearch")
    scan_project(ctx)
    llm_filter_files(ctx)

    important_files = [f for f in ctx.all_files if f.is_important]
    print(f"重要文件：{len(important_files)} 个\n")

    decompose_into_modules(ctx)

    print(f"拆分 {len(ctx.modules)} 个模块：\n")
    for m in ctx.modules:
        print(f"## {m.name}")
        print(f"{m.description}")
        for f in m.files:
            print(f"  - {f}")
        print()
