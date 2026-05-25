"""Entry point for the WeChat Group AI Agent.

Usage:
    # One-time scan with default config
    python -m agent.main --once

    # Scan with custom lookback
    python -m agent.main --once --lookback 6

    # Scan a specific group
    python -m agent.main --once --group "53327347948@chatroom"

    # Continuous watch mode
    python -m agent.main --watch

    # Custom config
    python -m agent.main --config my_config.yaml --once
"""

import sys
import os
import argparse

# Ensure the project root and weixin-decrypte-script are on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'weixin-decrypte-script'))
sys.path.insert(0, ROOT)

from agent.config import load_config
from agent.agent_core import WeChatAgent


def main():
    parser = argparse.ArgumentParser(
        description="微信群 AI Agent — 自动整理群聊重要信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m agent.main --once                  # 单次扫描（默认回溯24小时）
  python -m agent.main --once --lookback 6     # 回溯6小时
  python -m agent.main --once --group "xxx@chatroom"  # 只扫描指定群
  python -m agent.main --watch                 # 持续监控模式
  python -m agent.main --config prod.yaml      # 使用自定义配置
        """,
    )
    parser.add_argument(
        '--config', default=None,
        help='配置文件路径 (默认: agent/config.yaml)',
    )
    parser.add_argument(
        '--mode', choices=['once', 'watch'], default='once',
        help='运行模式: once=单次扫描, watch=持续监控',
    )
    parser.add_argument(
        '--lookback', type=int, default=None,
        help='回溯小时数 (覆盖 config.yaml 中的设置)',
    )
    parser.add_argument(
        '--group', default=None,
        help='只扫描指定群 (群ID 或群名关键词)',
    )
    parser.add_argument(
        '--once', action='store_true',
        help='等价于 --mode once',
    )
    parser.add_argument(
        '--watch', action='store_true',
        help='等价于 --mode watch',
    )

    args = parser.parse_args()

    # Resolve mode
    mode = args.mode
    if args.once:
        mode = 'once'
    elif args.watch:
        mode = 'watch'

    # Load config
    config_path = args.config
    if not config_path:
        default_path = os.path.join(ROOT, 'agent', 'config.yaml')
        if os.path.exists(default_path):
            config_path = default_path
        else:
            print("[main] 未找到 config.yaml，使用默认配置")
            config_path = None

    if config_path:
        config = load_config(config_path)
        print(f"[main] 加载配置: {config_path}")
    else:
        from agent.config import AgentConfig
        config = AgentConfig(project_root=ROOT)

    # Set default data paths if not configured
    if not config.data.db_storage_path:
        # Auto-detect WeChat data directory
        candidates = []
        if os.name == 'nt':
            # Windows: Documents\xwechat_files
            userprofile = os.environ.get('USERPROFILE', '')
            candidates.append(os.path.join(userprofile, 'Documents', 'xwechat_files'))
        else:
            # macOS/Linux: ~/Library/Containers or ~/.wx-cli
            home = os.path.expanduser('~')
            candidates.append(os.path.join(home, 'Library', 'Containers', 'com.tencent.xinWeChat'))
            candidates.append(os.path.join(home, '.wechat_data'))

        for base in candidates:
            if not os.path.isdir(base):
                continue
            # Find wxid_* directories and pick one with db_storage
            for name in os.listdir(base):
                full = os.path.join(base, name)
                db_dir = os.path.join(full, 'db_storage')
                if os.path.isdir(db_dir):
                    config.data.db_storage_path = db_dir
                    break
            if config.data.db_storage_path:
                break

    if not config.data.key_file:
        key_file = os.path.join(ROOT, 'weixin-decrypte-script', 'found_keys.txt')
        if os.path.exists(key_file):
            config.data.key_file = key_file

    print(f"[main] 数据目录: {config.data.db_storage_path}")
    print(f"[main] 密钥文件: {config.data.key_file}")

    # Create agent
    agent = WeChatAgent(config)
    agent.setup()

    try:
        if mode == 'watch':
            agent.watch()
        else:
            result = agent.run_once(
                lookback_hours=args.lookback,
                target_group=args.group,
            )
            if result:
                fp = result.get('filepath', '')
                if fp:
                    print(f"\n[main] 摘要已保存: {fp}")
    finally:
        agent.shutdown()


if __name__ == '__main__':
    main()
