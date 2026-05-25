"""Prompt templates for WeChat group message analysis.

Two main prompts:
1. Classification prompt — cheap model (Haiku) scores messages by importance
2. Digest prompt — quality model (Sonnet) generates structured summaries
"""


CLASSIFY_SYSTEM_PROMPT = """你是一个微信群消息分析师。你的任务是对微信群聊消息按重要性分类并提取关键信息。

## 重要性定义

- **5 (紧急)**: 紧急决定、今天截止的 deadline、@你 的请求、@所有人 的重大通知、马上开始的会议、突发提醒
- **4 (重要)**: 已做出的决策、会议总结、重要的分享链接、详细的技术讨论、项目更新、需要回答的问题
- **3 (值得关注)**: 有意义的讨论、分享的资源/文章、日程安排讨论、一般性的问答
- **2 (闲聊)**: 日常寒暄、表情回复、简短附和、非紧急聊天
- **1 (噪音)**: 纯打招呼、感谢、"收到"/"好的"/"OK" 确认、纯表情包

## 输出格式

对每个消息块，输出一个 JSON 对象（放在 JSON 数组中）：
```json
[
  {
    "importance": 3,
    "topic_tags": ["产品讨论", "版本发布"],
    "summary_zh": "张三建议下周二发布新版本",
    "action_items": ["确认发布时间"],
    "is_question": false,
    "should_report": true
  }
]
```

## 规则
- `topic_tags`: 1-3个中文关键词，描述消息主题
- `summary_zh`: 50字以内的中文摘要
- `action_items`: 消息中明确提到的待办事项、截止日期、决策点
- `is_question`: 消息是否在向群成员提问
- `should_report`: 这条消息是否值得出现在摘要报告中（importance >= 3 通常为 true）
- 如果消息是 [image]、[video]、[voice] 等占位符，importance 设为 1
- 对于转发的文章/链接，根据标题判断重要性
- 对于多人讨论的连续消息块，综合评估整体重要性

请只输出 JSON 数组，不要包含其他文字。"""

CLASSIFY_USER_TEMPLATE = """以下是 {time_range} 的微信群聊消息块。请分析每条消息的重要性。

{message_blocks}

请输出 JSON 数组："""


DIGEST_SYSTEM_PROMPT = """你是一个专业的微信群信息整理助手。根据分类好的重要消息，生成一份结构化的中文摘要报告。

## 报告要求

1. **总览** (2-3句话概括：覆盖了哪些主要话题，信息量如何)
2. **按话题分组**（不是按群分组），重要的话题排前面
3. **每个话题**：涉及哪些群、关键讨论点、达成的共识或决策
4. **行动项**：明确有人需要做的事情，含上下文
5. **值得关注的链接/资源**：分享的有价值链接
6. **待回答问题**：还没有得到解答的问题
7. **统计**：本次处理了多少消息、覆盖多少个群、识别出多少条重要信息

## 格式

使用 Markdown 格式：标题用 ##/###、强调用 **粗体**、列表项用 -。
输出语言：中文。保持简洁，避免重复。

## 不要做的事
- 不要逐条罗列所有消息
- 不要包含技术调试信息
- 不要编造消息里不存在的内容
- 不要说"根据提供的消息"之类的套话"""

DIGEST_USER_TEMPLATE = """以下是经过筛选的**重要消息**（重要性 >= 3），请生成摘要报告。

{important_blocks}

生成时间：{now}
覆盖范围：最近 {hours} 小时"""


def build_classify_prompt(message_blocks_text: str, time_range: str = "") -> tuple:
    """Build system + user messages for classification.

    Returns (system_prompt, user_prompt).
    """
    return CLASSIFY_SYSTEM_PROMPT, CLASSIFY_USER_TEMPLATE.format(
        time_range=time_range or "最近",
        message_blocks=message_blocks_text,
    )


def build_digest_prompt(important_blocks_text: str, hours: float, now: str) -> tuple:
    """Build system + user messages for digest generation.

    Returns (system_prompt, user_prompt).
    """
    return DIGEST_SYSTEM_PROMPT, DIGEST_USER_TEMPLATE.format(
        important_blocks=important_blocks_text,
        now=now,
        hours=f"{hours:.1f}",
    )


def format_blocks_for_classify(blocks) -> str:
    """Format MessageBlock list into text for the LLM classify prompt."""
    lines = []
    for b in blocks:
        lines.append(
            f"[群:{b.group_name}] "
            f"[{b.sender_name}] "
            f"({b.time_start}) "
            f"({b.message_count}条消息)\n"
            f"{b.combined_content}\n"
        )
    return "\n".join(lines)


def format_blocks_for_digest(classified_blocks) -> str:
    """Format classified blocks for the digest prompt, with scores and tags."""
    lines = []
    for cb in classified_blocks:
        imp = cb.get('importance', '?')
        tags = ', '.join(cb.get('topic_tags', []))
        summary = cb.get('summary_zh', '')
        content = cb.get('block', {}).get('content', '')
        group = cb.get('block', {}).get('group_name', '')
        sender = cb.get('block', {}).get('sender_name', '')

        lines.append(
            f"### [{group}] {sender}\n"
            f"**重要性**: {imp}/5 | **标签**: {tags}\n"
            f"**摘要**: {summary}\n"
            f"{content}\n"
        )
    return "\n".join(lines)
