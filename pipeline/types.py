from dataclasses import dataclass, field


@dataclass
class Topic:
    """文档目录中的单个主题."""
    name: str           # 中文标题，如 "项目概述"
    slug: str           # URL slug，如 "1-xiang-mu-gai-shu"
    level: str          # "Beginner" | "Intermediate" | "Advanced"
    section_name: str   # 所属章节，如 "快速入门"
    group_name: str = ""  # 可选分组名
    content: str = ""   # Step 2 生成的内容


@dataclass
class PipelineContext:
    project_path: str
    project_name: str
    report_dir: str = ""
    # 模型配置
    lite_config: dict = field(default_factory=dict)
    pro_config: dict = field(default_factory=dict)
    max_config: dict = field(default_factory=dict)
    max_sub_agent_steps: int = 30
    research_parallel: bool = False
    research_threads: int = 4
    settings: dict = field(default_factory=dict)
    # Step 1 输出
    repo_structure: str = ""   # 顶层目录结构（预生成，两步共用）
    toc_xml: str = ""          # 原始 XML TOC
    topics: list[Topic] = field(default_factory=list)
    # Step 2 输出
    final_report: str = ""
