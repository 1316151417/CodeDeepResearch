"""Stage 3: 最终报告汇总 - 整合所有章节报告."""
import json

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.langfuse_prompt import get_compiled_messages
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


def aggregate_reports(ctx: PipelineContext) -> PipelineContext:
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    chapter_reports = []
    for ch in ctx.chapters:
        chapter_text = f"## 章：{ch.name}\n{ch.description}\n"
        for sec in ch.sections:
            chapter_text += f"\n### 节：{sec.name}\n{sec.research_report}\n"
        chapter_reports.append(chapter_text)

    module_reports = "\n\n---\n\n".join(chapter_reports)
    important_files = list({f for ch in ctx.chapters for sec in ch.sections for f in sec.files})

    messages = get_compiled_messages("aggregator",
        project_name=ctx.project_name,
        file_tree=ctx.file_tree,
        important_files=json.dumps(important_files, ensure_ascii=False, indent=2),
        module_reports=module_reports,
    )

    adaptor = LLMAdaptor(ctx.max_config)
    ctx.final_report = adaptor.react_for_text(messages=messages, tools=tools, max_steps=ctx.max_sub_agent_steps)

    return ctx
