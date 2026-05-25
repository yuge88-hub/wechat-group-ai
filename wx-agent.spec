# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run_agent.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('weixin-decrypte-script', 'weixin-decrypte-script'),
        ('chat_app.py', '.'),
        ('agent/chat.html', 'agent'),
    ],
    hiddenimports=[
        'db_service', 'decrypt_engine', 'models',
        'openai', 'yaml',
        'Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES', 'Crypto.Cipher._mode_cbc',
        'Crypto.Hash', 'Crypto.Hash.HMAC', 'Crypto.Hash.SHA512',
        'Crypto.Protocol', 'Crypto.Protocol.KDF',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'pandas', 'sqlalchemy',
               'openpyxl', 'lxml', 'PIL', 'IPython', 'jedi', 'parso',
               'bs4', 'requests', 'urllib3', 'tqdm', 'fsspec'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='wx-agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='wx-agent',
)
