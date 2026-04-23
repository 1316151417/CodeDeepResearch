"""Langfuse prompt management - fetch and compile prompts."""
import dotenv
dotenv.load_dotenv()

from langfuse import get_client, observe

_client = get_client()

@observe(as_type="generation")
def get_compiled_messages(name: str, **variables) -> list[dict]:
    """从 Langfuse 获取 chat prompt 并编译模板变量。

    Args:
        name: Langfuse 中的 prompt 名称（如 "file-filter"）
        **variables: 模板变量（如 project_name="xxx", files_json="..."）

    Returns:
        编译后的消息列表，如 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    prompt = _client.get_prompt(name, type="chat")
    return prompt.compile(**variables)
