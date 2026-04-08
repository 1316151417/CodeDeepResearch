# 功能性改动报告（从 main 合并到 feat-dashboard）

## 分支信息
- **当前分支**: `main`
- **源分支**: `feat-dashboard`
- **合并背景**: feat-dashboard 分支监控设计问题多，不继续迭代，仅提取功能性改动合并回 main

---

## 严重 Bug 修复

### `tool/fs_tool.py` 使用 ContextVar 追踪项目根目录，但 ContextVar 无法跨线程传播

**问题根因**（main 分支原有 Bug）:

`researcher.py` 在主线程调用 `set_project_root(ctx.project_path)`，然后将 `_research_single_module` 提交到 `ThreadPoolExecutor` 执行。由于 Python `ContextVar` 不支持跨线程传播，**worker 线程中 `get_project_root()` 返回空字符串**，导致文件工具在错误目录（运行命令的当前目录）而非目标项目目录中搜索文件。

```
main branch 原执行流程:
1. set_project_root("/path/to/target")  ← 主线程，设置了 ContextVar
2. ThreadPoolExecutor.submit(_research_single_module, ...)  ← 新线程
3. _research_single_module 内 get_project_root() → ""  ← ContextVar 未传播！
4. read_file("src/main.py") → 尝试读取 CWD/src/main.py  ← 错误！
```

**修复方式**: 将 `set_project_root(ctx.project_path)` 移至 `_research_single_module` 内部，在每个 worker 线程启动时立即调用。

---

## 统计概览

| 类别 | 文件数 | 改动行数 |
|------|--------|----------|
| 监控相关（排除） | ~15 | ~2500 |
| **功能性改动** | **2** | **~15** |

---

## 排除项（监控相关，不合并）

```
monitor/                          # 整个目录（dashboard、event_bus、events等）
.code_deep_research/runs/         # 测试运行输出
settings.json (prompts部分)        # prompt模板配置
uv.lock / pyproject.toml (依赖)   # 锁文件/新增依赖
pipeline/types.py (run_id/server_url)  # 纯监控支持字段
pipeline/__init__.py (run_id生成)  # 纯监控追踪用
agent/react_agent.py (event_handler) # 监控事件回调
settings.py (get_server_url)       # 配置读取
pipeline/scanner.py                # 仅增加监控事件发布
pipeline/decomposer.py             # 仅增加监控事件发布
pipeline/llm_filter.py             # 仅增加监控事件发布
pipeline/scorer.py                 # 仅增加监控事件发布
pipeline/aggregator.py             # 仅增加监控事件发布
```

---

## 合并回 main 的功能性改动

### 1. `pipeline/researcher.py` — Bug 修复：线程内正确设置项目根目录

**文件**: `pipeline/researcher.py`

| | 旧（main） | 新（来自 feat-dashboard） |
|---|---|---|
| `set_project_root` 位置 | 主线程 `research_modules()` 内 | **每个 worker 线程内** `_research_single_module()` |
| 并行 worker 数 | 硬编码 `4` | 可配置 `max_parallel_workers`（默认8） |

**关键修复代码**:
```python
# main - 在主线程设置，worker线程收不到
def research_modules(ctx: PipelineContext, report_dir: str) -> None:
    set_project_root(ctx.project_path)  # ← 只在主线程生效
    with ThreadPoolExecutor(max_workers=min(total, 4)) as executor:
        futures = {executor.submit(_research_single_module, ...): module for module in ...}

# feat-dashboard → main - 在每个worker线程内设置
def _research_single_module(ctx: PipelineContext, module: Module, tools: list, ...) -> None:
    set_project_root(ctx.project_path)  # ← 每个线程独立设置（修复Bug！）
    ...
```

**意义**: **严重 Bug 修复**。并行研究模式下，工具会在正确的项目目录中搜索文件，而非运行命令的当前目录。

---

### 2. `pipeline/researcher.py` — 并行 worker 数量可配置

**文件**: `pipeline/researcher.py:721-723`

```python
# 旧（main - 硬编码4并发）
with ThreadPoolExecutor(max_workers=min(total, 4)) as executor:

# 新（feat-dashboard → main - 从settings读取max_parallel_workers，默认8）
max_workers = settings.get("max_parallel_workers", 8)
with ThreadPoolExecutor(max_workers=min(total, max_workers)) as executor:
```

**意义**: 允许通过 `settings.json` 配置并行研究模块数，不再硬编码。

---

## 汇总

| # | 文件 | 改动类型 | 严重程度 | 说明 |
|---|------|----------|----------|------|
| 1 | `pipeline/researcher.py` | **Bug 修复** | **严重** | ContextVar 跨线程失效，导致并行模式下文件工具读错目录 |
| 2 | `pipeline/researcher.py` | 性能配置 | 低 | 并行 worker 数硬编码4 → 可配置 |

---

*报告生成时间: 2026-04-08*
