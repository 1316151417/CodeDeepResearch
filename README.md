# CodeDeepResearch

LLM 驱动的自动化代码深度分析引擎。输入任意代码仓库路径，输出结构化的中文项目分析报告（架构总览、模块详解、跨模块洞察、总结建议）。

## 核心能力

- **全自动化分析**：无需人工干预，输入仓库路径即可获得完整分析报告
- **智能文件筛选**：硬编码 + LLM 两层过滤，去除测试/文档/配置等无分析价值文件
- **并行模块研究**：对 top N 重要模块并行深度研究，充分利用 token 并发
- **生成-评估迭代**：子模块报告和最终报告均经过生成-评估-改进循环，确保质量
- **三级模型分层**：lite/pro/max 三档模型按场景分配，平衡速度与质量
- **流式事件架构**：完整的事件日志可追踪 agent 思维过程
- **流式超时保护**：所有 LLM 调用均有超时保护，防止无限卡死

## 架构

```
输入: /path/to/project
  │
  ▼
阶段 1: 扫描项目 ── 遍历文件，收集大小/扩展名/路径
  │         排除 node_modules/.git/test/docs 等目录
  │
  ▼
阶段 2: LLM 智能过滤 ── 基于项目类型判断文件重要性
  │         排除 README/配置文件/自动生成代码
  │
  ▼
阶段 3: 模块拆分 ── 按目录结构 + import 关系划分模块
  │
  ▼
阶段 4: 模块打分排序 ── 核心度/依赖度/入口/领域独特性评分
  │         取 top N 进入深度研究
  │
  ▼
阶段 5: 子模块深度研究 ── 并行 ReAct agent × N 模块
  │         每模块: 生成 → 评估 → (不通过则重试) → 最终生成
  │
  ▼
阶段 6: 最终报告汇总 ── ReAct agent 整合所有模块报告
  │         生成 → 评估 → (不通过则重试) → 最终生成
  │
  ▼
输出: report/{项目名}/{时间戳}/
  ├── 模块分析报告-{模块1}.md
  ├── 模块分析报告-{模块2}.md
  └── 最终报告-{项目名}.md
```

## 快速开始

### 安装依赖

```bash
uv sync
```

### 配置

编辑 `settings.json`：

```json
{
  "provider": "anthropic",
  "lite_model": "deepseek-chat",
  "pro_model": "deepseek-reasoner",
  "max_model": "deepseek-reasoner",
  "max_tokens": 16384,
  "max_sub_agent_steps": 30
}
```

| 配置项 | 说明 |
|--------|------|
| `provider` | `anthropic` 或 `openai`（均走 DeepSeek API 端点） |
| `lite_model` | 分类/过滤/打分用（速度快） |
| `pro_model` | 子模块深度分析 + 评估用（推理能力强） |
| `max_model` | 最终汇总用（最强推理） |
| `max_sub_agent_steps` | 每个 agent 的最大步数 |

### 运行

```bash
# 分析本地项目
uv run python main.py /path/to/project

# 指定配置文件
uv run python main.py /path/to/project --settings /path/to/settings.json

# 输出到指定文件
uv run python main.py /path/to/project -o output.md
```

### 环境变量

```bash
export DEEPSEEK_API_KEY="your-api-key"
```

## 核心模块

### 事件流

所有交互通过统一的 `Event` 抽象，流式顺序：

```
MESSAGE_START → THINKING_START → THINKING_DELTA* → THINKING_END
              → CONTENT_START  → CONTENT_DELTA*  → CONTENT_END
              → TOOL_CALL*
              → MESSAGE_END

ReAct agent 额外事件：
STEP_START/STEP_END（每轮迭代）
TOOL_CALL_SUCCESS/TOOL_CALL_FAILED（工具执行结果）
```

### 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| 基础类型 | `base/types.py` | `EventType`、`Event`、`Message` 体系、`@tool` 装饰器 |
| LLM 适配器 | `provider/adaptor.py` | 统一流式接口，OpenAI/Anthropic 协议转换 |
| ReAct Agent | `agent/react_agent.py` | 工具执行、多轮对话维护、流式事件转发 |
| 项目扫描 | `pipeline/scanner.py` | 硬编码过滤（目录/扩展名/文件名模式） |
| LLM 过滤 | `pipeline/llm_filter.py` | 基于项目类型的 LLM 智能过滤 |
| 模块拆分 | `pipeline/decomposer.py` | 按目录结构 + import 关系划分模块 |
| 模块打分 | `pipeline/scorer.py` | 核心度/依赖度/入口/领域独特性评分 |
| 深度研究 | `pipeline/researcher.py` | 并行 ReAct agent 子模块研究 + 评估迭代 |
| 最终汇总 | `pipeline/aggregator.py` | ReAct agent 整合 + 评估迭代生成最终报告 |

