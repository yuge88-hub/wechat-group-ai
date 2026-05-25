"""State persistence for WeChat Group AI Agent.

Tracks per-group last check time, message sequence numbers, and digest history.
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class GroupCheckState:
    group_id: str = ""           # e.g. "12345678@chatroom"
    group_name: str = ""         # resolved display name
    last_check_time: int = 0     # Unix timestamp of last poll
    last_message_seq: int = 0    # last seen sort_seq for delta detection
    priority: int = 3            # 1-5, higher = more important
    total_messages: int = 0      # cumulative message count processed
    important_count: int = 0     # cumulative high-importance count
    is_active: bool = True       # recently active?


@dataclass
class DigestRecord:
    id: str = ""
    time: str = ""
    type: str = "once"
    groups_covered: int = 0
    messages_processed: int = 0
    important_found: int = 0
    file: str = ""


@dataclass
class AgentState:
    version: int = 1
    created: str = ""
    last_updated: str = ""
    groups: Dict[str, GroupCheckState] = None
    digest_history: List[DigestRecord] = None
    meta: dict = None

    def __post_init__(self):
        if self.groups is None:
            self.groups = {}
        if self.digest_history is None:
            self.digest_history = []
        if self.meta is None:
            self.meta = {}


class StateManager:
    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, "agent_state.json")
        self._state: Optional[AgentState] = None

    def load(self) -> AgentState:
        if self._state is not None:
            return self._state

        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            groups = {}
            for gid, gdata in raw.get('groups', {}).items():
                groups[gid] = GroupCheckState(**gdata)
            history = [DigestRecord(**h) for h in raw.get('digest_history', [])]
            self._state = AgentState(
                version=raw.get('version', 1),
                created=raw.get('created', ''),
                last_updated=raw.get('last_updated', ''),
                groups=groups,
                digest_history=history,
                meta=raw.get('meta', {}),
            )
        else:
            self._state = AgentState(
                created=datetime.now().isoformat(),
                last_updated=datetime.now().isoformat(),
            )

        return self._state

    def save(self):
        if self._state is None:
            return
        self._state.last_updated = datetime.now().isoformat()
        data = {
            'version': self._state.version,
            'created': self._state.created or datetime.now().isoformat(),
            'last_updated': self._state.last_updated,
            'groups': {gid: asdict(g) for gid, g in self._state.groups.items()},
            'digest_history': [asdict(h) for h in self._state.digest_history],
            'meta': self._state.meta,
        }
        os.makedirs(self.state_dir, exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_group(self, group_id: str) -> GroupCheckState:
        state = self.load()
        if group_id not in state.groups:
            state.groups[group_id] = GroupCheckState(group_id=group_id)
        return state.groups[group_id]

    def update_group(self, group_id: str, group_name: str = "",
                     last_check_time: int = 0, last_message_seq: int = 0,
                     total_messages: int = 0, important_count: int = 0):
        gs = self.get_group(group_id)
        if group_name:
            gs.group_name = group_name
        if last_check_time:
            gs.last_check_time = last_check_time
        if last_message_seq:
            gs.last_message_seq = max(gs.last_message_seq, last_message_seq)
        gs.total_messages += total_messages
        gs.important_count += important_count
        gs.is_active = total_messages > 0

    def record_digest(self, record: DigestRecord):
        state = self.load()
        state.digest_history.append(record)
        if len(state.digest_history) > 200:
            state.digest_history = state.digest_history[-200:]

    def get_last_digest_time(self) -> float:
        state = self.load()
        if state.digest_history:
            last = state.digest_history[-1]
            try:
                return datetime.fromisoformat(last.time).timestamp()
            except (ValueError, TypeError):
                return 0
        return 0

    def state(self) -> AgentState:
        return self.load()
