"""Real-time message watcher using file change detection.

Monitors encrypted WeChat DB files for changes, re-decrypts on the fly,
and instantly processes new messages instead of waiting 30 minutes.
"""

import os
import time
import sys
from datetime import datetime
from typing import Dict, Optional, Set

# In PyInstaller frozen mode, sys.path is already set up by run_agent.py
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'weixin-decrypte-script'))

from decrypt_engine import decrypt_db, find_db_files


class FileWatcher:
    """Watch WeChat DB files for changes using mtime polling."""

    def __init__(self, db_storage_path: str, key_file: str, poll_seconds: float = 5.0):
        self.db_path = db_storage_path
        self.poll_seconds = poll_seconds
        self._keys_hex: list = []
        self._mtimes: Dict[str, float] = {}
        self._key_idx: Dict[str, int] = {}  # db_path -> best key index

        # Load keys
        if key_file and os.path.exists(key_file):
            with open(key_file, 'r') as f:
                self._keys_hex = [line.strip().split('\t')[-1] for line in f if line.strip()]
        if not self._keys_hex:
            print("[watch] No keys loaded — run scan_keys.py first")
            return

    def scan_dbs(self) -> Set[str]:
        """Return set of encrypted .db paths in the storage directory."""
        return set(find_db_files(self.db_path))

    def snapshot(self) -> Dict[str, float]:
        """Record current mtime of all encrypted DB files."""
        result = {}
        for db in self.scan_dbs():
            try:
                result[db] = os.path.getmtime(db)
            except OSError:
                result[db] = 0
        return result

    def changed(self, previous: Dict[str, float]) -> list:
        """Return list of (db_path, old_mtime, new_mtime) for changed files."""
        changed_files = []
        current = self.snapshot()

        # Check existing files for changes
        for db, old_mtime in previous.items():
            new_mtime = current.get(db, 0)
            if new_mtime > old_mtime + 0.5:  # 0.5s threshold to avoid noise
                changed_files.append((db, old_mtime, new_mtime))

        # Check for new files
        for db in current:
            if db not in previous:
                changed_files.append((db, 0, current[db]))

        return changed_files

    def re_decrypt_changed(self, changed_files: list) -> list:
        """Re-decrypt changed DBs. Returns list of updated decrypted paths."""
        updated = []
        for db_path, _, _ in changed_files:
            try:
                dec_path = db_path
                if dec_path.endswith('.db'):
                    dec_path = dec_path[:-3] + '.decrypted.db'
                else:
                    dec_path += '.decrypted.db'

                # Try known keys
                best_key = self._get_best_key(db_path)
                if best_key is None:
                    continue

                rawkey = bytes.fromhex(best_key)
                result = decrypt_db(db_path, rawkey, dec_path)
                if result:
                    updated.append(dec_path)
            except Exception as e:
                print(f"  [watch] decrypt failed for {os.path.basename(db_path)}: {e}")
        return updated

    def _get_best_key(self, db_path: str) -> Optional[str]:
        """Get the best key for a specific DB file, caching the result."""
        if db_path in self._key_idx:
            idx = self._key_idx[db_path]
            if idx < len(self._keys_hex):
                return self._keys_hex[idx]

        # Try all keys, remember which one worked
        for i, hex_key in enumerate(self._keys_hex):
            try:
                rawkey = bytes.fromhex(hex_key)
                result = decrypt_db(db_path, rawkey)
                if result:
                    self._key_idx[db_path] = i
                    # Clean up test decryption
                    os.remove(result)
                    return hex_key
            except Exception:
                continue
        return None

    def watch_loop(self, on_new_data):
        """Main watch loop: poll for changes, call on_new_data when messages arrive.

        on_new_data(delta_seconds) -> called when new data is available.
        Returns the time since last successful poll as delta.
        """
        if not self._keys_hex:
            print("[watch] Cannot start — no decryption keys")
            return

        mtimes = self.snapshot()
        last_success = time.time()
        print(f"[watch] 监控 {len(mtimes)} 个数据库文件 (每 {self.poll_seconds}s 检查一次)")
        print("[watch] 等待新消息... (Ctrl+C 停止)")

        while True:
            try:
                time.sleep(self.poll_seconds)
                changed_files = self.changed(mtimes)

                if changed_files:
                    updated = self.re_decrypt_changed(changed_files)
                    if updated:
                        delta = time.time() - last_success
                        last_success = time.time()
                        on_new_data(delta)

                    # Update mtime snapshot
                    mtimes = self.snapshot()

            except KeyboardInterrupt:
                print("\n[watch] 已停止")
                break
            except Exception as e:
                print(f"[watch] 错误: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
