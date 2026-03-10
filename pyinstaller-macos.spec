# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(
    ["app_entry.py"],
    pathex=["src"],
    binaries=[],
    datas=[("resources/app_icon.icns", "resources")],
    hiddenimports=["openai", "httpx", "httpcore", "anyio", "sniffio", "certifi", "h11", "pydantic", "pydantic_core", "jiter", "annotated_types", "typing_extensions", "typing_inspection"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="FFmpegWrapper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="resources/app_icon.icns",
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name="FFmpegWrapper.app",
    icon="resources/app_icon.icns",
    bundle_identifier="com.example.ffmpegwrapper",
)