### 关键设计

1. **`@tool` 装饰器**：从函数签名和 docstring 自动提取参数类型、描述，生成 `Tool` 对象
2. **TOOL_CALL 事件的 `raw` 字段**：携带 `{"id", "name", "arguments"}`，直接构建 `AssistantMessage`
3. **消息格式转换在 adaptor 层**：agent 层使用统一中间格式，adaptor 负责转换
4. **三级模型分层**：lite=过滤/pro=研究/max=汇总，平衡速度与质量
5. **tool_use 文本过滤**：`STEP_END` 过滤 LLM 误输出的 `tool_use(...)` 文本
6. **流式超时保护**：daemon thread + Queue + 120s per step + 60s LLM call + 600s future.result()

## 提示词体系

| 提示词 | 用途 | 关键设计 |
|--------|------|---------|
| `FILE_FILTER_SYSTEM` | LLM 文件过滤 | 排除/保留规则详细列举，JSON 数组输出 |
| `DECOMPOSER_SYSTEM` | 模块拆分 | 目录结构 + import 关系分析，3-10 个模块输出 |
| `SCORER_SYSTEM` | 模块打分 | 5 维度评分（核心度/依赖度/入口/领域/复杂度） |
| `SUB_AGENT_SYSTEM` | 子模块深度分析 | 并发调用指令 + 批量读取/grep + 报告模板 |
| `EVAL_AGENT_SYSTEM` | 子模块评估 | Veto 检查 + 4 维度评分，suggestions 具体可操作 |
| `AGGREGATOR_SYSTEM` | 最终报告汇总 | 并发调用指令 + 单 Pass 生成 |
| `AGGREGATOR_EVAL_SYSTEM` | 最终报告评估 | 完整性/深度/洞察力/实用性 Veto 检查 |
| `COMPRESS_SYSTEM` | 上下文压缩 | 多轮对话摘要，保留关键引用 |

## 输出示例

```
============================================================
阶段 1/6: 扫描项目 [my-project]
============================================================
  扫描到 1247 个文件
  基础过滤后剩余 312 个文件

============================================================
阶段 2/6: LLM 智能过滤
============================================================
  LLM 评估后保留 89 个重要文件

============================================================
阶段 3/6: 模块拆分
============================================================
  识别到 7 个模块:
    - core-agent: ReAct 智能体循环引擎 (4 个文件)
    - llm-provider: LLM API 多协议适配层 (3 个文件)
    ...

============================================================
阶段 4/6: 模块重要性打分
============================================================
  模块评分（从高到低）:
    - core-agent: 95分 ★
    - llm-provider: 82分 ★
    - workflow-orchestration: 78分 ★
  选择前 3 个模块进行深度研究

============================================================
阶段 5/6: 子模块深度研究
============================================================
  并行研究 3 个模块（最多 1 轮评估）
  ✓ [core-agent] 完成 (4521 字符)
  ✓ [llm-provider] 完成 (3892 字符)
  ✓ [workflow-orchestration] 完成 (4103 字符)

============================================================
阶段 6/6: 汇总最终报告
============================================================
  汇总 agent 第 1/1 轮：研究阶段...
  汇总 agent 评估通过 (分数: 85)
  分析完成！共生成 3 份模块报告 + 1 份最终报告
  报告目录: report/my-project/202604062320
```

## 依赖

- Python 3.12+
- `anthropic>=0.89.0`
- `openai>=2.30.0`
- `uv`（包管理）

## 目录结构

```
CodeDeepResearch/
├── main.py                  # CLI 入口
├── settings.json            # 运行时配置
├── settings.py              # 配置加载器
├── base/
│   └── types.py            # 核心类型定义
├── provider/
│   ├── adaptor.py          # LLM 统一适配器
│   ├── anthropic/deepseek_api.py   # Anthropic 协议实现
│   └── openai/deepseek_api.py     # OpenAI 协议实现
├── agent/
│   └── react_agent.py       # ReAct agent 实现
├── pipeline/
│   ├── __init__.py         # run_pipeline() 入口
│   ├── types.py            # PipelineContext/Module
│   ├── scanner.py          # 项目扫描
│   ├── llm_filter.py       # LLM 智能过滤
│   ├── decomposer.py       # 模块拆分
│   ├── scorer.py           # 模块打分
│   ├── researcher.py        # 子模块深度研究
│   └── aggregator.py       # 最终报告汇总
├── prompt/
│   └── pipeline_prompts.py  # 所有提示词定义
├── tool/
│   └── fs_tool.py          # 文件系统工具（read_file/list_dir/grep）
├── log/
│   ├── logger.py           # 调试日志
│   └── printer.py          # 事件格式化打印
└── report/                 # 分析报告输出目录
```
