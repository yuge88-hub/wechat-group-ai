"""Configuration loader for WeChat Group AI Agent."""

import os
import re
import sys
import yaml
from dataclasses import dataclass, field
from typing import List, Optional


def _expand_env(value):
    """Replace ${VAR_NAME} with environment variable."""
    if not isinstance(value, str):
        return value
    pattern = re.compile(r'\$\{([^}]+)\}')
    return pattern.sub(lambda m: os.environ.get(m.group(1), ''), value)


@dataclass
class LLMConfig:
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model_filter: str = "deepseek-chat"
    model_digest: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0.3

    def __post_init__(self):
        if self.api_key and '${' in self.api_key:
            self.api_key = _expand_env(self.api_key)
        if not self.api_key:
            self.api_key = os.environ.get("ANTHROPIC_API_KEY",
                        os.environ.get("OPENAI_API_KEY",
                        os.environ.get("DEEPSEEK_API_KEY", "")))


@dataclass
class DataConfig:
    db_storage_path: str = ""
    key_file: str = ""

    def __post_init__(self):
        if self.key_file and '${' in str(self.key_file):
            self.key_file = _expand_env(self.key_file)


@dataclass
class GroupConfig:
    mode: str = "auto"
    watchlist: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    min_members: int = 5
    max_groups: int = 50


@dataclass
class FilterConfig:
    min_text_length: int = 5
    skip_types: List[int] = field(default_factory=lambda: [3, 34, 43, 47, 50, 10000])
    skip_sub_types: List[int] = field(default_factory=lambda: [8, 62, 2000, 2001])
    skip_patterns: List[str] = field(default_factory=lambda: [
        r'^\[.*\]$',
        r'^[嗯哦啊好]+$',
        r'^(好的|收到|谢谢|ok|OK|1|顶|赞|哈哈|👍|👌)$',
    ])
    aggregation_window_seconds: int = 120


@dataclass
class ScheduleConfig:
    poll_interval_minutes: int = 30
    lookback_hours: int = 24
    digest_hour: int = 9
    digest_interval: str = "hourly"


@dataclass
class OutputConfig:
    digest_dir: str = "digests"
    format: str = "markdown"
    console_output: bool = True
    windows_notification: bool = False


@dataclass
class AgentConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    data: DataConfig = field(default_factory=DataConfig)
    groups: GroupConfig = field(default_factory=GroupConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    project_root: str = ""


def load_config(path: str) -> AgentConfig:
    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}

    raw = _resolve_env_recursive(raw)

    llm_raw = raw.get('llm', {})
    llm = LLMConfig(
        provider=llm_raw.get('provider', 'openai'),
        api_key=llm_raw.get('api_key', ''),
        base_url=llm_raw.get('base_url', ''),
        model_filter=llm_raw.get('model_filter', 'deepseek-chat'),
        model_digest=llm_raw.get('model_digest', 'deepseek-chat'),
        max_tokens=llm_raw.get('max_tokens', 4096),
        temperature=llm_raw.get('temperature', 0.3),
    )

    data_raw = raw.get('data', {})
    data = DataConfig(
        db_storage_path=data_raw.get('db_storage_path', ''),
        key_file=data_raw.get('key_file', ''),
    )

    groups_raw = raw.get('groups', {})
    groups = GroupConfig(
        mode=groups_raw.get('mode', 'auto'),
        watchlist=groups_raw.get('watchlist', []),
        exclude=groups_raw.get('exclude', []),
        min_members=groups_raw.get('min_members', 5),
        max_groups=groups_raw.get('max_groups', 50),
    )

    filter_raw = raw.get('filter', {})
    filter_cfg = FilterConfig(
        min_text_length=filter_raw.get('min_text_length', 5),
        skip_types=filter_raw.get('skip_types', [3, 34, 43, 47, 50, 10000]),
        skip_sub_types=filter_raw.get('skip_sub_types', [8, 62, 2000, 2001]),
        skip_patterns=filter_raw.get('skip_patterns', filter_cfg_default_patterns()),
        aggregation_window_seconds=filter_raw.get('aggregation_window_seconds', 120),
    )

    sched_raw = raw.get('schedule', {})
    schedule = ScheduleConfig(
        poll_interval_minutes=sched_raw.get('poll_interval_minutes', 30),
        lookback_hours=sched_raw.get('lookback_hours', 24),
        digest_hour=sched_raw.get('digest_hour', 9),
        digest_interval=sched_raw.get('digest_interval', 'hourly'),
    )

    out_raw = raw.get('output', {})
    output = OutputConfig(
        digest_dir=out_raw.get('digest_dir', 'digests'),
        format=out_raw.get('format', 'markdown'),
        console_output=out_raw.get('console_output', True),
        windows_notification=out_raw.get('windows_notification', False),
    )

    if getattr(sys, 'frozen', False):
        project_root = os.path.dirname(sys.executable)
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return AgentConfig(
        llm=llm,
        data=data,
        groups=groups,
        filter=filter_cfg,
        schedule=schedule,
        output=output,
        project_root=project_root,
    )


def filter_cfg_default_patterns() -> List[str]:
    return [
        r'^\[.*\]$',
        r'^[嗯哦啊好]+$',
        r'^(好的|收到|谢谢|ok|OK|1|顶|赞|哈哈|👍|👌)$',
    ]


def _resolve_env_recursive(obj):
    if isinstance(obj, dict):
        return {k: _resolve_env_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_recursive(v) for v in obj]
    elif isinstance(obj, str):
        return _expand_env(obj)
    return obj
