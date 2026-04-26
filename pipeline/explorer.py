"""Step 1: 章节拆分 — 生成文档目录（TOC）."""
import json
import os
import platform

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext
from pipeline.utils import parse_toc_xml
from prompt.langfuse_prompt import get_compiled_messages
from tool.fs_tool import set_project_root, get_dir_structure, view_file_in_detail, run_bash


def generate_toc(ctx: PipelineContext) -> PipelineContext:
    """探索项目并生成文档目录结构。"""
    set_project_root(ctx.project_path)
    tools = [get_dir_structure, view_file_in_detail, run_bash]

    # 预生成顶层目录结构
    ctx.repo_structure = get_dir_structure(".", 2)
    os_name = platform.system().lower()

    messages = get_compiled_messages("step1",
        working_dir=ctx.project_path,
        os_name=os_name,
        repo_structure=ctx.repo_structure,
        doc_language=ctx.settings.get("doc_language", "中文"),
    )

    adaptor = LLMAdaptor(ctx.pro_config)
    raw_output = adaptor.react_for_text(messages=messages, tools=tools, max_steps=ctx.max_sub_agent_steps)

    # 保存原始 XML
    ctx.toc_xml = raw_output

    # 解析 TOC
    ctx.topics = parse_toc_xml(raw_output)
    if not ctx.topics:
        raise ValueError("章节拆分失败：未能解析出任何主题")

    return ctx
