"""
ReAct Agent - implements the Observe -> Think -> Act loop with streaming events.
"""
import json

from dataclasses import dataclass, field

from log.logger import logger
from provider.adaptor import LLMAdaptor
from base.types import Event, EventType, ToolMessage, AssistantMessage, normalize_messages

from langfuse import observe

MAX_STEP_CNT = 30
MAX_CONTEXT_CHARS = 200_000
COMPRESS_KEEP_RECENT = 6


# --- Context compression ---

def compress_if_needed(adaptor, messages) -> list:
    """检查上下文长度，超阈值则压缩旧消息。"""
    messages = normalize_messages(messages)
    total_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    if total_chars <= MAX_CONTEXT_CHARS:
        return messages

    print(f"\n  [上下文压缩] {total_chars} 字符超过阈值 {MAX_CONTEXT_CHARS}，开始压缩...")

    system_msgs = [m for m in messages if m.get("role") == "system"]
    other_msgs = [m for m in messages if m.get("role") != "system"]

    if len(other_msgs) <= COMPRESS_KEEP_RECENT:
        return messages

    to_compress = other_msgs[:-COMPRESS_KEEP_RECENT]
    to_keep = other_msgs[-COMPRESS_KEEP_RECENT:]

    # 跳过 to_keep 开头的孤立 tool 消息（对应的 tool_use 已在压缩部分）
    while to_keep and to_keep[0].get("role") == "tool":
        to_keep.pop(0)
    summary = _summarize_messages(adaptor, to_compress)

    compressed = list(system_msgs)
    if summary:
        compressed.append({"role": "user", "content": f"[以下是之前对话的摘要]\n{summary}"})
        compressed.append({"role": "assistant", "content": "好的，我已了解之前的分析内容，继续进行。"})
    compressed.extend(to_keep)

    new_chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in compressed)
    print(f"  [上下文压缩] 完成：{total_chars} → {new_chars} 字符")
    return compressed


def _summarize_messages(adaptor, messages: list) -> str:
    from prompt.langfuse_prompt import get_compiled_messages
    conversation_text = _format_messages_for_summary(messages)
    if not conversation_text.strip():
        return ""

    try:
        compiled = get_compiled_messages("compress", conversation=conversation_text[:30000])
        return adaptor.call(compiled)
    except Exception as e:
        print(f"  [上下文压缩] 压缩失败: {e}")
        return ""


def _format_messages_for_summary(messages: list) -> str:
    lines = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")

        if role == "assistant":
            lines.append(_format_assistant_for_summary(content))
        elif role == "user":
            lines.append(_format_user_for_summary(content))
        elif role == "tool":
            result = m.get("tool_result") or m.get("tool_error") or ""
            lines.append(f"[工具结果({m.get('tool_name', '?')})]: {str(result)[:500]}")
    return "\n".join(lines)


def _format_assistant_for_summary(content) -> str:
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(f"[助手]: {block['text'][:500]}")
                elif block.get("type") == "tool_use":
                    parts.append(f"[助手调用工具]: {block.get('name', '?')}({json.dumps(block.get('input', {}), ensure_ascii=False)[:200]})")
        return "\n".join(parts) if parts else ""
    elif content:
        return f"[助手]: {str(content)[:500]}"
    return ""


def _format_user_for_summary(content) -> str:
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                parts.append(f"[工具结果]: {str(block.get('content', ''))[:500]}")
        return "\n".join(parts) if parts else ""
    elif content:
        return f"[用户]: {str(content)[:500]}"
    return ""


# --- Step accumulator ---

@dataclass
class _Step:
    """Accumulates streaming events within a single ReAct step."""
    content: str = ""
    thinking: str = ""
    tool_calls: list = field(default_factory=list)
    tool_results: dict = field(default_factory=dict)

    def process(self, event: Event) -> None:
        if event.type == EventType.THINKING_DELTA:
            self.thinking += event.content or ""
        elif event.type == EventType.CONTENT_DELTA:
            self.content += event.content or ""
        elif event.type == EventType.TOOL_CALL:
            self.tool_calls.append(event.raw)

    def build_messages(self) -> list:
        """Build AssistantMessage + ToolMessages for appending to conversation."""
        msgs = [AssistantMessage(
            content=self.content,
            tool_calls=self.tool_calls,
            thinking=self.thinking,
        )]
        for tc in self.tool_calls:
            tr = self.tool_results[tc["id"]]
            msgs.append(ToolMessage(
                tool_id=tc["id"],
                tool_name=tc["name"],
                tool_result=tr["result"],
                tool_error=tr["error"],
            ))
        return msgs


def _parse_arguments(arguments_str: str) -> dict:
    """Parse tool call arguments JSON."""
    if not arguments_str:
        return {}
    try:
        return json.loads(arguments_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in tool arguments: {arguments_str[:100]}... ({e})")


@observe(name="react_agent_stream")
def stream(messages, tools, config: dict, max_steps=MAX_STEP_CNT):
    """ReAct stream generator: yields events for each step."""
    adaptor = LLMAdaptor(config)
    tool_map = {t.name: t for t in tools}

    for step in range(1, max_steps + 1):
        compressed = compress_if_needed(adaptor, messages)
        if compressed is not messages:
            messages.clear()
            messages.extend(compressed)

        yield Event(type=EventType.STEP_START, step=step)
        step_state = _Step()

        for event in adaptor.stream(messages, tools):
            yield event
            step_state.process(event)

            if event.type == EventType.TOOL_CALL:
                tool = tool_map.get(event.tool_name)
                if tool is None:
                    raise RuntimeError(f"Tool '{event.tool_name}' not found")

                logger.debug(f"[ReAct] 调用工具: {event.tool_name}({(event.tool_arguments or '')[:80]}...)")
                try:
                    result = tool(**_parse_arguments(event.tool_arguments))
                    error = None
                    logger.debug(f"[ReAct] 工具结果: {str(result)[:100]}...")
                except Exception as e:
                    result = None
                    error = str(e)
                    logger.debug(f"[ReAct] 工具执行失败 {tool.name}: {e}")

                step_state.tool_results[event.tool_id] = {"result": result, "error": error}
                yield Event(
                    type=EventType.TOOL_CALL_SUCCESS if not error else EventType.TOOL_CALL_FAILED,
                    tool_id=event.tool_id,
                    tool_name=event.tool_name,
                    tool_arguments=event.tool_arguments,
                    tool_result=result,
                    tool_error=error,
                )

        yield Event(type=EventType.STEP_END, content=step_state.content, step=step)

        if not step_state.tool_calls:
            break

        messages.extend(step_state.build_messages())
