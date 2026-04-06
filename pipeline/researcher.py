import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from base.types import EventType, SystemMessage, UserMessage
from agent.react_agent import stream as react_stream
from pipeline.types import PipelineContext, Module
from prompt.pipeline_prompts import SUB_AGENT_SYSTEM, SUB_AGENT_USER, EVAL_AGENT_SYSTEM, EVAL_AGENT_USER
from tool.fs_tool import set_project_root, read_file, list_directory, glob_pattern, grep_content


def research_modules(ctx: PipelineContext, report_dir: str) -> None:
    settings = ctx.settings
    parallel = settings.get("parallel_research", True)
    max_eval_rounds = settings.get("max_eval_rounds", 3)

    set_project_root(ctx.project_path)
    tools = [read_file, list_directory, glob_pattern, grep_content]
    total = len(ctx.selected_modules)

    if parallel and total > 1:
        print(f"  并行研究 {total} 个模块（最多 {max_eval_rounds} 轮评估）", flush=True)
        with ThreadPoolExecutor(max_workers=min(total, 4)) as executor:
            futures = {}
            for module in ctx.selected_modules:
                future = executor.submit(
                    _research_single_module,
                    ctx, module, tools,
                    max_eval_rounds, report_dir, verbose=False,
                )
                futures[future] = module

            for future in as_completed(futures):
                module = futures[future]
                try:
                    # 每个模块最多等 10 分钟，超时则放弃该模块
                    future.result(timeout=600)
                    print(f"  ✓ [{module.name}] 完成 ({len(module.research_report)} 字符)", flush=True)
                except FuturesTimeoutError:
                    print(f"  ✗ [{module.name}] 研究超时（>600秒），强制跳过", flush=True)
                    module.research_report = f"# 模块 {module.name} 分析报告\n\n研究超时，未能完成。"
                    _write_module_report(report_dir, module)
                except Exception as e:
                    import traceback
                    print(f"  ✗ [{module.name}] 失败: {e}", flush=True)
                    print(f"  ✗ 堆栈: {traceback.format_exc()}", flush=True)
                    module.research_report = f"# 模块 {module.name} 分析报告\n\n研究过程出错: {e}"
                    _write_module_report(report_dir, module)
    else:
        print(f"  串行研究 {total} 个模块", flush=True)
        for module in ctx.selected_modules:
            _research_single_module(
                ctx, module, tools,
                max_eval_rounds, report_dir, verbose=True,
            )


def _research_single_module(
    ctx: PipelineContext,
    module: Module,
    tools: list,
    max_eval_rounds: int,
    report_dir: str,
    verbose: bool = True,
) -> None:
    tag = f"[{module.name}]"
    _print(verbose, f"  {tag} 开始研究 ({len(module.files)} 个文件)")

    # === 阶段 1：多轮生成 + 评估反馈 ===
    for round_num in range(1, max_eval_rounds + 1):
        _print(verbose, f"  {tag} === 第 {round_num}/{max_eval_rounds} 轮 ===")

        _print(verbose, f"  {tag} 构建提示词...")
        messages = _build_generate_messages(ctx, module, round_num)

        _print(verbose or round_num == 1, f"  {tag} 调用 ReAct agent 生成报告...")
        events = react_stream(
            messages=messages,
            tools=tools,
            provider=ctx.provider,
            max_steps=ctx.max_sub_agent_steps,
        )
        report = _collect_agent_output(events, tag, verbose)
        module.research_report = report

        _print(verbose, f"  {tag} 生成完毕，报告 {len(report)} 字符")

        if round_num >= max_eval_rounds:
            print(f"  {tag} 达到最大轮次，进入最终生成", flush=True)
            break

        # 评估报告
        print(f"  {tag} 正在评估报告质量...", flush=True)
        eval_result = _evaluate_report(ctx, module, report)
        score = eval_result.get("total_score", "?")

        if eval_result.get("pass", False):
            print(f"  {tag} 评估通过 (分数: {score})，进入最终生成", flush=True)
            break
        else:
            suggestions = eval_result.get("suggestions", [])
            print(f"  {tag} 评估未通过 (分数: {score})，改进后重试", flush=True)
            if verbose:
                for s in suggestions:
                    print(f"    → {s}", flush=True)

    # === 阶段 2：最终无工具生成报告 ===
    _print(verbose, f"  {tag} 构建最终报告（无工具模式）...")
    final_messages = _build_final_messages(ctx, module)
    final_directive = "已收集足够上下文，请立即生成完整的中文分析报告。不再调用任何工具，直接输出报告。"
    final_messages.append(UserMessage(final_directive))

    _print(verbose, f"  {tag} 最终生成，无工具模式...")
    events = react_stream(
        messages=final_messages,
        tools=[],  # 无工具
        provider=ctx.provider,
        max_steps=ctx.max_sub_agent_steps,
    )
    report = _collect_agent_output(events, tag, verbose)
    module.research_report = report
    _print(verbose, f"  {tag} 最终报告 {len(report)} 字符")

    # 写入报告
    _write_module_report(report_dir, module)
    print(f"  {tag} 报告已保存", flush=True)


