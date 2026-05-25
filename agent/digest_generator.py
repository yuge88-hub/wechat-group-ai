"""Digest output formatting for the WeChat Group AI Agent.

Generates Markdown files and console summaries from LLM digest results.
"""

import os
from datetime import datetime


class DigestGenerator:
    def __init__(self, config):
        self.digest_dir = config.digest_dir
        self.format = config.format
        self.console_output = config.console_output
        self.windows_notification = config.windows_notification

    def generate(self, digest_content: str, context: dict) -> dict:
        """Save digest to file and return metadata.

        context = {
            'groups_count': int,
            'messages_total': int,
            'important_count': int,
            'hours': float,
            'project_root': str,
        }
        """
        now = datetime.now()
        digest_id = f"digest_{now.strftime('%Y%m%d_%H%M%S')}"
        filename = f"{digest_id}.md"

        digest_dir = os.path.join(context.get('project_root', ''), self.digest_dir)
        os.makedirs(digest_dir, exist_ok=True)
        filepath = os.path.join(digest_dir, filename)

        header = self._build_header(now, context)
        footer = self._build_footer(now)

        full_content = header + "\n" + digest_content + "\n" + footer

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)

        return {
            'id': digest_id,
            'file': filepath,
            'filename': filename,
            'time': now.isoformat(),
            'size': len(full_content),
        }

    def console_summary(self, digest_content: str, context: dict):
        """Print a concise summary to console."""
        if not self.console_output:
            return

        print()
        print("=" * 60)
        print(f"  微信群消息摘要  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        print(f"  覆盖群数: {context.get('groups_count', 0)}")
        print(f"  处理消息: {context.get('messages_total', 0)} 条")
        print(f"  重要消息: {context.get('important_count', 0)} 条")
        print("-" * 60)

        # Print the first few meaningful lines
        lines = [l for l in digest_content.split('\n') if l.strip() and not l.startswith('```')]
        preview = lines[:8]
        for line in preview:
            print(f"  {line[:80]}")
        if len(lines) > 8:
            print(f"  ... (完整报告见文件)")

        filepath = context.get('filepath', '')
        if filepath:
            print(f"\n  完整报告: {filepath}")
        print("=" * 60)
        print()

    def _build_header(self, now: datetime, context: dict) -> str:
        """Build digest file header."""
        return f"""# 微信群消息摘要

> 生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}
> 覆盖范围：最近 {context.get('hours', 0):.1f} 小时
> 覆盖群数：{context.get('groups_count', 0)}
> 处理消息：{context.get('messages_total', 0)} 条
> 筛选重要：{context.get('important_count', 0)} 条

---

"""

    def _build_footer(self, now: datetime) -> str:
        """Build digest file footer."""
        return f"""

---

*由微信群 AI Agent 自动生成 · {now.strftime('%Y-%m-%d %H:%M:%S')}*
*由微信群 AI Agent 自动生成*
"""
