"""Pre-LLM filtering pipeline for WeChat messages.

Takes raw Message objects from DBService, filters out noise, aggregates
consecutive messages from the same sender into MessageBlocks.
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from models import Message, MSG_TYPE_TEXT, MSG_TYPE_SHARE, MSG_TYPE_SYSTEM


@dataclass
class MessageBlock:
    """A coherent unit of messages from the same sender in the same group."""
    group_id: str
    group_name: str
    sender_id: str
    sender_name: str
    messages: List[Message] = field(default_factory=list)
    is_self: bool = False
    time_start: str = ""
    time_end: str = ""

    @property
    def combined_content(self) -> str:
        return "\n".join(m.content for m in self.messages if m.content)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def seq(self) -> int:
        return self.messages[-1].seq if self.messages else 0


class MessageFilter:
    """Filter and aggregate WeChat messages before LLM processing."""

    def __init__(self, config):
        self.min_text_length = config.min_text_length
        self.skip_types = set(config.skip_types)
        self.skip_sub_types = set(config.skip_sub_types)
        self.skip_patterns = [re.compile(p) for p in config.skip_patterns]
        self.aggregation_window = config.aggregation_window_seconds

    def pipeline(self, messages: List[Message]) -> List[MessageBlock]:
        """Run all filter stages, return clean message blocks."""
        msgs = self._filter_type(messages)
        msgs = self._filter_content(msgs)
        blocks = self._aggregate(msgs)
        return blocks

    def _filter_type(self, messages: List[Message]) -> List[Message]:
        """Stage 1: Remove non-text and system messages."""
        result = []
        for m in messages:
            if m.type in self.skip_types:
                continue
            if m.type == MSG_TYPE_SHARE and m.sub_type in self.skip_sub_types:
                continue
            result.append(m)
        return result

    def _filter_content(self, messages: List[Message]) -> List[Message]:
        """Stage 2: Remove noise by content patterns and length."""
        result = []
        for m in messages:
            text = self._meaningful_text(m.content)
            if len(text) < self.min_text_length:
                continue
            if self._matches_noise_pattern(text):
                continue
            result.append(m)
        return result

    def _meaningful_text(self, content: str) -> str:
        """Strip emoji, whitespace, punctuation to get meaningful text."""
        if not content:
            return ""
        # Remove common emoji and symbols (Unicode ranges)
        cleaned = re.sub(
            r'[\U0001F300-\U0001F9FF'            # emoji
            r'☀-➿'                       # misc symbols
            r'︀-﻿'                       # variation selectors
            r'‍‌'                         # ZWJ/ZWNJ
            r']+', '', content)
        # Remove whitespace
        cleaned = re.sub(r'\s+', '', cleaned)
        # Remove common Chinese and English punctuation marks
        punct_chars = (
            ',，。！？、；：“”‘’'
            '「」《》（）()[]{}'
            '…—–.!?-'
        )
        cleaned = cleaned.translate(str.maketrans('', '', punct_chars))
        return cleaned.strip()

    def _matches_noise_pattern(self, text: str) -> bool:
        """Check if text matches any noise pattern."""
        for pattern in self.skip_patterns:
            if pattern.match(text.strip()):
                return True
        return False

    def _aggregate(self, messages: List[Message]) -> List[MessageBlock]:
        """Stage 3: Group consecutive same-sender messages into blocks.

        Messages from the same sender in the same group, within the
        aggregation window, are merged into a single MessageBlock.
        """
        if not messages:
            return []

        # Group by (group_id, sender_id)
        groups: Dict[str, List[Message]] = {}
        for m in messages:
            key = f"{m.talker}|{m.sender}"
            if key not in groups:
                groups[key] = []
            groups[key].append(m)

        blocks = []
        for key, msgs in groups.items():
            # Sort by seq/time
            msgs.sort(key=lambda m: (m.seq, m.time))

            # Split into sub-blocks by time window
            current_block = [msgs[0]]
            for i in range(1, len(msgs)):
                gap = self._time_diff_seconds(current_block[-1].time, msgs[i].time)
                if gap <= self.aggregation_window:
                    current_block.append(msgs[i])
                else:
                    blocks.append(self._make_block(current_block))
                    current_block = [msgs[i]]
            if current_block:
                blocks.append(self._make_block(current_block))

        # Also deduplicate cross-group
        blocks = self._deduplicate(blocks)

        # Sort by time, most recent first
        blocks.sort(key=lambda b: b.seq, reverse=True)
        return blocks

    def _make_block(self, messages: List[Message]) -> MessageBlock:
        m0 = messages[0]
        m_last = messages[-1]
        return MessageBlock(
            group_id=m0.talker,
            group_name=m0.talker_name or m0.talker,
            sender_id=m0.sender,
            sender_name=m0.sender_name or m0.sender,
            messages=messages,
            is_self=any(m.is_self for m in messages),
            time_start=m0.time,
            time_end=m_last.time,
        )

    def _time_diff_seconds(self, t1: str, t2: str) -> float:
        """Calculate difference in seconds between two time strings."""
        try:
            from datetime import datetime
            fmt = "%Y-%m-%d %H:%M:%S"
            dt1 = datetime.strptime(t1, fmt)
            dt2 = datetime.strptime(t2, fmt)
            return abs((dt2 - dt1).total_seconds())
        except (ValueError, TypeError):
            return 999  # can't parse, treat as large gap

    def _deduplicate(self, blocks: List[MessageBlock]) -> List[MessageBlock]:
        """Remove near-duplicate messages across groups (forwarded content)."""
        seen = set()
        result = []
        for block in blocks:
            content_sig = block.combined_content[:200].strip()
            sender = block.sender_id
            h = hashlib.md5(f"{sender}|{content_sig}".encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                result.append(block)
        return result
