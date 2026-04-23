"""Stage 5: 子模块深度研究 - ReAct agent 研究模块并生成报告."""
import json
import os
from pathlib import Path

from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import SUB_AGENT_SYSTEM, SUB_AGENT_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


def prepare_research(ctx: PipelineContext) -> tuple:
    """初始化研究工具和文件树，供 research_one_module 使用。"""
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]
    file_tree = _build_file_tree(ctx.all_files)
    return tools, file_tree


def research_one_module(ctx: PipelineContext, module: Module, tools: list, report_dir: str, file_tree: str) -> None:
    """研究单个模块并生成报告。"""
    set_project_root(ctx.project_path)

    module_files_json = json.dumps([f for f in module.files], ensure_ascii=False, indent=2)

    system = SUB_AGENT_SYSTEM.format()
    messages = [
        SystemMessage(system),
        UserMessage(SUB_AGENT_USER.format(
            project_name=ctx.project_name,
            module_name=module.name,
            file_tree=file_tree,
            module_files_json=module_files_json,
        )),
    ]

    events = react_stream(messages=messages, tools=tools, config=ctx.pro_config, max_steps=ctx.max_sub_agent_steps)

    module.research_report = _collect_report(events)

    path = os.path.join(report_dir, f"模块分析报告-{module.name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(module.research_report)


def _build_file_tree(files) -> str:
    """构建文本形式的文件树。"""
    tree = {}
    for f in files:
        parts = Path(f.path).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = None

    lines = ["project/"]
    _render_tree(tree, lines, "")
    return "".join(lines)


def _render_tree(node: dict, lines: list, prefix: str) -> None:
    items = sorted(node.items(), key=lambda x: (not isinstance(x[1], dict), x[0]))
    for i, (name, value) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        if isinstance(value, dict):
            lines.append(f"{prefix}{connector}{name}")
            child_prefix = prefix + ("    " if is_last else "│   ")
            _render_tree(value, lines, child_prefix)
        else:
            lines.append(f"{prefix}{connector}{name}")


def _get_file_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    doc_exts = {".md", ".rst", ".txt", ".pdf"}
    config_exts = {".toml", ".yaml", ".yml", ".json", ".properties", ".conf", ".cfg", ".ini", ".xml"}
    if ext in doc_exts:
        return "doc"
    if ext in config_exts:
        return "config"
    if ext == ".log":
        return "log"
    return "code"


def _collect_report(events) -> str:
    contents = [e.content for e in events if e.type == EventType.STEP_END and e.content]
    return contents[-1] if contents else "（未能生成报告）"


if __name__ == "__main__":
    from pipeline.scanner import scan_project
    from pipeline.llm_filter import llm_filter_files
    from pipeline.decomposer import decompose_into_modules
    from pipeline.scorer import score_and_rank_modules
    from settings import get_lite_config, get_pro_config

    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ctx = PipelineContext(project_path=project_path, project_name="CodeDeepResearch", lite_config=get_lite_config(), pro_config=get_pro_config())
    scan_project(ctx)
    llm_filter_files(ctx)
    decompose_into_modules(ctx)
    score_and_rank_modules(ctx)

    selected = ctx.modules[:1]
    report_dir = os.path.join(os.getcwd(), ".report", ctx.project_name)
    os.makedirs(report_dir, exist_ok=True)

    research_modules(ctx, report_dir, selected)
    print(f"完成：{selected[0].name}")
