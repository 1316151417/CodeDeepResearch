"""
Filesystem tools for ReAct agent - read_file, list_directory, glob_pattern, grep_content, scan_directory.
"""
import os
import re
from contextvars import ContextVar
from pathlib import Path

import pathspec

from base.types import tool

# Context variable for project root - thread-safe for concurrent research
_project_root_var: ContextVar[str] = ContextVar('project_root', default='')

MAX_READ_SIZE = 20 * 1024  # 20KB - 控制上下文膨胀
MAX_GREP_RESULTS = 100
MAX_SCAN_RESULTS = 500

EXCLUDE_PATTERNS = [
    ".git/", ".svn/", ".hg/", ".venv/", "venv/",
    "__pycache__/", "*.pyc", "*.pyo", ".DS_Store",
    "node_modules/", ".idea/", ".vscode/",
]

_exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", EXCLUDE_PATTERNS)


def _load_gitignore_spec(root: str) -> pathspec.PathSpec | None:
    gitignore_path = os.path.join(root, ".gitignore")
    if not os.path.isfile(gitignore_path):
        return None
    with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
        return pathspec.PathSpec.from_lines("gitwildmatch", f)


def set_project_root(path: str) -> None:
    """设置当前研究会话的项目根目录（线程安全）。"""
    _project_root_var.set(path)


def get_project_root() -> str:
    """获取当前研究会话的项目根目录。"""
    return _project_root_var.get()


@tool
def read_file(file_path: str) -> str:
    """Read the full contents of a file.

    Args:
        file_path: Relative path from the project root
    """
    project_root = get_project_root()
    full_path = os.path.join(project_root, file_path) if project_root else file_path
    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_READ_SIZE)
        if os.path.getsize(full_path) > MAX_READ_SIZE:
            content += f"\n\n... [truncated, file exceeds {MAX_READ_SIZE // 1024}KB]"
        return content
    except FileNotFoundError:
        return f"Error: File not found: {file_path}"
    except IsADirectoryError:
        return f"Error: {file_path} is a directory, not a file"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def list_directory(dir_path: str) -> str:
    """List files and subdirectories in a directory.

    Args:
        dir_path: Relative path from the project root, use '.' for root
    """
    project_root = get_project_root()
    full_path = os.path.join(project_root, dir_path) if project_root else dir_path
    try:
        entries = sorted(os.listdir(full_path))
        lines = []
        for name in entries:
            child = os.path.join(full_path, name)
            if os.path.isdir(child):
                lines.append(f"DIR:  {name}/")
            else:
                size = os.path.getsize(child)
                lines.append(f"FILE: {name} ({size} bytes)")
        return "\n".join(lines) if lines else "(empty directory)"
    except FileNotFoundError:
        return f"Error: Directory not found: {dir_path}"
    except NotADirectoryError:
        return f"Error: {dir_path} is not a directory"
    except Exception as e:
        return f"Error listing directory: {e}"


@tool
def glob_pattern(pattern: str) -> str:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern like '**/*.py' or 'src/**/*.ts'
    """
    project_root = get_project_root()
    root = Path(project_root) if project_root else Path.cwd()
    matches = sorted(root.glob(pattern))
    results = []
    for m in matches:
        rel = os.path.relpath(m, project_root) if project_root else m
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        results.append(rel)
    if not results:
        return "No files matched the pattern."
    return "\n".join(str(r) for r in results)


@tool
def grep_content(pattern: str, file_pattern: str = "**/*") -> str:
    """Search for a regex pattern across files.

    Args:
        pattern: Regular expression pattern to search for
        file_pattern: Glob pattern to limit which files to search, default all files
    """
    project_root = get_project_root()
    root = Path(project_root) if project_root else Path.cwd()
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    results = []
    for match_path in sorted(root.glob(file_pattern)):
        if not match_path.is_file():
            continue
        rel = os.path.relpath(match_path, project_root) if project_root else match_path
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        try:
            with open(match_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_no, line in enumerate(f, 1):
                    if regex.search(line):
                        results.append(f"{rel}:{line_no}: {line.rstrip()}")
                        if len(results) >= MAX_GREP_RESULTS:
                            return "\n".join(results) + f"\n... [truncated at {MAX_GREP_RESULTS} results]"
        except Exception:
            continue

    if not results:
        return "No matches found."
    return "\n".join(results)


@tool
def scan_directory(dir_path: str, max_depth: int = 3) -> str:
    """Recursively list all files in a directory with built-in filtering.
    Automatically skips .git, node_modules, .venv, __pycache__, .idea, .vscode, etc.
    Also respects .gitignore rules.

    Args:
        dir_path: Relative path from the project root, use '.' for root
        max_depth: Maximum directory depth to scan, default 3
    """
    project_root = get_project_root()
    full_path = os.path.join(project_root, dir_path) if project_root else dir_path

    if not os.path.isdir(full_path):
        return f"Error: Directory not found: {dir_path}"

    gitignore_spec = _load_gitignore_spec(project_root)
    lines = []
    for dirpath, dirnames, filenames in os.walk(full_path):
        rel_dir = os.path.relpath(dirpath, full_path)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if depth >= max_depth:
            dirnames.clear()
            continue

        dirnames[:] = sorted([
            d for d in dirnames
            if not _exclude_spec.match_file(d + "/")
            and (gitignore_spec is None or not gitignore_spec.match_file(
                os.path.join(rel_dir, d) + "/" if rel_dir != "." else d + "/"
            ))
        ])

        for fname in sorted(filenames):
            rel_path = os.path.join(rel_dir, fname) if rel_dir != "." else fname
            if _exclude_spec.match_file(rel_path):
                continue
            if gitignore_spec is not None and gitignore_spec.match_file(rel_path):
                continue
            lines.append(rel_path)
            if len(lines) >= MAX_SCAN_RESULTS:
                return f"Found {len(lines)}+ files (truncated):\n" + "\n".join(lines)

    if not lines:
        return "(no files found)"
    return f"Found {len(lines)} files:\n" + "\n".join(lines)
