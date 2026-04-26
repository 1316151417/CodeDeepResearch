# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM 驱动的自动化代码深度分析引擎。输入任意代码仓库路径，输出结构化的中文项目分析报告（文档目录 + 每个主题的详细内容）。

底层使用 DeepSeek API 端点，支持 OpenAI/Anthropic 两种协议格式的流式调用 + 工具调用（ReAct 模式）。

## Commands

```bash
# 分析本地项目
uv run python main.py /path/to/project

# 指定配置文件
uv run python main.py /path/to/project --settings /path/to/settings.json

# 输出到指定文件
uv run python main.py /path/to/project -o output.md

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

### 2-Stage Pipeline

```
输入 → 章节拆分(生成TOC) → 内容生成(每个主题) → 输出
```

1. **章节拆分（generate_toc）** — ReAct agent 探索项目，生成 XML 格式的文档目录（section/group/topic 层级）
2. **内容生成（generate_content）** — 并行 ReAct agent 为每个主题生成详细文档，带导航上下文约束

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
| `provider/adaptor.py` | LLMAdaptor 统一流式接口，OpenAI/Anthropic 协议互转 |
| `provider/api/anthropic_api.py` | Anthropic 协议客户端实现 |
| `provider/api/openai_api.py` | OpenAI 协议客户端实现 |
| `agent/react_agent.py` | ReAct 循环：消费事件、执行工具、维护多轮对话 |
| `pipeline/run.py` | `run_pipeline()` 入口，2 阶段调度 |
| `pipeline/types.py` | Topic/PipelineContext 数据结构 |
| `pipeline/explorer.py` | Step 1：章节拆分，生成 XML TOC |
| `pipeline/researcher.py` | Step 2：内容生成，每个主题独立 agent |
| `pipeline/utils.py` | TOC 解析、导航上下文、报告拼接 |
| `prompt/pipeline_prompts.py` | STEP1/STEP2 提示词（照搬 zread 设计） |
| `prompt/react_prompts.py` | ReAct agent 上下文压缩提示词 |
| `tool/fs_tool.py` | 3 个工具：get_dir_structure/view_file_in_detail/run_bash |
| `log/printer.py` | 事件格式化打印，流式输出追踪 |
| `log/logger.py` | 调试日志，DEBUG=1 启用 |

### 3 个工具

1. **get_dir_structure** — 获取目录树形结构，自动过滤 .git/node_modules 等
2. **view_file_in_detail** — 查看文件内容，支持行号范围
3. **run_bash** — 执行只读 shell 命令（白名单校验 + 30s 超时）

### 关键设计

1. **TOOL_CALL 事件的 `raw` 字段**：携带 `{"id", "name", "arguments"}`，直接构建 `AssistantMessage`
2. **`@tool` 装饰器**：从函数签名/docstring 自动提取参数，生成 `Tool` 对象
3. **消息格式转换在 adaptor 层**：agent 层使用统一中间格式
4. **三级模型分层**：lite=过滤/pro=研究+生成/max=最强，平衡速度与质量
5. **上下文压缩**：`MAX_CONTEXT_CHARS=200000` 阈值，自动压缩超长对话保留关键引用
6. **导航上下文**：Step 2 每个 agent 获得完整 TOC + 当前位置标记，约束内容边界
7. **并行内容生成**：ThreadPoolExecutor 并行生成各主题文档

### Settings Configuration (`settings.json`)

三级模型独立配置，每级包含 provider/base_url/api_key/model/max_tokens：

```json
{
  "lite": { "provider": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-flash" },
  "pro":  { "provider": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-flash" },
  "max":  { "provider": "openai", "base_url": "https://api.deepseek.com", "model": "deepseek-v4-flash" },
  "max_sub_agent_steps": 30,
  "research_parallel": true,
  "research_threads": 10,
  "doc_language": "中文",
  "target_audience": "初级开发者",
  "debug": false
}
```

| 配置项 | 说明 |
|--------|------|
| `lite` | 备用（速度快） |
| `pro` | 章节拆分 + 内容生成（主要推理） |
| `max` | 备用（最强推理） |
| `max_sub_agent_steps` | 每个 agent 的最大步数 |
| `research_parallel` | 是否并行生成内容 |
| `research_threads` | 并行线程数 |
| `doc_language` | 文档语言 |
| `target_audience` | 目标受众 |

## Dependencies

Python 3.12, `anthropic>=0.89.0`, `openai>=2.30.0`。包管理用 `uv`.
