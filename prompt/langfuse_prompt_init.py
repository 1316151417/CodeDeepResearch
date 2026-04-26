"""将提示词同步到 Langfuse Prompt Management."""
import re
import dotenv
dotenv.load_dotenv()

from langfuse import get_client
from prompt.pipeline_prompts import (
    STEP1_SYSTEM, STEP1_USER,
    STEP2_SYSTEM, STEP2_USER,
)
from prompt.react_prompts import COMPRESS_SYSTEM, COMPRESS_USER


def _to_langfuse_vars(text: str) -> str:
    """将 Python format {var} 转为 Langfuse 模板变量 {{var}}。"""
    return re.sub(r'(?<!\{)\{(\w+)\}(?!\})', r'{{\1}}', text)


langfuse = get_client()

# 每个 pipeline 阶段的 system + user 配对为 chat prompt
chat_prompts = [
    ("step1", STEP1_SYSTEM, STEP1_USER),
    ("step2", STEP2_SYSTEM, STEP2_USER),
    ("compress", COMPRESS_SYSTEM, COMPRESS_USER),
]

for name, system, user in chat_prompts:
    try:
        langfuse.create_prompt(
            name=name,
            type="chat",
            prompt=[
                {"role": "system", "content": _to_langfuse_vars(system)},
                {"role": "user", "content": _to_langfuse_vars(user)},
            ],
            labels=["production"],
        )
        print(f"  ✓ {name}")
    except Exception as e:
        print(f"  ✗ {name}: {e}")

print("\n同步完成")
