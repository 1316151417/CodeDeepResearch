"""Stage 1: Explore & Decompose - explore project and output chapter structure."""
import json
import os

from provider.adaptor import LLMAdaptor
from pipeline.types import PipelineContext, Chapter, Section, FileInfo
from prompt.langfuse_prompt import get_compiled_messages
from pipeline.utils import build_file_tree
from tool.fs_tool import (
    set_project_root, read_file, list_directory,
    glob_pattern, grep_content, scan_directory,
)


def explore_and_decompose(ctx: PipelineContext) -> PipelineContext:
    """Explore project filesystem and decompose into chapters."""
    set_project_root(ctx.project_path)
    tools = [scan_directory, read_file, list_directory, glob_pattern, grep_content]

    messages = get_compiled_messages("explorer",
        project_name=ctx.project_name,
    )

    adaptor = LLMAdaptor(ctx.pro_config)
    result = json.loads(adaptor.react_for_json(messages=messages, tools=tools, max_steps=ctx.max_sub_agent_steps))
    chapters_data = result.get("chapters", [])

    if not chapters_data:
        raise ValueError("Explore & Decompose failed: agent returned no chapters")

    all_file_paths = set()
    ctx.chapters = []

    for ch in chapters_data:
        sections = []
        for sec in ch.get("sections", []):
            name = sec.get("name", "")
            description = sec.get("description", "")
            files = sec.get("files", [])
            valid_files = [
                f for f in files
                if os.path.isfile(os.path.join(ctx.project_path, f))
            ]
            if name and valid_files:
                sections.append(Section(name=name, description=description, files=valid_files))
                all_file_paths.update(valid_files)
        if ch.get("name") and sections:
            ctx.chapters.append(Chapter(
                name=ch["name"],
                description=ch.get("description", ""),
                sections=sections,
            ))

    # Populate all_files for downstream build_file_tree() usage
    ctx.all_files = [FileInfo(path=p) for p in sorted(all_file_paths)]
    ctx.file_tree = build_file_tree(ctx.all_files)

    if not ctx.chapters:
        raise ValueError("Explore & Decompose failed: no valid chapters produced")

    return ctx
