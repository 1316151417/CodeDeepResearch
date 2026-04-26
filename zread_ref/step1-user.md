## 用户提示词（中文版）

你需要为这个本地仓库生成一份全面的文档目录，作为面向开发者的高质量指南。

## 操作指南
1. 使用 `get_dir_structure` 了解项目布局。对于嵌套较深的仓库，可根据需要展开目录。
2. 使用 `view_file_in_detail` 阅读关键源文件（README、入口文件、核心模块）。
3. 使用 `run_bash` 执行只读命令以获取额外信息（例如查找入口点、列出文件类型）。
4. 在每次工具调用之前，请仔细思考从上一结果中观察到了什么，以及下一步需要什么信息。

## 你的任务
当前仓库的信息如下：
<metadata>
工作目录：/Users/zhoujie/IdeaProjects/Code-Analyser
操作系统：darwin
文档语言：中文

仓库结构（顶层目录）：
.
├── .DS_Store
├── .gitignore
├── .python-version
├── .zread
│   └── wiki
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
</metadata>

**只输出文档目录，不要附带任何解释或评论。所有章节名称和主题标题均使用中文。主题总数不得超过 30 个。** 按照如下结构组织每个章节：

```
<section>
章节名称
<topic level="...">
主题标题
</topic>
<group>
分组名称
<topic level="...">
主题标题
</topic>
</group>
</section>
```