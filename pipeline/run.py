"""Pipeline 主入口：3 阶段编排."""
import os
import uuid
from datetime import datetime

from langfuse import observe, propagate_attributes

from settings import load_settings, get_config
from pipeline.types import PipelineContext
from pipeline.explorer import explore_and_decompose
from pipeline.researcher import research_sections
from pipeline.aggregator import aggregate_reports


def _observed(name, fn, *args, session_id, **kwargs):
    """通用 Langfuse 观察包装。"""
    with propagate_attributes(session_id=session_id):
        return observe(name=name)(fn)(*args, **kwargs)


def run_pipeline(
    project_path: str,
    settings_path: str | None = None,
) -> str:
    """运行完整分析流水线。"""
    session_id = f"pipeline-{uuid.uuid4().hex[:8]}"

    settings = load_settings(settings_path)
    project_path = os.path.abspath(project_path)
    project_name = os.path.basename(project_path)

    lite_config = get_config("lite")
    pro_config = get_config("pro")
    max_config = get_config("max")
    max_sub_agent_steps = settings["max_sub_agent_steps"]
    research_parallel = settings["research_parallel"]
    research_threads = settings["research_threads"]

    print(f"模型配置: lite={lite_config['model']}, pro={pro_config['model']}, max={max_config['model']}")

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    report_dir = os.path.join(os.getcwd(), ".report", project_name, timestamp)
    os.makedirs(report_dir, exist_ok=True)
    print(f"报告输出目录: {report_dir}")

    ctx = PipelineContext(
        project_path=project_path,
        project_name=project_name,
        report_dir=report_dir,
        lite_config=lite_config,
        pro_config=pro_config,
        max_config=max_config,
        max_sub_agent_steps=max_sub_agent_steps,
        research_parallel=research_parallel,
        research_threads=research_threads,
        settings=settings,
    )

    # ====== 阶段 1: 探索与分解 ======
    print(f"\n{'='*60}\n阶段 1/3: 探索与分解 [{project_name}]\n{'='*60}")
    ctx = _observed("explore_and_decompose", explore_and_decompose, ctx, session_id=session_id)
    total_sections = sum(len(ch.sections) for ch in ctx.chapters)
    print(f"  识别到 {len(ctx.chapters)} 个章, {total_sections} 个节:")
    for ch in ctx.chapters:
        print(f"    章: {ch.name} - {ch.description}")
        for sec in ch.sections:
            print(f"      节: {sec.name} ({len(sec.files)} 个文件)")

    # ====== 阶段 2: 深度研究 ======
    print(f"\n{'='*60}\n阶段 2/3: 节深度研究\n{'='*60}")
    ctx = _observed("research_sections", research_sections, ctx, session_id=session_id)

    # 写入各节报告
    all_sections = [sec for ch in ctx.chapters for sec in ch.sections]
    for sec in all_sections:
        path = os.path.join(report_dir, f"模块分析报告-{sec.name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(sec.research_report)

    # ====== 阶段 3: 汇总报告 ======
    print(f"\n{'='*60}\n阶段 3/3: 汇总最终报告\n{'='*60}")
    ctx = _observed("aggregate_reports", aggregate_reports, ctx, session_id=session_id)

    # 写入最终报告
    final_path = os.path.join(report_dir, f"最终报告-{ctx.project_name}.md")
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(ctx.final_report)

    print(f"\n{'='*60}")
    print(f"分析完成！共 {len(ctx.chapters)} 章, {total_sections} 节报告 + 1 份最终报告")
    print(f"报告目录: {report_dir}")
    print(f"{'='*60}")
    return ctx.final_report
