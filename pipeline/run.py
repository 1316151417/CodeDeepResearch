"""Pipeline 主入口：6 阶段编排."""
import os
from datetime import datetime

from settings import load_settings, get_lite_model, get_pro_model, get_max_model
from pipeline.types import PipelineContext
from pipeline.scanner import scan_project
from pipeline.llm_filter import llm_filter_files
from pipeline.decomposer import decompose_into_modules
from pipeline.scorer import score_and_rank_modules
from pipeline.researcher import research_modules
from pipeline.aggregator import aggregate_reports


def run_pipeline(
    project_path: str,
    settings_path: str | None = None,
) -> str:
    """运行完整分析流水线。"""
    settings = load_settings(settings_path)
    project_path = os.path.abspath(project_path)
    project_name = os.path.basename(project_path)

    provider = settings["provider"]
    max_sub_agent_steps = settings["max_sub_agent_steps"]
    research_parallel = settings["research_parallel"]
    research_threads = settings["research_threads"]
    lite_model = get_lite_model()
    pro_model = get_pro_model()
    max_model = get_max_model()

    print(f"模型配置: lite={lite_model}, pro={pro_model}, max={max_model}")

    ctx = PipelineContext(
        project_path=project_path,
        project_name=project_name,
        provider=provider,
        lite_model=lite_model,
        pro_model=pro_model,
        max_model=max_model,
        max_sub_agent_steps=max_sub_agent_steps,
        research_parallel=research_parallel,
        research_threads=research_threads,
        settings=settings,
    )

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    report_dir = os.path.join(os.getcwd(), "report", project_name, timestamp)
    os.makedirs(report_dir, exist_ok=True)
    print(f"报告输出目录: {report_dir}")

    # ====== 阶段 1: 扫描 ======
    print(f"\n{'='*60}\n阶段 1/6: 扫描项目 [{project_name}]\n{'='*60}")
    scan_project(ctx)
    print(f"  扫描到 {len(ctx.all_files)} 个文件")

    # ====== 阶段 2: LLM 过滤 ======
    print(f"\n{'='*60}\n阶段 2/6: LLM 智能过滤\n{'='*60}")
    llm_filter_files(ctx)
    important_count = sum(1 for f in ctx.all_files if f.is_important)
    print(f"  保留 {important_count} 个重要文件")

    # ====== 阶段 3: 模块拆分 ======
    print(f"\n{'='*60}\n阶段 3/6: 模块拆分\n{'='*60}")
    decompose_into_modules(ctx)
    print(f"  识别到 {len(ctx.modules)} 个模块:")
    for m in ctx.modules:
        print(f"    - {m.name}: {m.description} ({len(m.files)} 个文件)")

    # ====== 阶段 4: 模块打分 ======
    print(f"\n{'='*60}\n阶段 4/6: 模块重要性打分\n{'='*60}")
    score_and_rank_modules(ctx)
    print(f"  模块评分（从高到低）:")
    for m in ctx.modules:
        print(f"    - {m.name}: {m.score:.0f}分")
    print(f"  共 {len(ctx.modules)} 个模块，全部进行深度研究")

    # ====== 阶段 5: 深度研究 ======
    print(f"\n{'='*60}\n阶段 5/6: 子模块深度研究\n{'='*60}")
    research_modules(ctx, report_dir, ctx.modules)

    # ====== 阶段 6: 汇总报告 ======
    print(f"\n{'='*60}\n阶段 6/6: 汇总最终报告\n{'='*60}")
    aggregate_reports(ctx, ctx.modules)

    final_path = os.path.join(report_dir, f"最终报告-{ctx.project_name}.md")
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(ctx.final_report)

    print(f"\n{'='*60}")
    print(f"分析完成！共 {len(ctx.modules)} 个模块报告 + 1 份最终报告")
    print(f"报告目录: {report_dir}")
    print(f"{'='*60}")
    return ctx.final_report
