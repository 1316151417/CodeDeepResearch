"""Stage 1: Explore & Decompose - ReAct agent explores project and outputs chapter structure."""
import json
import os

from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Chapter, Section, FileInfo
from prompt.langfuse_prompt import get_compiled_messages
from pipeline.utils import collect_report
from tool.fs_tool import (
    set_project_root, read_file, list_directory,
    glob_pattern, grep_content, scan_directory,
)


def explore_and_decompose(ctx: PipelineContext) -> None:
    """ReAct agent: explore project filesystem and decompose into chapters."""
    set_project_root(ctx.project_path)
    tools = [scan_directory, read_file, list_directory, glob_pattern, grep_content]

    messages = get_compiled_messages("explorer",
        project_name=ctx.project_name,
    )

    events = react_stream(
        messages=messages, tools=tools,
        config=ctx.pro_config,
        max_steps=ctx.max_sub_agent_steps,
    )

    raw_output = collect_report(events)
    result = json.loads(_extract_json(raw_output))
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

    if not ctx.chapters:
        raise ValueError("Explore & Decompose failed: no valid chapters produced")


def _extract_json(text: str) -> str:
    """Extract JSON from possibly markdown-wrapped text."""
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start != end:
            inner = text[start:end]
            first_newline = inner.find("\n")
            if first_newline != -1:
                inner = inner[first_newline + 1:]
            return inner.strip()
    for i, ch in enumerate(text):
        if ch in "[{":
            return text[i:]
    return text
