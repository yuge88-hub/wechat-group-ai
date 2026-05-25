"""Core orchestrator for the WeChat Group AI Agent.

Coordinates: group selection → message fetching → filtering →
LLM classification → digest generation → output → state update.
"""

import sys
import os
import time
from datetime import datetime
from typing import List, Dict, Optional

from db_service import DBService
from decrypt_engine import ensure_decrypted

from agent.state_manager import StateManager, DigestRecord
from agent.message_filter import MessageFilter
from agent.llm_client import LLMClient
from agent.group_manager import GroupManager
from agent.digest_generator import DigestGenerator
from agent.prompt_builder import (
    build_classify_prompt,
    build_digest_prompt,
    format_blocks_for_classify,
    format_blocks_for_digest,
)


class WeChatAgent:
    def __init__(self, config):
        self.config = config
        self.project_root = config.project_root

        # Resolve paths
        db_path = config.data.db_storage_path
        if not db_path:
            db_path = os.path.join(
                os.environ.get('USERPROFILE', ''),
                'Documents', 'xwechat_files',
            )
        self.db_path = db_path

        key_file = config.data.key_file
        if not key_file:
            key_file = os.path.join(
                self.project_root, 'weixin-decrypte-script', 'found_keys.txt'
            )
        self.key_file = key_file

        # State
        state_dir = os.path.join(self.project_root, 'state')
        self.state_manager = StateManager(state_dir)

        # Services (initialized in setup)
        self.db: Optional[DBService] = None
        self.group_manager: Optional[GroupManager] = None
        self.filter: Optional[MessageFilter] = None
        self.llm: Optional[LLMClient] = None
        self.digest_gen: Optional[DigestGenerator] = None

    def setup(self):
        """Initialize all services: decrypt + DB + filters + LLM."""
        print("[agent] 正在初始化...")

        # Ensure databases are decrypted
        print(f"[agent] 检查数据库: {self.db_path}")
        if os.path.exists(self.key_file):
            with open(self.key_file, 'r') as f:
                keys = [line.strip().split('\t')[-1] for line in f if line.strip()]
            ensure_decrypted(self.db_path, keys)
        else:
            print("[agent] 未找到 key_file，尝试内存扫描...")
            ensure_decrypted(self.db_path)

        # Initialize DB service
        self.db = DBService(self.db_path)
        self.db.init()
        print(f"[agent] DB 初始化完成: {len(self.db._chatroom_cache)} 群, {len(self.db._contact_cache)} 联系人")

        # Initialize components
        self.group_manager = GroupManager(self.db, self.config.groups)
        self.filter = MessageFilter(self.config.filter)
        self.llm = LLMClient(self.config.llm)
        self.digest_gen = DigestGenerator(self.config.output)

        print("[agent] 初始化完成。")

    def run_once(self, lookback_hours: Optional[int] = None,
                 target_group: Optional[str] = None):
        """Run one polling cycle: fetch new messages → analyze → digest."""
        if self.db is None:
            self.setup()

        state = self.state_manager.load()
        hours = lookback_hours or self.config.schedule.lookback_hours
        now_ts = int(time.time())
        start_ts = now_ts - int(hours * 3600)

        print(f"\n[agent] 开始扫描 (回溯 {hours} 小时)...")
        print(f"[agent] 从 {datetime.fromtimestamp(start_ts).strftime('%m-%d %H:%M')} "
              f"到 {datetime.fromtimestamp(now_ts).strftime('%m-%d %H:%M')}")

        # ---- Step 1: Select groups ----
        if target_group:
            groups = [{'id': target_group, 'name': target_group, 'priority': 5}]
        else:
            groups = self.group_manager.select_groups(state)

        if not groups:
            print("[agent] 没有找到需要监控的群。")
            return None

        print(f"[agent] 选中 {len(groups)} 个群")

        # ---- Step 2: Fetch new messages ----
        all_messages = []
        group_messages_count = {}

        for g in groups:
            gid = g['id']
            gs = state.groups.get(gid)
            last_ts = gs.last_check_time if gs else start_ts
            if last_ts < start_ts:
                last_ts = start_ts

            try:
                msgs, total = self.db.get_messages(
                    talker=gid,
                    start_time=str(last_ts),
                    limit=0,  # no limit
                    offset=0,
                )
                all_messages.extend(msgs)
                group_messages_count[gid] = len(msgs)
            except Exception as e:
                print(f"  [warn] 读取 {gid} 失败: {e}")
                group_messages_count[gid] = 0

        total_raw = len(all_messages)
        print(f"[agent] 获取 {total_raw} 条新消息")

        if total_raw == 0:
            print("[agent] 没有新消息。")
            return {
                'groups_count': len(groups),
                'messages_total': 0,
                'important_count': 0,
                'filepath': '',
                'groups': groups,
            }

        # ---- Step 3: Filter ----
        blocks = self.filter.pipeline(all_messages)
        print(f"[agent] 过滤后: {len(blocks)} 个消息块 (过滤掉 {total_raw - len(blocks)} 条噪音)")

        if not blocks:
            print("[agent] 过滤后无有效消息。")
            return {
                'groups_count': len(groups),
                'messages_total': total_raw,
                'important_count': 0,
                'filepath': '',
                'groups': groups,
            }

        # ---- Step 4: LLM Classification (batched) ----
        BATCH_SIZE = 25
        time_range = f"{datetime.fromtimestamp(start_ts).strftime('%m-%d %H:%M')} ~ {datetime.fromtimestamp(now_ts).strftime('%m-%d %H:%M')}"
        all_classifications = []

        print(f"[agent] 发送 {len(blocks)} 个消息块到 LLM 分类 (每批 {BATCH_SIZE})...")
        for batch_idx in range(0, len(blocks), BATCH_SIZE):
            batch = blocks[batch_idx:batch_idx + BATCH_SIZE]
            batch_text = format_blocks_for_classify(batch)
            sys_prompt, user_prompt = build_classify_prompt(batch_text, time_range=time_range)

            batch_results = self.llm.classify_messages(sys_prompt, user_prompt)
            if batch_results:
                all_classifications.extend(batch_results)
            print(f"  [{batch_idx+1}-{min(batch_idx+BATCH_SIZE, len(blocks))}/{len(blocks)}] "
                  f"返回 {len(batch_results)} 条")

        classifications = all_classifications
        print(f"[agent] LLM 共返回 {len(classifications)} 条分类结果")

        # Merge classifications with block data
        classified_blocks = []
        for i, cls in enumerate(classifications):
            if i < len(blocks):
                block = blocks[i]
                classified_blocks.append({
                    'importance': cls.get('importance', 3),
                    'topic_tags': cls.get('topic_tags', []),
                    'summary_zh': cls.get('summary_zh', ''),
                    'action_items': cls.get('action_items', []),
                    'is_question': cls.get('is_question', False),
                    'should_report': cls.get('should_report', False),
                    'block': {
                        'group_id': block.group_id,
                        'group_name': block.group_name,
                        'sender_name': block.sender_name,
                        'content': block.combined_content,
                        'time': block.time_start,
                        'message_count': block.message_count,
                    },
                })

        # ---- Step 5: Filter to important only ----
        important = [cb for cb in classified_blocks
                     if cb['importance'] >= 3 or cb['should_report']]
        print(f"[agent] 重要消息: {len(important)} 条")

        if not important:
            print("[agent] 没有重要消息需要报告。")
            self._update_state(groups, group_messages_count,
                               all_messages, classified_blocks)
            return {
                'groups_count': len(groups),
                'messages_total': total_raw,
                'important_count': 0,
                'filepath': '',
                'groups': groups,
            }

        # ---- Step 6: Generate Digest ----
        important_text = format_blocks_for_digest(important)
        sys_digest, user_digest = build_digest_prompt(
            important_text,
            hours=hours,
            now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )

        print(f"[agent] 生成摘要中 ({len(important)} 条重要消息)...")
        digest_content = self.llm.generate_digest(sys_digest, user_digest)

        # ---- Step 7: Output ----
        context = {
            'groups_count': len(groups),
            'messages_total': total_raw,
            'important_count': len(important),
            'hours': hours,
            'project_root': self.project_root,
        }

        result = self.digest_gen.generate(digest_content, context)
        context['filepath'] = result['file']

        self.digest_gen.console_summary(digest_content, context)

        # ---- Step 8: Update state ----
        self._update_state(groups, group_messages_count,
                           all_messages, classified_blocks)

        # Record digest
        self.state_manager.record_digest(DigestRecord(
            id=result['id'],
            time=result['time'],
            type="once" if target_group else self.config.schedule.digest_interval,
            groups_covered=len(groups),
            messages_processed=total_raw,
            important_found=len(important),
            file=result['filename'],
        ))
        self.state_manager.save()

        # Print usage
        if self.llm.usage['total_calls'] > 0:
            usage = self.llm.usage
            print(f"\n[agent] API 用量: {usage['total_calls']} 次调用, "
                  f"{usage['total_tokens']} tokens, "
                  f"预估费用 ${usage['estimated_cost_usd']:.4f}")

        return result

    def _update_state(self, groups, group_messages_count,
                      all_messages, classified_blocks):
        """Update state for all scanned groups."""
        now_ts = int(time.time())

        # Per-group important counts
        imp_by_group = {}
        for cb in classified_blocks:
            gid = cb['block'].get('group_id', '')
            if cb['importance'] >= 3:
                imp_by_group[gid] = imp_by_group.get(gid, 0) + 1

        for g in groups:
            gid = g['id']
            count = group_messages_count.get(gid, 0)
            imp_count = imp_by_group.get(gid, 0)

            # Get max seq from messages for this group
            max_seq = 0
            for m in all_messages:
                if m.talker == gid and m.seq > max_seq:
                    max_seq = m.seq

            self.state_manager.update_group(
                group_id=gid,
                group_name=g['name'],
                last_check_time=now_ts,
                last_message_seq=max_seq or 0,
                total_messages=count,
                important_count=imp_count,
            )

    def watch(self):
        """Run continuously with file-change-based real-time monitoring.

        Monitors encrypted DB files for changes (mtime), re-decrypts on the fly,
        and instantly processes new messages. Poll interval in config is ignored
        in favor of fast file polling (~5 seconds).
        """
        from agent.live_watch import FileWatcher

        if self.db is None:
            self.setup()

        watcher = FileWatcher(
            db_storage_path=self.db_path,
            key_file=self.key_file,
            poll_seconds=5.0,
        )

        state = self.state_manager.load()
        last_check_time = int(time.time())
        print(f"[agent] 实时监听已启动 (每5秒检测文件变化)")
        print("[agent] 微信收到新消息后几秒内就会分析。Ctrl+C 停止\n")

        def on_new_data(delta_seconds: float):
            nonlocal last_check_time
            print(f"\n── 检测到新消息 (间隔 {delta_seconds:.0f}秒) ──")

            # Re-init DBService to pick up re-decrypted data
            try:
                if self.db:
                    self.db.close()
                self.db = DBService(self.db_path)
                self.db.init()
                self.group_manager = GroupManager(self.db, self.config.groups)
            except Exception as e:
                print(f"[agent] DB 重载失败: {e}")
                return

            # Quick scan: get recent messages from monitored groups
            now_ts = int(time.time())
            start_ts = last_check_time - 30  # slight overlap to avoid missing

            # Get active group sessions
            groups = self.group_manager.select_groups(state)
            if not groups:
                return

            all_messages = []
            for g in groups[:20]:  # Limit to top 20 for responsiveness
                gid = g['id']
                try:
                    msgs, _ = self.db.get_messages(
                        talker=gid,
                        start_time=str(start_ts),
                        limit=0, offset=0,
                    )
                    if msgs:
                        all_messages.extend(msgs)
                except Exception:
                    pass

            if not all_messages:
                return

            total_raw = len(all_messages)
            blocks = self.filter.pipeline(all_messages)
            if not blocks:
                return

            print(f"[agent] {total_raw}条新消息 → {len(blocks)}个消息块")

            # Classify (batched, fast)
            BATCH_SIZE = 20
            all_classifications = []
            for batch_idx in range(0, len(blocks), BATCH_SIZE):
                batch = blocks[batch_idx:batch_idx + BATCH_SIZE]
                batch_text = format_blocks_for_classify(batch)
                sys_prompt, user_prompt = build_classify_prompt(batch_text)
                results = self.llm.classify_messages(sys_prompt, user_prompt)
                if results:
                    all_classifications.extend(results)

            # Find important blocks
            important_blocks = []
            for i, cls in enumerate(all_classifications):
                if i < len(blocks) and (cls.get('importance', 0) >= 4 or cls.get('should_report')):
                    b = blocks[i]
                    important_blocks.append({
                        'importance': cls.get('importance', 0),
                        'summary_zh': cls.get('summary_zh', ''),
                        'topic_tags': cls.get('topic_tags', []),
                        'group_name': b.group_name,
                        'sender_name': b.sender_name,
                        'content': b.combined_content[:150],
                        'time': b.time_start,
                    })

            if important_blocks:
                print(f"\n{'='*60}")
                print(f"  🔔 重要消息 ({len(important_blocks)}条)")
                print(f"{'='*60}")
                for ib in sorted(important_blocks, key=lambda x: -x['importance']):
                    print(f"\n  ⭐ {'★' * ib['importance']}")
                    print(f"  群: {ib['group_name']}")
                    print(f"  人: {ib['sender_name']}")
                    print(f"  摘要: {ib['summary_zh']}")
                    if ib['topic_tags']:
                        print(f"  标签: {', '.join(ib['topic_tags'])}")
                    print(f"  内容: {ib['content'][:100]}")
                print(f"\n{'='*60}\n")

            # Update state
            max_seq = max((m.seq for m in all_messages), default=0)
            for g in groups[:20]:
                self.state_manager.update_group(
                    group_id=g['id'],
                    group_name=g['name'],
                    last_check_time=now_ts,
                    last_message_seq=max_seq or 0,
                    total_messages=total_raw,
                    important_count=len(important_blocks),
                )
            self.state_manager.save()
            last_check_time = now_ts

        try:
            watcher.watch_loop(on_new_data)
        except KeyboardInterrupt:
            print("\n[agent] 已停止。")

    def shutdown(self):
        """Clean up resources."""
        if self.db:
            self.db.close()
