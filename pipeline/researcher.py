"""Step 2: 内容生成 — 为每个主题生成详细文档."""
import os
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from pipeline.utils import build_toc_navigation, extract_blog_content
from prompt.langfuse_prompt import get_compiled_messages
from tool.fs_tool import set_project_root, get_dir_structure, view_file_in_detail, run_bash


def generate_content(ctx: PipelineContext) -> PipelineContext:
    """为所有主题生成内容，并行或串行。"""
    set_project_root(ctx.project_path)
    adaptor = LLMAdaptor(ctx.pro_config)
    tools = [get_dir_structure, view_file_in_detail, run_bash]
    os_name = platform.system().lower()

    if ctx.research_parallel:
        print(f"  并行模式: {ctx.research_threads} 线程, {len(ctx.topics)} 个主题")
        with ThreadPoolExecutor(max_workers=ctx.research_threads) as executor:
            futures = {
                executor.submit(_generate_one, ctx, topic, adaptor, tools, os_name): topic
                for topic in ctx.topics
            }
            for future in as_completed(futures):
                topic = futures[future]
                try:
                    future.result()
                    print(f"  ✓ 主题完成: {topic.name}")
                except Exception as e:
                    print(f"  ✗ 主题失败: {topic.name} - {e}")
    else:
        print(f"  串行模式: {len(ctx.topics)} 个主题")
        for topic in ctx.topics:
            _generate_one(ctx, topic, adaptor, tools, os_name)
            print(f"  ✓ 主题完成: {topic.name}")

    return ctx


def _generate_one(ctx: PipelineContext, topic, adaptor: LLMAdaptor, tools: list, os_name: str) -> None:
    """内部函数：为单个主题生成内容。"""
    full_toc = build_toc_navigation(ctx.topics, topic)

    messages = get_compiled_messages("step2",
        working_dir=ctx.project_path,
        os_name=os_name,
        current_section=topic.section_name,
        current_topic=topic.name,
        target_audience=ctx.settings.get("target_audience", "初级开发者"),
        doc_language=ctx.settings.get("doc_language", "中文"),
        repo_structure=ctx.repo_structure,
        full_toc=full_toc,
    )

    raw_output = adaptor.react_for_text(messages=messages, tools=tools, max_steps=ctx.max_sub_agent_steps)
    topic.content = extract_blog_content(raw_output)
