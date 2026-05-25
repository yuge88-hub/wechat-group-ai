"""Entry point for 微信群 AI Agent (dev + PyInstaller onedir)."""
import sys
import os

if getattr(sys, 'frozen', False):
    APP_ROOT = os.path.dirname(sys.executable)
    BUNDLE = os.path.join(APP_ROOT, '_internal')
    wxd_path = os.path.join(BUNDLE, 'weixin-decrypte-script')
    cfg_path = os.path.join(APP_ROOT, 'agent', 'config.yaml')
    if not os.path.exists(cfg_path):
        cfg_path = os.path.join(BUNDLE, 'agent', 'config.yaml')
else:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    wxd_path = os.path.join(APP_ROOT, 'weixin-decrypte-script')
    cfg_path = os.path.join(APP_ROOT, 'agent', 'config.yaml')

sys.path.insert(0, wxd_path)
sys.path.insert(0, APP_ROOT)

from agent.main import main

if __name__ == '__main__':
    if '--config' not in sys.argv:
        sys.argv.extend(['--config', cfg_path])
    main()
