"""Pipeline 共用工具函数."""
import re
import unicodedata

from base.types import EventType
from pipeline.types import Topic


def collect_report(events) -> str:
    """从 ReAct agent 事件流中提取最终报告内容。"""
    contents = [e.content for e in events if e.type == EventType.STEP_END and e.content]
    return contents[-1] if contents else "（未能生成报告）"


def extract_json(text: str) -> str:
    """从 LLM 响应中提取 JSON（可能被 markdown 代码块包裹）。"""
    text = text.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start != end:
            inner = text[start:end]
            first_newline = inner.find("\n")
            if first_newline != -1:
                inner = inner[first_newline + 1:]
            return inner.strip()
    for i, ch in enumerate(text):
        if ch in "[{":
            return text[i:]
    return text


def collect_stream_text(events) -> str:
    """从 adaptor 流式事件中收集完整文本内容。"""
    parts = [e.content for e in events if e.type == EventType.CONTENT_DELTA and e.content]
    return "".join(parts)


# ---------------------------------------------------------------------------
# TOC 解析
# ---------------------------------------------------------------------------

def parse_toc_xml(xml_text: str) -> list[Topic]:
    """解析 XML TOC 输出，提取为 Topic 列表。"""
    topics = []
    index = 0

    # 匹配 <section>...</section> 块
    section_pattern = re.compile(r'<section>\s*(.*?)\s*</section>', re.DOTALL)
    # 匹配 <group>名称<topic ...>主题</topic>...</group>
    group_pattern = re.compile(r'<group>\s*(.*?)\s*((?:<topic[^>]*>.*?</topic>\s*)+)\s*</group>', re.DOTALL)
    # 匹配独立 <topic level="...">主题名</topic>
    topic_pattern = re.compile(r'<topic\s+level="([^"]*)">\s*(.*?)\s*</topic>', re.DOTALL)

    for section_match in section_pattern.finditer(xml_text):
        section_body = section_match.group(1)
        # 提取章节名（section 标签后的第一行非标签文本）
        section_name = _extract_section_name(section_body)

        # 先处理 group 块
        group_replaced = section_body
        for group_match in group_pattern.finditer(section_body):
            group_name = group_match.group(1).strip()
            group_body = group_match.group(2)
            for topic_match in topic_pattern.finditer(group_body):
                index += 1
                topics.append(Topic(
                    name=topic_match.group(2).strip(),
                    slug=slugify(topic_match.group(2).strip(), index),
                    level=topic_match.group(1).strip(),
                    section_name=section_name,
                    group_name=group_name,
                ))
            group_replaced = group_replaced.replace(group_match.group(0), "")

        # 再处理剩余的独立 topic
        for topic_match in topic_pattern.finditer(group_replaced):
            index += 1
            topics.append(Topic(
                name=topic_match.group(2).strip(),
                slug=slugify(topic_match.group(2).strip(), index),
                level=topic_match.group(1).strip(),
                section_name=section_name,
            ))

    return topics


def _extract_section_name(body: str) -> str:
    """从 section body 中提取章节名称（第一个非标签文本行）。"""
    lines = body.strip().split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('<'):
            return stripped
    return "未命名章节"


def slugify(name: str, index: int) -> str:
    """将中英文标题转为 URL slug。格式：{index}-{slug}"""
    # 移除常见标点
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[\s_]+', '-', name)
    # 对非 ASCII 字符做简化处理
    slug_parts = []
    for ch in name:
        if ch.isascii() and (ch.isalnum() or ch == '-'):
            slug_parts.append(ch.lower())
        elif not ch.isascii():
            # 非拉丁字符用音译简化
            normalized = unicodedata.normalize('NFKD', ch)
            ascii_chars = [c for c in normalized if c.isascii() and c.isalnum()]
            if ascii_chars:
                slug_parts.extend(ascii_chars)
            # 如果没有 ascii 等价物，跳过
    slug = ''.join(slug_parts).strip('-')
    slug = re.sub(r'-+', '-', slug)  # 合并连续的 -
    return f"{index}-{slug}" if slug else str(index)


# ---------------------------------------------------------------------------
# 导航上下文
# ---------------------------------------------------------------------------

def build_toc_navigation(topics: list[Topic], current: Topic) -> str:
    """构建 step2 的导航上下文，标记 [你当前在此处]。"""
    # 按 section 分组
    sections = {}
    for t in topics:
        sections.setdefault(t.section_name, []).append(t)

    lines = []
    for sec_name, sec_topics in sections.items():
        lines.append(f"- **{sec_name}**")
        current_group = None
        for t in sec_topics:
            # 处理分组
            if t.group_name != current_group:
                current_group = t.group_name
                if current_group:
                    lines.append(f"  - *{current_group}*")

            marker = " [你当前在此处]" if t.slug == current.slug else ""
            indent = "    " if current_group else "  "
            lines.append(f"{indent}- [{t.name}]({t.slug}){marker}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 内容提取
# ---------------------------------------------------------------------------

def extract_blog_content(text: str) -> str:
    """从 LLM 输出中提取 <blog>...</blog> 内容。"""
    match = re.search(r'<blog>(.*?)</blog>', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 如果没有 blog 标签，返回原文
    return text.strip()
