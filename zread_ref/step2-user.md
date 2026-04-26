## 当前任务
**工作目录**：/Users/zhoujie/IdeaProjects/Code-Analyser  
**操作系统**：darwin  
**当前页面**：文档《项目概述》  
**目标受众**：初级开发者  
**文档语言**：中文

## 环境信息
仓库结构（前两级目录）：
```
.
├── .DS_Store
├── .gitignore
├── .python-version
├── .zread
│   └── wiki
│       └── drafts
├── README.md
├── __init__.py
├── final_report.md
├── langgraph_app.py
├── main.py
├── pyproject.toml
├── requirements.txt
├── run_cli.py
├── src
│   ├── config
│   │   └── settings.py
│   ├── github_repo_parser.py
│   ├── llm
│   │   └── llm_config.py
│   ├── nodes
│   │   ├── analyze_repo_node.py
│   │   ├── fetch_and_parse_node.py
│   │   ├── fetch_repo_metadata_node.py
│   │   ├── global_context_node.py
│   │   ├── query_analyser_node.py
│   │   └── summarize_repo_node.py
│   ├── tools
│   │   ├── parse_json_yaml.py
│   │   ├── parse_markdown.py
│   │   ├── parse_notebook.py
│   │   └── parse_python.py
│   └── utils
│       ├── fetch_blob.py
│       ├── flatten_tree.py
│       └── summarize_state.py
├── state_schema.py
└── uv.lock
```

## 导航上下文
**完整目录及你的当前位置**：
```
- **快速入门**
  - [项目概述](1-xiang-mu-gai-shu) [你当前在此处]
  - [快速启动指南](2-kuai-su-qi-dong-zhi-nan)
  - [环境配置与安装](3-huan-jing-pei-zhi-yu-an-zhuang)
  - [命令行使用方式](4-ming-ling-xing-shi-yong-fang-shi)
- **核心概念**
  - [系统架构总览](5-xi-tong-jia-gou-zong-lan)
  - [状态管理机制](6-zhuang-tai-guan-li-ji-zhi)
  - *意图识别模块*
    - [意图检测原理](7-yi-tu-jian-ce-yuan-li)
    - [关键词与目标提取](8-guan-jian-ci-yu-mu-biao-ti-qu)
- **深度解析**
  - [索引工作流详解](9-suo-yin-gong-zuo-liu-xiang-jie)
  - [问答工作流详解](10-wen-da-gong-zuo-liu-xiang-jie)
  - [文件选择策略](11-wen-jian-xuan-ze-ce-lue)
  - [增量解析机制](12-zeng-liang-jie-xi-ji-zhi)
  - *节点实现*
    - [元数据获取节点](13-yuan-shu-ju-huo-qu-jie-dian)
    - [全局上下文节点](14-quan-ju-shang-xia-wen-jie-dian)
    - [仓库分析节点](15-cang-ku-fen-xi-jie-dian)
    - [文件获取与解析节点](16-wen-jian-huo-qu-yu-jie-xi-jie-dian)
    - [总结生成节点](17-zong-jie-sheng-cheng-jie-dian)
- **工具与解析器**
  - [解析器注册机制](18-jie-xi-qi-zhu-ce-ji-zhi)
  - [Python文件解析器](19-pythonwen-jian-jie-xi-qi)
  - [Markdown文件解析器](20-markdownwen-jian-jie-xi-qi)
  - [JSON/YAML解析器](21-json-yamljie-xi-qi)
  - [Jupyter Notebook解析器](22-jupyter-notebookjie-xi-qi)
  - [文件内容获取工具](23-wen-jian-nei-rong-huo-qu-gong-ju)
- **配置与扩展**
  - [LLM配置管理](24-llmpei-zhi-guan-li)
  - [系统参数配置](25-xi-tong-can-shu-pei-zhi)
  - [扩展新解析器](26-kuo-zhan-xin-jie-xi-qi)

```
**内容边界约束**：
- 仅围绕《项目概述》撰写内容——避免写入属于其他目录页面的内容
- 明确标有 `[你当前在此处]` 的页面即为你当前所处位置
- 在建议后续阅读步骤时，请使用精确的目录链接引用其他页面

## 文档类型要求
**全局要求**：
- 每个段落末尾均需标注本地文件引用，格式为：`Sources: [文件名](相对/路径#L<起始行>-L<结束行>)`
- 所有撰写内容均使用中文

**适用于概述/入门文档**：
- 根据目录结构，使用精确的目录链接（如 `[页面名称](page_slug)`）给出合理的阅读进阶建议
- 使用 Mermaid 图表创建架构概览图
- 使用表格进行功能对比、配置选项说明或 API 摘要总结
- 添加可视化的项目结构表示

**适用于操作指南/教程文档**：
- 包含分步操作的 Mermaid 流程图
- 使用表格解释参数含义、提供故障排除指南
- 添加修改前后的代码对比表格

**适用于解释性文档**：
- 使用 Mermaid 创建概念关系图
- 使用表格进行模式对比、优劣势分析
- 包含类/模块交互图

## 输出格式
**重要提示**：请将最终的完整文档内容包裹在 `<blog></blog>` 标签内，示例如下：

```
<blog>
# 项目概述
此处简述当前页面的目的与范围。
## 章节名称
内容仅聚焦于《项目概述》相关部分
Sources: [文件名](相对/路径#L123-L456)
## 下一章节名称
内容仅聚焦于《项目概述》相关部分
Sources: [文件名](相对/路径#L789)
...
</blog>
```

## 立即执行
请从形成架构假设开始。通过使用可用工具进行有针对性的代码审查来验证假设。交付包含可视化元素和精确本地文件引用的《项目概述》文档。请记住将最终输出包裹在 `<blog></blog>` 标签内。