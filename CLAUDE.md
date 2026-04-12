# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM 驱动的自动化代码深度分析引擎。输入任意代码仓库路径，输出结构化的中文项目分析报告（架构总览、模块详解、跨模块洞察、总结建议）。

底层使用 DeepSeek API 端点，支持 OpenAI/Anthropic 两种协议格式的流式调用 + 工具调用（ReAct 模式）。

## Commands

```bash
# 分析本地项目
uv run python main.py /path/to/project

# 指定配置文件
uv run python main.py /path/to/project --settings /path/to/settings.json

# 运行测试
python test/llm_test.py

# 使用 uv 管理依赖（项目用 uv，不用 pip）
uv sync
uv add <package>
```

## Environment Variables

```bash
export DEEPSEEK_API_KEY="your-api-key"
export DEBUG=1  # 启用调试日志输出
```

## Architecture

### 6-Stage Pipeline

```
输入 → 扫描项目 → LLM过滤 → 模块拆分 → 模块打分 → 深度研究 → 汇总报告 → 输出
```

1. **scanner** — 遍历文件，收集大小/扩展名/路径，硬编码过滤 node_modules/.git/test/docs
2. **llm_filter** — 基于项目类型判断文件重要性，LLM 智能过滤
3. **decomposer** — 按目录结构 + import 关系划分模块
4. **scorer** — 核心度/依赖度/入口/领域独特性评分，取 top N
5. **researcher** — 并行 ReAct agent 深度研究，每模块生成→评估→重试→最终
6. **aggregator** — ReAct agent 整合所有模块报告，生成→评估→重试→最终

### 事件流（核心数据流）

所有交互通过 `Event` 统一抽象，流式顺序：

```
MESSAGE_START → THINKING_START → THINKING_DELTA* → THINKING_END
              → CONTENT_START  → CONTENT_DELTA*  → CONTENT_END
              → TOOL_CALL*
              → MESSAGE_END

ReAct agent 额外事件：
STEP_START/STEP_END（每轮迭代）
TOOL_CALL_SUCCESS/TOOL_CALL_FAILED（工具执行结果）
```

### 关键模块

| 文件 | 职责 |
|------|------|
| `base/types.py` | 核心类型：EventType/Event/Tool/Message 体系/@tool 装饰器 |
| `provider/llm.py` | 共享 LLM 工具：`call_llm`、`extract_json`、`call_llm_sync` |
| `provider/adaptor.py` | 统一流式接口，OpenAI/Anthropic 协议互转 |
| `provider/deepseek_base.py` | DeepSeek API 客户端实现，两种协议的 call/call_stream |
| `agent/react_agent.py` | ReAct 循环：消费事件、执行工具、维护多轮对话 |
| `pipeline/__init__.py` | `run_pipeline()` 入口，6 阶段调度 |
| `tool/fs_tool.py` | 文件系统工具：read_file/list_directory/glob_pattern/grep_content（线程安全） |

### 关键设计

1. **TOOL_CALL 事件的 `raw` 字段**：携带 `{"id", "name", "arguments"}`，直接构建 `AssistantMessage`
2. **`@tool` 装饰器**：从函数签名/docstring 自动提取参数，生成 `Tool` 对象
3. **消息格式转换在 adaptor 层**：agent 层使用统一中间格式
4. **三级模型分层**：lite=过滤/pro=研究/max=汇总，平衡速度与质量
5. **tool_use 文本过滤**：`STEP_END` 过滤 LLM 误输出的 `tool_use(...)` 文本
6. **流式超时保护**：daemon thread + Queue + 120s per step + 60s LLM call

### Settings Configuration (`settings.json`)

| 配置项 | 说明 |
|--------|------|
| `provider` | `anthropic` 或 `openai`（均走 DeepSeek API 端点） |
| `lite_model` | 分类/过滤/打分用（速度快） |
| `pro_model` | 子模块深度分析 + 评估用（推理能力强） |
| `max_model` | 最终汇总用（最强推理） |
| `max_sub_agent_steps` | 每个 agent 的最大步数 |

## Dependencies

Python 3.12, `anthropic>=0.89.0`, `openai>=2.30.0`。包管理用 `uv`.
