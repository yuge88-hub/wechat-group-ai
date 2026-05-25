"""Group selection and prioritization for the WeChat Agent.

Determines which groups to monitor based on activity level, member count,
and user configuration.
"""

from typing import List, Dict, Optional


class GroupManager:
    def __init__(self, db_service, config):
        self.db = db_service
        self.config = config
        self.mode = config.mode
        self.watchlist = config.watchlist
        self.exclude = set(config.exclude)
        self.min_members = config.min_members
        self.max_groups = config.max_groups

    def select_groups(self, state) -> List[Dict]:
        """Return list of groups to check, each with metadata.

        Returns: [{'id': 'xxx@chatroom', 'name': '群名', 'priority': 3, ...}]
        """
        if self.mode == "manual" and self.watchlist:
            return self._resolve_by_name(self.watchlist)

        return self._auto_select(state)

    def _auto_select(self, state) -> List[Dict]:
        """Auto-select groups based on session activity and chatroom list.

        Strategy:
        1. Get all chatrooms from DBService
        2. Get all sessions (sorted by last activity)
        3. Cross-reference: sessions that are chatrooms
        4. Filter by member count and exclude list
        5. Sort by activity and take top max_groups
        """
        # Get chatrooms for member count
        chatrooms = self.db.get_chatrooms(keyword="", limit=0, offset=0)

        # Build lookup: chatroom name -> member count
        cr_info = {}
        for cr in chatrooms.items:
            cr_info[cr.name] = {
                'name': cr.name,
                'display': cr.display_name(),
                'members': len(cr.users),
            }

        # Get active sessions
        sessions = self.db.get_sessions(keyword="", limit=200, offset=0)

        # Filter to chatroom sessions, sort by activity
        group_sessions = []
        for s in sessions.items:
            if not s.username.endswith('@chatroom'):
                continue
            if s.username in self.exclude:
                continue

            info = cr_info.get(s.username, {})
            member_count = info.get('members', 0)
            if member_count > 0 and member_count < self.min_members:
                continue

            # Priority: from state if previously tracked, otherwise default 3
            gs = state.groups.get(s.username)
            priority = gs.priority if gs else 3

            group_sessions.append({
                'id': s.username,
                'name': s.nick_name or info.get('display', s.username),
                'priority': priority,
                'member_count': member_count,
                'last_msg_time': s.time,
                'last_msg_preview': s.content[:80] if s.content else '',
            })

        # Sort: active groups with higher priority first
        group_sessions.sort(key=lambda g: (g['priority'], g.get('last_msg_time', '')), reverse=True)

        return group_sessions[:self.max_groups]

    def _resolve_by_name(self, names: List[str]) -> List[Dict]:
        """Resolve group names or IDs to group metadata.

        Supports: exact chatroom ID, partial name match via chatrooms API.
        """
        chatrooms = self.db.get_chatrooms(keyword="", limit=0, offset=0)

        # Build name -> chatroom mapping
        by_id = {}
        by_display = {}
        for cr in chatrooms.items:
            by_id[cr.name] = cr
            display = cr.display_name()
            if display:
                by_display[display] = cr

        result = []
        for name in names:
            cr = by_id.get(name) or by_display.get(name)
            if cr:
                result.append({
                    'id': cr.name,
                    'name': cr.display_name(),
                    'priority': 5,
                    'member_count': len(cr.users),
                    'last_msg_time': '',
                    'last_msg_preview': '',
                })
            else:
                # Could be a partial match, search
                matches = self.db.get_chatrooms(keyword=name, limit=5, offset=0)
                for m in matches.items:
                    if m.name not in [r['id'] for r in result]:
                        result.append({
                            'id': m.name,
                            'name': m.display_name(),
                            'priority': 3,
                            'member_count': len(m.users),
                            'last_msg_time': '',
                            'last_msg_preview': '',
                        })

        return result[:self.max_groups]

    def update_priorities(self, state, digest_results: List[Dict]):
        """After digest, adjust group priorities based on findings.

        Groups with more important messages get higher priority.
        Groups with zero important messages in 3 consecutive runs
        get demoted.
        """
        for result in digest_results:
            gid = result.get('group_id', '')
            important = result.get('important_count', 0)
            if gid in state.groups:
                gs = state.groups[gid]
                if important > 5:
                    gs.priority = min(5, gs.priority + 1)
                elif important == 0:
                    gs.priority = max(1, gs.priority - 1)
