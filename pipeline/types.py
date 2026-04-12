from dataclasses import dataclass, field


@dataclass
class FileInfo:
    path: str
    size: int
    file_type: str = ""  # code, doc, config, log
    is_important: bool = True


@dataclass
class Module:
    name: str
    description: str
    files: list[str]
    score: float = 0.0
    research_report: str = ""


@dataclass
class PipelineContext:
    project_path: str
    project_name: str
    provider: str = "anthropic"
    lite_model: str = "deepseek-chat"
    pro_model: str = "deepseek-chat"
    max_model: str = "deepseek-reasoner"
    max_sub_agent_steps: int = 30
    research_parallel: bool = False
    research_threads: int = 4
    settings: dict = field(default_factory=dict)

    # Stage 1: scanner output
    all_files: list[FileInfo] = field(default_factory=list)

    # Stage 3: decomposer output
    modules: list[Module] = field(default_factory=list)

    # Stage 5: aggregator output
    final_report: str = ""
