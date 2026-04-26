"""Pipeline 主入口：2 阶段编排."""
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from langfuse import observe, propagate_attributes

from settings import load_settings, get_config
from pipeline.types import PipelineContext
from pipeline.explorer import generate_toc
from pipeline.researcher import generate_topic_content


def _observed(name, fn, *args, session_id, **kwargs):
    """通用 Langfuse 观察包装。"""
    with propagate_attributes(session_id=session_id):
        return observe(name=name)(fn)(*args, **kwargs)


def _build_wiki(topics) -> dict:
    """构建 wiki.json 结构化数据。"""
    sections = {}
    for t in topics:
        sections.setdefault(t.section_name, []).append(t)

    result = []
    for sec_name, sec_topics in sections.items():
        groups = {}
        section_entry = {"section": sec_name, "groups": []}

        for t in sec_topics:
            entry = {
                "name": t.name,
                "slug": t.slug,
                "level": t.level,
                "file": f"{t.slug}.md",
            }
            if t.group_name:
                groups.setdefault(t.group_name, []).append(entry)
            else:
                section_entry["groups"].append({"topics": [entry]})

        for group_name, group_topics in groups.items():
            section_entry["groups"].append({"name": group_name, "topics": group_topics})

        result.append(section_entry)

    return {"sections": result}


def run_pipeline(settings_path: str | None = None) -> None:
    """运行完整分析流水线，输出到当前目录的 .zread/ 下。"""
    session_id = f"pipeline-{uuid.uuid4().hex[:8]}"

    settings = load_settings(settings_path)
    project_path = os.getcwd()
    project_name = os.path.basename(project_path)

    lite_config = get_config("lite")
    pro_config = get_config("pro")
    max_config = get_config("max")
    max_sub_agent_steps = settings["max_sub_agent_steps"]
    research_parallel = settings["research_parallel"]
    research_threads = settings["research_threads"]

    print(f"模型配置: lite={lite_config['model']}, pro={pro_config['model']}, max={max_config['model']}")

    # .zread 目录结构
    zread_dir = os.path.join(project_path, ".zread")
    versions_dir = os.path.join(zread_dir, "versions")
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    version_dir = os.path.join(versions_dir, timestamp)
    os.makedirs(version_dir, exist_ok=True)
    print(f"报告输出目录: {version_dir}")

    # 更新 current 指针
    current_path = os.path.join(zread_dir, "current")
    with open(current_path, "w", encoding="utf-8") as f:
        f.write(f"versions/{timestamp}")

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

    # ====== 阶段 1: 章节拆分 ======
    print(f"\n{'='*60}\n阶段 1/2: 章节拆分 [{project_name}]\n{'='*60}")
    ctx = _observed("generate_toc", generate_toc, ctx, session_id=session_id)
    print(f"  识别到 {len(ctx.topics)} 个主题:")
    for topic in ctx.topics:
        group = f" ({topic.group_name})" if topic.group_name else ""
        print(f"    [{topic.section_name}] {topic.name} [{topic.level}]{group}")

    # 保存 TOC
    toc_path = os.path.join(version_dir, "toc.xml")
    with open(toc_path, "w", encoding="utf-8") as f:
        f.write(ctx.toc_xml)

    # ====== 阶段 2: 内容生成 ======
    print(f"\n{'='*60}\n阶段 2/2: 内容生成\n{'='*60}")

    def _process_topic(topic):
        """处理单个 topic: observe + 生成 + 即时写文件。"""
        try:
            topic.content = _observed(
                f"generate_content: {topic.name}",
                generate_topic_content, ctx, topic,
                session_id=session_id,
            )
            path = os.path.join(version_dir, f"{topic.slug}.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(topic.content)
            print(f"  ✓ 主题完成: {topic.name}")
        except Exception as e:
            print(f"  ✗ 主题失败: {topic.name} - {e}")

    if research_parallel:
        print(f"  并行模式: {research_threads} 线程, {len(ctx.topics)} 个主题")
        with ThreadPoolExecutor(max_workers=research_threads) as executor:
            futures = {executor.submit(_process_topic, t): t for t in ctx.topics}
            for future in as_completed(futures):
                future.result()
    else:
        print(f"  串行模式: {len(ctx.topics)} 个主题")
        for topic in ctx.topics:
            _process_topic(topic)

    # 保存 wiki.json
    wiki = _build_wiki(ctx.topics)
    wiki_path = os.path.join(version_dir, "wiki.json")
    with open(wiki_path, "w", encoding="utf-8") as f:
        json.dump(wiki, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"分析完成！共 {len(ctx.topics)} 个主题报告")
    print(f"报告目录: {version_dir}")
    print(f"{'='*60}")
