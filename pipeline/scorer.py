"""Stage 4: 模块打分排序 - 按重要性评分并倒序."""
import json

from provider.llm import call_llm, extract_json
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import SCORER_SYSTEM, SCORER_USER


def score_and_rank_modules(ctx: PipelineContext) -> None:
    modules_json = json.dumps([
        {"name": m.name, "description": m.description, "files": m.files}
        for m in ctx.modules
    ], ensure_ascii=False, indent=2)

    user_msg = SCORER_USER.format(project_name=ctx.project_name, modules_json=modules_json)
    response = call_llm(ctx.provider, SCORER_SYSTEM, user_msg, model=ctx.lite_model, response_format={"type": "json_object"})

    result = json.loads(extract_json(response))
    scores = result.get("scores", {})

    for m in ctx.modules:
        m.score = float(scores.get(m.name, 0))

    ctx.modules.sort(key=lambda m: m.score, reverse=True)


if __name__ == "__main__":
    import os
    from pipeline.decomposer import decompose_into_modules
    from pipeline.llm_filter import llm_filter_files
    from pipeline.scanner import scan_project

    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ctx = PipelineContext(project_path=project_path, project_name="CodeDeepResearch")
    scan_project(ctx)
    llm_filter_files(ctx)
    decompose_into_modules(ctx)

    print(f"打分前：{len(ctx.modules)} 个模块\n")
    score_and_rank_modules(ctx)

    print(f"打分后（倒序）：")
    for m in ctx.modules:
        print(f"  {m.score:5.1f}  {m.name}")
