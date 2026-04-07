import os
import re
from pathlib import Path

from pipeline.types import PipelineContext, FileInfo
from monitor.event_bus import get_event_bus
from monitor.events import PipelineEvent, PipelineEventType

# ====== 排除目录 ======
EXCLUDE_DIRS = {
    # 包管理/构建产物
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "target", "bin", "obj", "out",
    "vendor", "Pods", ".gradle", ".dart_tool",
    # 测试目录
    "test", "tests", "spec", "specs", "__tests__", "testdata", "test_data", "fixtures",
    # 文档目录
    "docs", "doc", "documentation", "wiki",
    # 示例/演示
    "examples", "example", "demo", "demos", "samples", "sample",
    # CI/CD
    ".github", ".gitlab", ".circleci", "jenkins",
    # 数据库迁移/种子
    "migrations", "seeds",
    # IDE/编辑器
    ".idea", ".vscode", ".claude", ".eclipse", ".settings",
}

# ====== 排除扩展名 ======
EXCLUDE_EXTENSIONS = {
    # Python 编译
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe",
    # 图片
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    ".tiff", ".tif", ".raw", ".psd", ".ai",
    # 音视频
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".wmv", ".flv", ".mkv",
    # 压缩包
    ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz", ".lzma", ".cab",
    # 字体
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # 数据库
    ".db", ".sqlite",
    # Java 编译产物
    ".class", ".jar", ".war",
    # 数据文件
    ".npy", ".npz", ".parquet", ".pkl", ".pickle",
    ".csv", ".tsv",
    # Office 文档
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # 配置文件（无逻辑）
    ".properties", ".conf", ".cfg", ".ini",
    # Python 项目配置（TOML/YAML/INI 格式）
    ".toml", ".yaml", ".yml",
}

# ====== 排除文件名 ======
EXCLUDE_NAMES = {
    # 系统文件
    ".DS_Store", "Thumbs.db", ".DS_Store",
    # Lock 文件
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Gemfile.lock",
    "Cargo.lock", "go.sum", "poetry.lock", "uv.lock", "composer.lock",
    # Python 依赖/项目配置文件
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
    "requirements-prod.txt", "requirements-staging.txt",
    "pyproject.toml", "setup.py", "setup.cfg", "MANIFEST.in",
    "Pipfile", "Pipfile.lock", "pyproject.toml",
    # 包管理
    "Makefile", "CMakeLists.txt", "tox.ini", "noxfile.py",
    # 测试配置
    "pytest.ini", ".pytest.ini", "conftest.py", "tox.ini",
    # Lint 配置
    ".flake8", ".pylintrc", "mypy.ini", ".pylintrc",
    ".ruff.toml", ".ruff_cache",
    # 环境配置
    ".env", ".env.local", ".env.production", ".env.development",
    ".env.example", ".env.template",
    # 编辑器配置
    ".editorconfig", ".prettierrc", ".eslintrc", ".babelrc",
    ".prettierrc.js", ".prettierrc.json", ".prettierrc.yaml",
    ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml",
    ".eslintrc.cjs", ".babelrc.js",
    # Git
    ".gitignore", ".gitattributes", ".gitmodules",
    # 其他
    "LICENSE", "COPYING", "NOTICE", "CHANGELOG", "CONTRIBUTING",
    "AUTHORS", "MAINTAINERS", "CODEOWNERS",
}

# ====== 测试/构建文件名模式 ======
EXCLUDE_PATTERNS = [
    re.compile(r"^test_"),           # test_foo.py
    re.compile(r"_test\."),          # foo_test.py / foo_test.go
    re.compile(r"Test\."),           # FooTest.py / FooTest.java
    re.compile(r"Tests\."),          # FooTests.java
    re.compile(r"TestCase\."),       # FooTestCase.java
    re.compile(r"\.spec\."),         # foo.spec.ts / foo.spec.js
    re.compile(r"\.test\."),         # foo.test.ts / foo.test.js
    re.compile(r"\.stories\."),      # foo.stories.tsx
    re.compile(r"\.mock\."),         # foo.mock.ts
    re.compile(r"conftest\."),       # pytest conftest.py
    re.compile(r"^Makefile"),        # Makefile, Makefile.am
    re.compile(r"^Dockerfile"),      # Dockerfile
    re.compile(r"\.dockerfile$", re.IGNORECASE),  # foo.dockerfile
    re.compile(r"^setup\.py$"),      # setup.py (打包配置)
    re.compile(r"^setup\.cfg$"),     # setup.cfg
    re.compile(r"\.config\."),       # webpack.config.js, vite.config.ts
    re.compile(r"^__init__\.py$"),   # __init__.py (包标记，通常无逻辑)
    re.compile(r"^__init__\."),      # __init__.py 或其他 __init__ 文件
]

# ====== 需要排除的路径段（目录级别） ======
EXCLUDE_PATH_SEGMENTS = {
    "test", "tests", "spec", "specs", "__tests__",
    "docs", "doc", "documentation",
    "examples", "example", "demo", "demos", "samples", "sample",
    "migrations", "fixtures", "testdata", "test_data",
}

