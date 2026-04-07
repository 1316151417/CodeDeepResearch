from dataclasses import dataclass, field


@dataclass
class FileInfo:
    path: str
    size: int
    extension: str
    is_text: bool


@dataclass
class Module:
    name: str
    description: str
    files: list[str]
    importance_score: float = 0.0
    research_report: str = ""


@dataclass
class PipelineContext:
    project_path: str
    project_name: str
    run_id: str = ""
    server_url: str = "http://localhost:7890"
    provider: str = "anthropic"
    lite_model: str = "deepseek-chat"
    pro_model: str = "deepseek-chat"
    max_model: str = "deepseek-reasoner"
    max_sub_agents: int = 5
    max_sub_agent_steps: int = 15
    settings: dict = field(default_factory=dict)

    # Stage 1: scanner output
    all_files: list[FileInfo] = field(default_factory=list)
    tree_text: str = ""

    # Stage 2: basic filter output
    filtered_files: list[FileInfo] = field(default_factory=list)

    # Stage 3: LLM filter output
    important_files: list[FileInfo] = field(default_factory=list)

    # Stage 4: decomposer output
    modules: list[Module] = field(default_factory=list)

    # Stage 5: scorer output
    ranked_modules: list[Module] = field(default_factory=list)
    selected_modules: list[Module] = field(default_factory=list)

    # Stage 7: aggregator output
    final_report: str = ""
