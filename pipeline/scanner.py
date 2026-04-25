"""Stage 1: 扫描项目文件 - 基于 .gitignore + 默认排除规则."""
import os
from pathlib import Path

import pathspec

from pipeline.types import PipelineContext, FileInfo

# 默认排除模式（.gitignore 通常不覆盖的路径）
DEFAULT_EXCLUDE_PATTERNS = [
    ".git/",
    ".svn/",
    ".hg/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "node_modules/",
    ".idea/",
    ".vscode/",
]


def _load_gitignore_spec(root: Path) -> pathspec.PathSpec | None:
    """解析项目根目录的 .gitignore 文件。"""
    gitignore_path = root / ".gitignore"
    if not gitignore_path.is_file():
        return None
    with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
        return pathspec.PathSpec.from_lines("gitwildmatch", f)


def scan_project(ctx: PipelineContext) -> None:
    root = Path(ctx.project_path)

    default_spec = pathspec.PathSpec.from_lines("gitwildmatch", DEFAULT_EXCLUDE_PATTERNS)
    gitignore_spec = _load_gitignore_spec(root)

    all_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)

        # 剪枝：排除匹配的目录，阻止 os.walk 递归进入
        dirnames[:] = sorted([
            d for d in dirnames
            if not default_spec.match_file(d + "/")
            and (gitignore_spec is None or not gitignore_spec.match_file(
                os.path.join(rel_dir, d) + "/" if rel_dir != "." else d + "/"
            ))
        ])

        for fname in sorted(filenames):
            rel_path = os.path.join(rel_dir, fname) if rel_dir != "." else fname

            # 默认排除规则
            if default_spec.match_file(rel_path):
                continue

            # .gitignore 规则
            if gitignore_spec is not None and gitignore_spec.match_file(rel_path):
                continue

            all_files.append(FileInfo(path=rel_path))

    ctx.all_files = all_files
