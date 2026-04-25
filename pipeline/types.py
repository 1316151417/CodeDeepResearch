from dataclasses import dataclass, field


@dataclass
class FileInfo:
    path: str


@dataclass
class Module:
    name: str
    description: str
    files: list[str]
    research_report: str = ""


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

    # Stage 1: scanner output
    all_files: list[FileInfo] = field(default_factory=list)

    # Stage 2: decomposer output
    modules: list[Module] = field(default_factory=list)

    # Stage 4: aggregator output
    final_report: str = ""
