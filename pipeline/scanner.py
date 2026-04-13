import os
import re
from pathlib import Path

from pipeline.types import PipelineContext, FileInfo

# 不重要目录（os.walk 时直接跳过，不进入）
UNIMPORTANT_DIRS = {
    ".git", ".venv", "test", "log", "__pycache__", 
    # 定制化
    "report"
}
# 不重要文件名
UNIMPORTANT_NAMES = {
    ".DS_Store", ".gitignore", "CLAUDE.md", "__init__.py"
}

# 不重要扩展名
UNIMPORTANT_EXTENSIONS = {
    ".log", ".lock"
}

# 文档扩展名
DOC_EXTENSIONS = {
    ".md"
}

# 配置文件
CONFIG_NAMES = {
    ".python-version"
}
# 配置扩展名
CONFIG_EXTENSIONS = {
    ".json", ".xml", ".yml", ".yaml", ".toml"
}


def _get_file_type(path: str) -> str:
    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    if ext in DOC_EXTENSIONS or name in DOC_EXTENSIONS:
        return "doc"
    if ext in CONFIG_EXTENSIONS or name in CONFIG_NAMES:
        return "config"
    return "code"


def _is_important(path: str, name: str = "") -> bool:
    name = name or os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if name in UNIMPORTANT_NAMES or ext in UNIMPORTANT_EXTENSIONS:
        return False
    if any(p in UNIMPORTANT_DIRS for p in Path(path).parts):
        return False
    return True


def scan_project(ctx: PipelineContext) -> None:
    root = Path(ctx.project_path)
    all_files = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in UNIMPORTANT_DIRS and not d.startswith(".")]

        for fname in sorted(filenames):
            rel_dir = os.path.relpath(dirpath, root)
            rel_path = os.path.join(rel_dir, fname) if rel_dir != "." else fname
            full_path = os.path.join(dirpath, fname)

            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue

            important = _is_important(rel_path, fname)
            fi = FileInfo(path=rel_path, size=size, file_type=_get_file_type(rel_path), is_important=important)
            all_files.append(fi)

    ctx.all_files = all_files


if __name__ == "__main__":
    import sys
    from settings import get_lite_config

    project_path = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    ctx = PipelineContext(project_path=project_path, project_name=os.path.basename(project_path), lite_config=get_lite_config())
    scan_project(ctx)

    important = [f for f in ctx.all_files if f.is_important]
    unimportant = [f for f in ctx.all_files if not f.is_important]

    print(f"扫描完成：{len(ctx.all_files)} 个文件，其中 {len(important)} 个重要\n")
    print("=== 重要文件 ===")
    for fi in important:
        print(f"  [{fi.file_type:6}] {fi.path}")
    print(f"\n=== 不重要文件 ({len(unimportant)} 个) ===")
    for fi in unimportant:
        print(f"  [{fi.file_type:6}] {fi.path}")
