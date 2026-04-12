"""Stage 6: 最终报告汇总 - ReAct agent 整合所有模块报告."""
import json
from pathlib import Path

from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import AGGREGATOR_SYSTEM, AGGREGATOR_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


def aggregate_reports(ctx: PipelineContext, selected: list) -> None:
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    module_reports = "\n\n---\n\n".join(f"### 模块：{m.name}\n\n{m.research_report}" for m in selected)
    file_tree = _build_file_tree(ctx.all_files)
    important_files = list({f for m in selected for f in m.files})

    system = AGGREGATOR_SYSTEM.format(project_name=ctx.project_name)
    messages = [
        SystemMessage(system),
        UserMessage(AGGREGATOR_USER.format(
            project_name=ctx.project_name,
            file_tree=file_tree,
            important_files=json.dumps(important_files, ensure_ascii=False, indent=2),
            module_reports=module_reports,
        )),
    ]

    events = react_stream(messages=messages, tools=tools, provider=ctx.provider, model=ctx.max_model, max_steps=ctx.max_sub_agent_steps)
    ctx.final_report = _collect_report(events)


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


def _collect_report(events) -> str:
    contents = [e.content for e in events if e.type == EventType.STEP_END and e.content]
    return contents[-1] if contents else "（未能生成报告）"


if __name__ == "__main__":
    from dataclasses import dataclass

    @dataclass
    class MockModule:
        name: str
        description: str
        files: list
        research_report: str = ""

    # 简单 mock，不要复杂结构
    ctx = PipelineContext(
        project_path="/Users/zhoujie/IdeaProjects/CodeDeepResearch",
        project_name="CodeDeepResearch",
        provider="anthropic",
        pro_model="deepseek-chat",
        max_model="deepseek-chat",
        max_sub_agent_steps=30,
        all_files=[],
        modules=[],
        settings={},
    )

    # 简单的模块报告 mock
    ctx.modules = [
        MockModule(
            name="agent",
            description="ReAct 智能体循环",
            files=["agent/react_agent.py"],
            research_report="""### 模块：agent

## 模块定位
本模块实现了 ReAct 模式的智能体循环...

## 核心架构图
...

## 关键实现
核心函数 `stream()` 实现了...
""",
        ),
        MockModule(
            name="pipeline",
            description="流水线编排",
            files=["pipeline/researcher.py"],
            research_report="""### 模块：pipeline

## 模块定位
负责整体分析流程的 6 阶段编排...

## 核心架构图
...

## 关键实现
`run_pipeline()` 是主入口...
""",
        ),
    ]

    print("开始汇总测试...", flush=True)
    aggregate_reports(ctx, ctx.modules)
    print(f"\n汇总完成，报告长度: {len(ctx.final_report)} 字符")
    print(ctx.final_report[:500])