# ====== 文本文件扩展名（用于 is_text 判断） ======
TEXT_EXTENSIONS = {
    # 编程语言
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".kt", ".kts",
    ".go", ".rs", ".rb", ".php", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".swift", ".m", ".mm", ".scala", ".clj", ".hs",
    ".r", ".R", ".m", ".mm", ".lua", ".pl", ".ex", ".exs",
    ".erl", ".dart", ".zig", ".nim",
    # Web
    ".html", ".css", ".scss", ".less", ".vue", ".svelte",
    # 标记语言（.toml/.yaml/.yml 已移至 EXCLUDE_EXTENSIONS）
    ".xml", ".json",
    ".md", ".rst", ".txt",
    # 脚本
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat",
    # 数据库
    ".sql", ".prisma", ".graphql", ".gql", ".proto",
    # 其他
    ".gitignore", "Dockerfile",
}


def scan_project(ctx: PipelineContext) -> None:
    bus = get_event_bus(server_url=ctx.server_url)
    _publish = lambda et, stage, data, step=1: bus.publish(
        PipelineEvent.new(run_id=ctx.run_id, event_type=et, stage=stage, data=data, step=step)
    ) if ctx.run_id else None

    _publish(PipelineEventType.STAGE_START, "scanner", {"stage_index": 1})
    root = Path(ctx.project_path)

    all_files = []

    for dirpath, dirnames, filenames in os.walk(root):
        # 过滤排除的目录（原地修改 dirnames 影响 os.walk 后续遍历）
        dirnames[:] = [
            d for d in sorted(dirnames)
            if d not in EXCLUDE_DIRS and not d.startswith(".")
        ]

        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""

        for fname in sorted(filenames):
            rel_path = os.path.join(rel_dir, fname) if rel_dir else fname
            full_path = os.path.join(dirpath, fname)
            ext = os.path.splitext(fname)[1].lower()

            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue

            is_text = ext in TEXT_EXTENSIONS

            fi = FileInfo(path=rel_path, size=size, extension=ext, is_text=is_text)
            all_files.append(fi)

    ctx.all_files = all_files
    ctx.tree_text = _build_tree_text(ctx.project_name, all_files)
    ctx.filtered_files = [f for f in all_files if _is_important_file(f)]

    _publish(PipelineEventType.STAGE_SCAN_COMPLETE, "scanner", {
        "all_files_count": len(ctx.all_files),
        "filtered_files_count": len(ctx.filtered_files),
        "excluded_count": len(ctx.all_files) - len(ctx.filtered_files),
    })
    _publish(PipelineEventType.STAGE_END, "scanner", {
        "output_summary": f"{len(ctx.all_files)} files total, {len(ctx.filtered_files)} after basic filter"
    })


def _build_tree_text(project_name: str, files: list[FileInfo]) -> str:
    if not files:
        return f"{project_name}/\n  (empty)"

    tree = {}
    for fi in files:
        parts = Path(fi.path).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = fi.size

    lines = [f"{project_name}/"]
    _render_tree(tree, lines, "")
    return "\n".join(lines)


def _render_tree(node: dict, lines: list, prefix: str) -> None:
    items = sorted(node.items(), key=lambda x: (not isinstance(x[1], dict), x[0]))
    for i, (name, value) in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        if isinstance(value, dict):
            lines.append(f"{prefix}{connector}{name}")
            child_prefix = prefix + ("    " if is_last else "│   ")
            _render_tree(value, lines, child_prefix)
        else:
            size_str = _format_size(value)
            lines.append(f"{prefix}{connector}{name}  ({size_str})")


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / (1024 * 1024):.1f}MB"


def _is_important_file(f: FileInfo) -> bool:
    name = os.path.basename(f.path)

    # 文件名精确排除
    if name in EXCLUDE_NAMES:
        return False

    # 扩展名排除
    if f.extension in EXCLUDE_EXTENSIONS:
        return False

    # 非文本文件排除
    if not f.is_text:
        return False

    # 空文件排除
    if f.size == 0:
        return False

    # 文件名模式排除（测试文件、构建文件等）
    if any(pat.match(name) for pat in EXCLUDE_PATTERNS):
        return False

    # 路径中的目录段排除（如 src/test/ 下的文件）
    parts = Path(f.path).parts
    if any(p in EXCLUDE_PATH_SEGMENTS for p in parts):
        return False

    return True


if __name__ == "__main__":
    ctx = PipelineContext(
        project_path=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        project_name="CodeDeepResearch",
    )
    scan_project(ctx)
    print(f"Total files: {len(ctx.all_files)}")
    print(f"Filtered files: {len(ctx.filtered_files)}")
    print()
    print(ctx.tree_text)
    print()
    print("Filtered files:")
    for f in ctx.filtered_files:
        print(f"  {f.path} ({f.size}B)")
