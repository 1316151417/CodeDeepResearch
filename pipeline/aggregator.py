from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import AGGREGATOR_SYSTEM, AGGREGATOR_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


def aggregate_reports(ctx: PipelineContext) -> None:
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    module_reports = "\n\n---\n\n".join(
        f"### 模块：{m.name}\n\n{m.research_report}"
        for m in ctx.selected_modules
    )

    system_prompt = AGGREGATOR_SYSTEM.format(
        project_name=ctx.project_name,
        tree_text=ctx.tree_text,
    )
    user_msg = AGGREGATOR_USER.format(
        project_name=ctx.project_name,
        module_reports=module_reports,
    )

    messages = [SystemMessage(system_prompt), UserMessage(user_msg)]

    print(f"  汇总 agent 第 1 阶段：工具研究（最多 {ctx.max_sub_agent_steps - 1} 步）...", flush=True)
    events = react_stream(
        messages=messages,
        tools=tools,
        provider=ctx.provider,
        max_steps=ctx.max_sub_agent_steps - 1,  # 留 1 步给最终生成
    )

    # 收集研究阶段的输出
    step_contents = {}
    step_count = 0
    for event in events:
        if event.type == EventType.STEP_START:
            step_count += 1
            print(f"  汇总 agent 步骤 {step_count}...", flush=True)
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
            print(f"  汇总 agent 步骤 {event.step} 完成，内容 {len(event.content)} 字符", flush=True)
        if event.type == EventType.TOOL_CALL:
            print(f"  汇总 agent 调用工具: {event.tool_name}", flush=True)

    # 附上之前的研究内容
    best_research = max(step_contents.values(), key=len) if step_contents else ""
    print(f"  研究阶段共 {step_count} 步，最佳内容 {len(best_research)} 字符", flush=True)

    # 第 2 阶段：最终生成（无工具）
    final_messages = [
        SystemMessage(system_prompt),
        UserMessage(user_msg),
    ]
    if best_research:
        final_messages.append(UserMessage(
            f"以下是之前的研究过程和结论：\n{best_research[:5000]}\n\n"
            f"请直接输出完整的中文项目分析报告。不再调用任何工具。"
        ))
    final_messages.append(UserMessage("请直接输出完整的中文项目分析报告。不再调用任何工具。"))

    print(f"  汇总 agent 第 2 阶段：最终生成（无工具）...", flush=True)
    events2 = react_stream(
        messages=final_messages,
        tools=[],  # 无工具
        provider=ctx.provider,
        max_steps=ctx.max_sub_agent_steps,
    )

    final_contents = {}
    final_count = 0
    for event in events2:
        if event.type == EventType.STEP_START:
            final_count += 1
            print(f"  汇总 agent 最终步骤 {final_count}...", flush=True)
        if event.type == EventType.STEP_END and event.content:
            final_contents[event.step] = event.content
            print(f"  汇总 agent 最终步骤 {event.step} 完成，内容 {len(event.content)} 字符", flush=True)

    if final_contents:
        ctx.final_report = max(final_contents.values(), key=len)
    elif best_research:
        print(f"  警告：最终生成无内容，使用研究阶段结果", flush=True)
        ctx.final_report = best_research
    else:
        ctx.final_report = "# 错误：未能生成报告"