"""Stage 2: 节深度研究 - 研究模块并生成报告."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from prompt.langfuse_prompt import get_compiled_messages
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


def research_sections(ctx: PipelineContext) -> PipelineContext:
    """研究所有节，并行或串行。"""
    set_project_root(ctx.project_path)
    adaptor = LLMAdaptor(ctx.pro_config)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    all_sections = [sec for ch in ctx.chapters for sec in ch.sections]

    if ctx.research_parallel:
        print(f"  并行模式: {ctx.research_threads} 线程, {len(all_sections)} 个节")
        with ThreadPoolExecutor(max_workers=ctx.research_threads) as executor:
            futures = {
                executor.submit(_research_one, ctx, sec, adaptor, tools): sec
                for sec in all_sections
            }
            for future in as_completed(futures):
                sec = futures[future]
                try:
                    future.result()
                    print(f"  ✓ 节完成: {sec.name}")
                except Exception as e:
                    print(f"  ✗ 节失败: {sec.name} - {e}")
    else:
        print(f"  串行模式: {len(all_sections)} 个节")
        for sec in all_sections:
            _research_one(ctx, sec, adaptor, tools)
            print(f"  ✓ 节完成: {sec.name}")

    return ctx


def _research_one(ctx: PipelineContext, section, adaptor: LLMAdaptor, tools: list) -> None:
    """内部函数：研究单个 section，结果写入 section.research_report。"""
    module_files_json = json.dumps(section.files, ensure_ascii=False, indent=2)

    messages = get_compiled_messages("sub-agent",
        project_name=ctx.project_name,
        module_name=section.name,
        file_tree=ctx.file_tree,
        module_files_json=module_files_json,
    )

    section.research_report = adaptor.react_for_text(messages=messages, tools=tools, max_steps=ctx.max_sub_agent_steps)
