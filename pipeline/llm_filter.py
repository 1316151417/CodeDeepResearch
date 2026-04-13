"""Stage 2: LLM 智能过滤 - 基于项目类型判断文件重要性."""
import json

from base.types import SystemMessage, UserMessage
from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import FILE_FILTER_SYSTEM, FILE_FILTER_USER


def llm_filter_files(ctx: PipelineContext) -> None:
    # 构建文件 JSON 列表，只包含可能重要的文件
    files_json = json.dumps([
        {"path": f.path, "type": f.file_type, "size": f.size}
        for f in ctx.all_files
        if f.is_important  # 初始标记为重要的才送入 LLM 进一步过滤
    ], ensure_ascii=False, indent=2)

    adaptor = LLMAdaptor(ctx.lite_config)
    messages = [SystemMessage(FILE_FILTER_SYSTEM), UserMessage(FILE_FILTER_USER.format(project_name=ctx.project_name, files_json=files_json))]
    response = adaptor.call_for_json(messages, response_format={"type": "json_object"})

    try:
        result = json.loads(response)
        unimportant_paths = set(result.get("unimportant_paths", []))
    except (json.JSONDecodeError, KeyError, TypeError):
        unimportant_paths = set()

    # 修正 is_important 标记
    for f in ctx.all_files:
        if f.path in unimportant_paths:
            f.is_important = False


if __name__ == "__main__":
    import os
    from pipeline.scanner import scan_project
    from settings import get_lite_config

    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ctx = PipelineContext(project_path=project_path, project_name="CodeDeepResearch", lite_config=get_lite_config())
    scan_project(ctx)

    important_before = [f for f in ctx.all_files if f.is_important]
    print(f"过滤前：{len(important_before)} 个重要文件\n")

    llm_filter_files(ctx)

    important_after = [f for f in ctx.all_files if f.is_important]
    newly_unimportant = set(f.path for f in important_before) - set(f.path for f in important_after)

    print(f"过滤后：{len(important_after)} 个重要文件\n")
    if newly_unimportant:
        print(f"新增不重要的文件：")
        for path in sorted(newly_unimportant):
            print(f"  - {path}")
