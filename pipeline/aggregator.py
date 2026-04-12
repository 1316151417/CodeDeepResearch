"""Stage 6: 最终报告汇总 - ReAct agent 整合所有模块报告."""
import json

from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext
from prompt.pipeline_prompts import AGGREGATOR_SYSTEM, AGGREGATOR_USER, AGGREGATOR_EVAL_SYSTEM, AGGREGATOR_EVAL_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content
from provider.llm import call_llm, extract_json


def aggregate_reports(ctx: PipelineContext, selected: list) -> None:
    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]

    module_reports = "\n\n---\n\n".join(f"### 模块：{m.name}\n\n{m.research_report}" for m in selected)
    max_eval_rounds = ctx.settings.get("max_eval_rounds", 1)
    final_report = ""
    eval_result = {"suggestions": []}

    # === 阶段 1：多轮生成 + 评估反馈 ===
    for round_num in range(1, max_eval_rounds + 1):
        system_prompt = AGGREGATOR_SYSTEM.format(project_name=ctx.project_name)
        user_msg = AGGREGATOR_USER.format(project_name=ctx.project_name, module_reports=module_reports)
        messages = [SystemMessage(system_prompt), UserMessage(user_msg)]

        print(f"  汇总 agent 第 {round_num}/{max_eval_rounds} 轮：研究阶段...", flush=True)
        events = react_stream(messages=messages, tools=tools, provider=ctx.provider, model=ctx.max_model, max_steps=ctx.max_sub_agent_steps)

        step_contents = _collect_step_contents(events)
        if not step_contents:
            final_report = "# 错误：未能生成报告"
            break

        best_research = max(step_contents.values(), key=len)
        print(f"  研究阶段完成，最佳内容 {len(best_research)} 字符", flush=True)

        if round_num >= max_eval_rounds:
            final_report = best_research
            break

        # 评估报告
        print(f"  汇总 agent 正在评估报告质量...", flush=True)
        eval_result = _evaluate_aggregator_report(ctx, best_research)

        if eval_result.get("pass", False):
            print(f"  汇总 agent 评估通过 (分数: {eval_result.get('total_score')})，进入最终生成", flush=True)
            final_report = best_research
            break
        else:
            suggestions = eval_result.get("suggestions", [])
            print(f"  汇总 agent 评估未通过 (分数: {eval_result.get('total_score')})，改进后重试", flush=True)
            for s in suggestions[:3]:
                print(f"    → {s}", flush=True)
            module_reports = best_research

    # === 阶段 2：最终无工具生成 ===
    system_prompt = AGGREGATOR_SYSTEM.format(project_name=ctx.project_name)
    final_messages = [
        SystemMessage(system_prompt),
        UserMessage(AGGREGATOR_USER.format(project_name=ctx.project_name, module_reports=module_reports)),
        UserMessage(f"以下是之前的研究结论，可作为参考：\n{final_report[:3000]}\n\n评估建议：\n{_get_suggestions_text(eval_result)}\n\n请综合以上信息，生成最终的完整中文项目分析报告。不再调用任何工具，直接输出报告。"),
    ]

    print(f"  汇总 agent 最终生成（无工具模式）...", flush=True)
    events2 = react_stream(messages=final_messages, tools=[], provider=ctx.provider, model=ctx.max_model, max_steps=ctx.max_sub_agent_steps)

    step_contents2 = _collect_step_contents(events2)
    if step_contents2:
        ctx.final_report = max(step_contents2.values(), key=len)
    elif final_report:
        ctx.final_report = final_report
    else:
        ctx.final_report = "# 错误：未能生成报告"


def _collect_step_contents(events) -> dict:
    step_contents = {}
    step_count = 0
    for event in events:
        if event.type == EventType.STEP_START:
            step_count += 1
            print(f"  汇总 agent 步骤 {step_count}...", flush=True)
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
            print(f"  汇总 agent 步骤 {step_count} 完成，内容 {len(event.content)} 字符", flush=True)
        if event.type == EventType.TOOL_CALL:
            print(f"  汇总 agent 调用工具: {event.tool_name}", flush=True)
    return step_contents


def _evaluate_aggregator_report(ctx: PipelineContext, report: str) -> dict:
    system_prompt = AGGREGATOR_EVAL_SYSTEM.format(project_name=ctx.project_name)
    user_prompt = AGGREGATOR_EVAL_USER.format(project_name=ctx.project_name, report=report)

    print(f"  [汇总评估] 调用评估 LLM...", flush=True)
    response = call_llm(ctx.provider, system_prompt, user_prompt, model=ctx.max_model)
    print(f"  [汇总评估] 评估响应 {len(response)} 字符", flush=True)

    try:
        result = json.loads(extract_json(response))
        print(f"  [汇总评估] 评估结果: pass={result.get('pass')}, score={result.get('total_score')}", flush=True)
        return result
    except json.JSONDecodeError as e:
        print(f"  [汇总评估] JSON 解析失败: {e}", flush=True)
        return {"pass": True, "total_score": 30, "suggestions": []}


def _get_suggestions_text(eval_result: dict) -> str:
    suggestions = eval_result.get("suggestions", [])
    if not suggestions:
        return "无具体建议"
    return "\n".join(f"  - {s}" for s in suggestions)
