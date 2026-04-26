"""Pipeline 主入口：2 阶段编排."""
import os
import uuid
from datetime import datetime

from langfuse import observe, propagate_attributes

from settings import load_settings, get_config
from pipeline.types import PipelineContext
from pipeline.explorer import generate_toc
from pipeline.researcher import generate_content
from pipeline.utils import assemble_final_report


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

    # ====== 阶段 1: 章节拆分 ======
    print(f"\n{'='*60}\n阶段 1/2: 章节拆分 [{project_name}]\n{'='*60}")
    ctx = _observed("generate_toc", generate_toc, ctx, session_id=session_id)
    print(f"  识别到 {len(ctx.topics)} 个主题:")
    for topic in ctx.topics:
        group = f" ({topic.group_name})" if topic.group_name else ""
        print(f"    [{topic.section_name}] {topic.name} [{topic.level}]{group}")

    # 保存 TOC
    toc_path = os.path.join(report_dir, "toc.xml")
    with open(toc_path, "w", encoding="utf-8") as f:
        f.write(ctx.toc_xml)

    # ====== 阶段 2: 内容生成 ======
    print(f"\n{'='*60}\n阶段 2/2: 内容生成\n{'='*60}")
    ctx = _observed("generate_content", generate_content, ctx, session_id=session_id)

    # 写入各主题文件
    for topic in ctx.topics:
        path = os.path.join(report_dir, f"{topic.slug}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(topic.content)

    # 拼接最终报告
    ctx.final_report = assemble_final_report(ctx.topics)
    final_path = os.path.join(report_dir, f"full-report-{ctx.project_name}.md")
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(ctx.final_report)

    print(f"\n{'='*60}")
    print(f"分析完成！共 {len(ctx.topics)} 个主题报告 + 1 份完整报告")
    print(f"报告目录: {report_dir}")
    print(f"{'='*60}")
    return ctx.final_report