def _build_generate_messages(ctx: PipelineContext, module: Module, round_num: int) -> list:
    system_prompt = SUB_AGENT_SYSTEM.format(
        module_name=module.name,
        project_name=ctx.project_name,
        module_description=module.description,
        module_files="\n".join(f"  - {f}" for f in module.files),
    )
    user_prompt = SUB_AGENT_USER.format(module_name=module.name)

    messages = [SystemMessage(system_prompt), UserMessage(user_prompt)]

    if round_num > 1 and module.research_report:
        improvement_hints = getattr(module, '_eval_suggestions', [])
        hints_text = "\n".join(f"  - {s}" for s in improvement_hints) if improvement_hints else "无具体建议"
        messages.append(UserMessage(
            f"上一轮评估发现以下不足，请针对性改进：\n{hints_text}\n\n"
            f"请重新读取相关文件，补充缺失的分析，输出改进后的完整报告。"
        ))

    return messages


def _build_final_messages(ctx: PipelineContext, module: Module) -> list:
    """最终生成阶段：基于已有报告和评估建议，直接生成最终报告"""
    system_prompt = SUB_AGENT_SYSTEM.format(
        module_name=module.name,
        project_name=ctx.project_name,
        module_description=module.description,
        module_files="\n".join(f"  - {f}" for f in module.files),
    )
    user_prompt = SUB_AGENT_USER.format(module_name=module.name)

    messages = [SystemMessage(system_prompt), UserMessage(user_prompt)]

    # 附上之前的报告和研究结论
    if module.research_report:
        suggestions = getattr(module, '_eval_suggestions', [])
        hints_text = "\n".join(f"  - {s}" for s in suggestions) if suggestions else "无具体建议"
        messages.append(UserMessage(
            f"以下是之前的研究结论，可作为参考：\n{module.research_report[:3000]}\n\n"
            f"评估建议：\n{hints_text}\n\n"
            f"请综合以上信息，生成最终的完整分析报告。"
        ))

    return messages


def _evaluate_report(ctx: PipelineContext, module: Module, report: str) -> dict:
    from pipeline.llm_filter import _call_llm

    system_prompt = EVAL_AGENT_SYSTEM.format(
        project_name=ctx.project_name,
        module_name=module.name,
        module_description=module.description,
        module_files="\n".join(f"  - {f}" for f in module.files),
    )
    user_prompt = EVAL_AGENT_USER.format(
        module_name=module.name,
        report=report,
    )

    print(f"  [{module.name}] 调用评估 LLM...", flush=True)
    response = _call_llm(ctx.provider, system_prompt, user_prompt)
    print(f"  [{module.name}] 评估响应 {len(response)} 字符: {response[:200]}...", flush=True)

    try:
        result = json.loads(_extract_json(response))
        print(f"  [{module.name}] 评估解析成功: {result}", flush=True)
    except json.JSONDecodeError as e:
        print(f"  [{module.name}] 评估 JSON 解析失败: {e}", flush=True)
        print(f"  [{module.name}] 原始响应: {response[:500]}", flush=True)
        return {"pass": True, "total_score": 30, "suggestions": []}

    module._eval_suggestions = result.get("suggestions", [])
    return result


def _collect_agent_output(events, tag: str, verbose: bool) -> str:
    step_contents = {}
    had_tool_calls_on_last_step = False
    tool_call_count = 0
    step_count = 0

    for event in events:
        if event.type == EventType.STEP_START:
            had_tool_calls_on_last_step = False
            step_count += 1
            if not verbose:
                print(f"  {tag} 步骤 {step_count}...", flush=True)
        if event.type == EventType.STEP_END and event.content:
            step_contents[event.step] = event.content
        if event.type == EventType.TOOL_CALL:
            had_tool_calls_on_last_step = True
            tool_call_count += 1
            if not verbose:
                print(f"  {tag}   工具: {event.tool_name}", flush=True)

    if not step_contents:
        return "（未能生成报告）"

    if not had_tool_calls_on_last_step:
        return list(step_contents.values())[-1]
    else:
        return max(step_contents.values(), key=len)


def _write_module_report(report_dir: str, module: Module) -> None:
    path = os.path.join(report_dir, f"模块分析报告-{module.name}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(module.research_report)


def _print(verbose: bool, msg: str) -> None:
    """条件打印，始终 flush"""
    if verbose:
        print(msg, flush=True)


def _extract_json(text: str) -> str:
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