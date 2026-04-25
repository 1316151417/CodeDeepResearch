from dataclasses import dataclass, field


@dataclass
class FileInfo:
    path: str


@dataclass
class Section:
    """Level 2: 子节."""
    name: str
    description: str
    files: list[str]
    research_report: str = ""


# 兼容 researcher.py
Module = Section


@dataclass
class Chapter:
    """Level 1: 章."""
    name: str
    description: str
    sections: list[Section] = field(default_factory=list)


@dataclass
class PipelineContext:
    project_path: str
    project_name: str
    lite_config: dict = field(default_factory=dict)
    pro_config: dict = field(default_factory=dict)
    max_config: dict = field(default_factory=dict)
    max_sub_agent_steps: int = 30
    research_parallel: bool = False
    research_threads: int = 4
    settings: dict = field(default_factory=dict)

    # Stage 1: explorer output
    all_files: list[FileInfo] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)

    # Stage 3: aggregator output
    final_report: str = ""
