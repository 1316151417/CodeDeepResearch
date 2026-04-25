"""Pipeline 主入口：4 阶段编排."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from langfuse import observe, propagate_attributes

from settings import load_settings, get_config
from pipeline.types import PipelineContext
from pipeline.scanner import scan_project
from pipeline.decomposer import decompose_into_modules
from pipeline.researcher import prepare_research, research_one_module
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

    ctx = PipelineContext(
        project_path=project_path,
        project_name=project_name,
        lite_config=lite_config,
        pro_config=pro_config,
        max_config=max_config,
        max_sub_agent_steps=max_sub_agent_steps,
        research_parallel=research_parallel,
        research_threads=research_threads,
        settings=settings,
    )

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    report_dir = os.path.join(os.getcwd(), ".report", project_name, timestamp)
    os.makedirs(report_dir, exist_ok=True)
    print(f"报告输出目录: {report_dir}")

    # ====== 阶段 1: 扫描 ======
    print(f"\n{'='*60}\n阶段 1/4: 扫描项目 [{project_name}]\n{'='*60}")
    _observed("scan_project", scan_project, ctx, session_id=session_id)
    print(f"  扫描到 {len(ctx.all_files)} 个文件")

    # ====== 阶段 2: 模块拆分 ======
    print(f"\n{'='*60}\n阶段 2/4: 模块拆分\n{'='*60}")
    _observed("decompose_into_modules", decompose_into_modules, ctx, session_id=session_id)
    print(f"  识别到 {len(ctx.modules)} 个模块:")
    for m in ctx.modules:
        print(f"    - {m.name}: {m.description} ({len(m.files)} 个文件)")

    # ====== 阶段 3: 深度研究 ======
    print(f"\n{'='*60}\n阶段 3/4: 子模块深度研究\n{'='*60}")
    tools, file_tree = prepare_research(ctx)
    if ctx.research_parallel:
        print(f"  并行模式: {ctx.research_threads} 线程, {len(ctx.modules)} 个模块")
        with ThreadPoolExecutor(max_workers=ctx.research_threads) as executor:
            futures = {
                executor.submit(_observed_research_module, ctx, m, tools, report_dir, file_tree, session_id): m
                for m in ctx.modules
            }
            for future in as_completed(futures):
                module = futures[future]
                try:
                    future.result()
                    print(f"  ✓ 模块完成: {module.name}")
                except Exception as e:
                    print(f"  ✗ 模块失败: {module.name} - {e}")
    else:
        print(f"  串行模式: {len(ctx.modules)} 个模块")
        for m in ctx.modules:
            _observed_research_module(ctx, m, tools, report_dir, file_tree, session_id)

    # ====== 阶段 4: 汇总报告 ======
    print(f"\n{'='*60}\n阶段 4/4: 汇总最终报告\n{'='*60}")
    _observed("aggregate_reports", aggregate_reports, ctx, ctx.modules, session_id=session_id)

    final_path = os.path.join(report_dir, f"最终报告-{ctx.project_name}.md")
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(ctx.final_report)

    print(f"\n{'='*60}")
    print(f"分析完成！共 {len(ctx.modules)} 个模块报告 + 1 份最终报告")
    print(f"报告目录: {report_dir}")
    print(f"{'='*60}")
    return ctx.final_report


def _observed_research_module(ctx, module, tools, report_dir, file_tree, session_id):
    with propagate_attributes(session_id=session_id):
        return observe(name=f"research_module:{module.name}")(research_one_module)(ctx, module, tools, report_dir, file_tree)
