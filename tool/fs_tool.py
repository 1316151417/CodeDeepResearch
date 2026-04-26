"""文件系统工具 — 3 个工具：get_dir_structure, view_file_in_detail, run_bash."""
import os
import subprocess
import sys
from contextvars import ContextVar

from base.types import tool

# ---------------------------------------------------------------------------
# 项目根目录（线程安全）
# ---------------------------------------------------------------------------
_project_root_var: ContextVar[str] = ContextVar("_project_root_var", default="")


def set_project_root(path: str) -> None:
    _project_root_var.set(os.path.abspath(path))


def get_project_root() -> str:
    return _project_root_var.get()


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
MAX_READ_SIZE = 20 * 1024  # 20KB
MAX_BASH_OUTPUT = 50_000

# 自动过滤的目录名
_SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "vendor", ".venv", "venv",
    "__pycache__", ".idea", ".vscode", ".DS_Store", "dist", "build",
    ".next", ".nuxt", ".cache", ".tox", ".mypy_cache", ".pytest_cache",
    ".eggs", "*.egg-info",
}


# ---------------------------------------------------------------------------
# 工具实现
# ---------------------------------------------------------------------------

@tool
def get_dir_structure(dir_path: str = ".", max_depth: int = 3) -> str:
    """获取本地目录结构。以树形文本展示目录内容，支持指定子目录和最大递归深度。
    自动过滤 .gitignore 中的条目和常见依赖目录（node_modules、vendor 等）。
    dir_path 使用相对于工作目录的路径，"." 表示根目录。
    Args:
        dir_path: 相对于工作目录的路径
        max_depth: 最大递归深度
    """
    root = get_project_root()
    target = os.path.normpath(os.path.join(root, dir_path))
    if not os.path.isdir(target):
        return f"错误：{dir_path} 不是有效目录"

    lines = []
    _walk_dir(target, lines, prefix="", depth=0, max_depth=max_depth)
    return "\n".join(lines) if lines else f"（空目录：{dir_path}）"


def _walk_dir(path: str, lines: list, prefix: str, depth: int, max_depth: int) -> None:
    if depth >= max_depth:
        return
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        lines.append(f"{prefix}（无权限）")
        return

    # 过滤掉不需要的目录/文件
    filtered = []
    for name in entries:
        if name in _SKIP_DIRS:
            continue
        if name.startswith(".") and name not in (".env", ".env.example"):
            continue
        filtered.append(name)

    for i, name in enumerate(filtered):
        full = os.path.join(path, name)
        is_last = i == len(filtered) - 1
        connector = "└── " if is_last else "├── "
        if os.path.isdir(full):
            lines.append(f"{prefix}{connector}{name}/")
            child_prefix = prefix + ("    " if is_last else "│   ")
            _walk_dir(full, lines, child_prefix, depth + 1, max_depth)
        else:
            lines.append(f"{prefix}{connector}{name}")


@tool
def view_file_in_detail(file_path: str, start_line: int = 1, end_line: int = 200, show_line_numbers: bool = True) -> str:
    """查看本地文件内容。支持指定起始/结束行号（默认前 200 行）和是否显示行号。
    file_path 使用相对于工作目录的路径。
    Args:
        file_path: 相对于工作目录的文件路径
        start_line: 起始行号（从 1 开始）
        end_line: 结束行号
        show_line_numbers: 是否显示行号
    """
    root = get_project_root()
    target = os.path.normpath(os.path.join(root, file_path))

    if not os.path.isfile(target):
        return f"错误：{file_path} 不是有效文件"

    if os.path.getsize(target) > MAX_READ_SIZE * 5:
        return f"警告：文件过大（{os.path.getsize(target)} 字节），建议分段查看"

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        return f"错误：无法读取文件 - {e}"

    # 调整行号范围
    start = max(1, start_line)
    end = min(len(all_lines), end_line)
    selected = all_lines[start - 1:end]

    if show_line_numbers:
        width = len(str(end))
        result_lines = [f"{str(i):>{width}} | {line.rstrip()}" for i, line in zip(range(start, end + 1), selected)]
    else:
        result_lines = [line.rstrip() for line in selected]

    header = f"文件: {file_path} (行 {start}-{end}, 共 {len(all_lines)} 行)"
    return header + "\n" + "\n".join(result_lines)


# run_bash 白名单命令前缀
_ALLOWED_COMMANDS = {
    "ls", "find", "cat", "grep", "head", "tail", "wc", "file", "du", "stat",
    "which", "type", "echo", "pwd", "git", "diff", "sort", "uniq", "awk",
    "sed", "tr", "cut", "xargs", "tee", "date", "uname", "whoami",
}
_DANGEROUS_PATTERNS = {
    "rm ", "mv ", "cp ", "chmod ", "chown ", "kill ", "sudo ",
    "curl ", "wget ", ">", ">>", "|", "&&", ";", "`", "$(",
    "python", "node", "bash", "sh ", "zsh", "npm ", "pip ",
    "uv ", "docker", "make",
}


@tool
def run_bash(command: str) -> str:
    """在本地仓库目录中执行只读 shell 命令。仅允许信息查询类命令（ls, find, cat, grep, head, tail, wc, git log, git show 等）。
    禁止写入、删除、修改文件或执行程序的命令。命令在工作目录下执行，超时 30 秒。
    Args:
        command: 要执行的 shell 命令
    """
    # 安全检查：检测危险模式
    cmd_lower = command.lower().strip()
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            # 允许 grep 内部的 | (管道)
            if pattern == "|" and cmd_lower.startswith(("grep", "find", "git")):
                continue
            return f"错误：命令包含不允许的操作: {pattern.strip()}"

    # 提取命令前缀做白名单检查
    first_word = command.strip().split()[0] if command.strip() else ""
    # 处理带路径的命令（如 /usr/bin/git）
    first_word = os.path.basename(first_word)
    if first_word not in _ALLOWED_COMMANDS:
        return f"错误：不允许的命令: {first_word}。允许的命令: {', '.join(sorted(_ALLOWED_COMMANDS))}"

    root = get_project_root()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=root,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        if len(output) > MAX_BASH_OUTPUT:
            output = output[:MAX_BASH_OUTPUT] + f"\n...（输出截断，共 {len(output)} 字符）"
        return output.strip() if output.strip() else "（无输出）"
    except subprocess.TimeoutExpired:
        return "错误：命令执行超时（30 秒）"
    except Exception as e:
        return f"错误：命令执行失败 - {e}"
